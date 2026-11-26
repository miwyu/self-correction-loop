#!/usr/bin/env python3
"""Mechanical gate for self-correction-loop (stdlib only, Python 3.8+).

Usage: python3 loop_guard.py init <ws> <slug> --request-file F
       python3 loop_guard.py freeze <run_dir>
       python3 loop_guard.py guards <run_dir> [--expect D]
       python3 loop_guard.py checks <run_dir>
       python3 loop_guard.py preflight <run_dir>
       python3 loop_guard.py finish <run_dir> {pass|stopped|failed} [note]

Runs live in <ws>/.loop/YYYYMMDD-HHMM-<slug>; CHECKs run in <ws>
without a shell. EXPECT lines must occur in stdout + stderr.
Exit 0 = OK, 1 = check/guard failure, 2 = usage or format error.
"""
import datetime, hashlib, json, os, re, shlex, subprocess, sys

TIMEOUT = int(os.environ.get("LOOP_CHECK_TIMEOUT", "600"))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def paths(loop_dir):
    loop_dir = os.path.abspath(loop_dir)
    return loop_dir, os.path.dirname(os.path.dirname(loop_dir))


SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def git(ws, *args):
    try:
        r = subprocess.run(["git", "-C", ws, *args], capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def skill_hash():
    """sha256 over every file of this skill (relative path + content), so a run records which text it ran under."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = hashlib.sha256()
    for dp, dn, fn in sorted(os.walk(root)):
        dn[:] = sorted(d for d in dn if d != "__pycache__" and not d.startswith("."))
        for f in sorted(fn):
            if f.startswith(".") or f.endswith(".pyc"):
                continue
            full = os.path.join(dp, f)
            h.update(os.path.relpath(full, root).encode() + b"\0" + sha256(full).encode() + b"\n")
    return h.hexdigest()


def cmd_init(ws, slug, request_file):
    ws = os.path.realpath(ws)
    if not SLUG_RE.match(slug) or len(slug) > 30:
        print("INIT: FAIL - slug must be lowercase a-z0-9 words joined by '-', max 30 chars")
        return 2
    try:
        with open(request_file, "rb") as f:
            request = f.read()
    except OSError as e:
        print(f"INIT: FAIL - cannot read request file: {e}")
        return 2
    if not request.strip():
        print("INIT: FAIL - request file must not be empty")
        return 2
    now = datetime.datetime.now().astimezone()
    base = os.path.join(ws, ".loop", now.strftime("%Y%m%d-%H%M") + "-" + slug)
    run, k = base, 2
    while os.path.exists(run):
        run, k = f"{base}-{k}", k + 1
    os.makedirs(run)
    rc, _ = git(ws, "rev-parse", "--is-inside-work-tree")
    in_repo = rc == 0
    state = {"status": "running", "started_at": now.isoformat(timespec="seconds"),
             "skill_sha256": skill_hash(), "workspace": ws, "git": None}
    if in_repo:
        _, head = git(ws, "rev-parse", "HEAD")
        _, branch = git(ws, "rev-parse", "--abbrev-ref", "HEAD")
        _, status = git(ws, "status", "--porcelain")
        state["git"] = {"head": head.strip() or None, "branch": branch.strip() or None,
                        "status_porcelain": status.splitlines()}
        _, common = git(ws, "rev-parse", "--path-format=absolute", "--git-common-dir")
        exc = os.path.join(common.strip(), "info", "exclude")
        os.makedirs(os.path.dirname(exc), exist_ok=True)
        lines = open(exc, encoding="utf-8").read().splitlines() if os.path.isfile(exc) else []
        if ".loop/" not in lines:
            with open(exc, "a", encoding="utf-8") as f:
                f.write("\n.loop/\n")
    with open(os.path.join(run, "STATE.json"), "x", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    with open(os.path.join(run, "REQUEST.md"), "xb") as f:
        f.write(request)
    runs = len([d for d in os.listdir(os.path.join(ws, ".loop")) if os.path.isdir(os.path.join(ws, ".loop", d))])
    print(run)
    print(f"INIT: OK - run dir created ({runs} run(s) now under .loop/)", file=sys.stderr)
    return 0


def parse_rubric(text):
    """Return (sections, protected_paths, criteria). criteria: list of dicts."""
    sections = set(re.findall(r"^## (.+?)\s*$", text, re.M))
    protected, criteria, cur, sec = [], [], None, None
    for line in text.splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
            continue
        if sec == "Protected files" and line.startswith("- "):
            p = line[2:].strip()
            if p != "(none)":
                protected.append(p)
        if sec == "Criteria":
            m = re.match(r"^### (C\d+):\s*(.*)$", line)
            if m:
                cur = {"id": m.group(1), "name": m.group(2), "check": None, "expect": [], "manual": None}
                criteria.append(cur)
            elif cur and line.startswith("CHECK: "):
                cur["check"] = line[7:].strip()
            elif cur and line.startswith("EXPECT: "):
                cur["expect"].append(line[8:].strip())
            elif cur and line.startswith("MANUAL: "):
                cur["manual"] = line[8:].strip()
    return sections, protected, criteria


def _git(ws, *args):
    try:
        r = subprocess.run(['git', '-C', ws, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''
    return r.returncode, r.stdout.strip()


def git_anchor(ws, path):
    """Tie a protected file to a committed blob: a reference the run records cannot rewrite."""
    rc, head = _git(ws, 'rev-parse', '--verify', 'HEAD')
    if rc:
        return {'anchor': 'none', 'reason': 'no git commit'}
    rc, blob = _git(ws, 'rev-parse', '--verify', head + ':./' + path)
    if rc:
        return {'anchor': 'none', 'reason': 'not committed at HEAD', 'head': head}
    rc, cur = _git(ws, 'hash-object', '--', path)
    if rc or cur != blob:
        return {'anchor': 'none', 'reason': 'differs from HEAD', 'head': head}
    return {'anchor': 'git', 'head': head, 'blob': blob}


def anchor_ok(ws, path, item):
    rc, blob = _git(ws, 'rev-parse', '--verify', item['head'] + ':./' + path)
    rc2, cur = _git(ws, 'hash-object', '--', path)
    return not rc and not rc2 and blob == item['blob'] == cur


def freeze_digest(loop_dir):
    return sha256(os.path.join(loop_dir, 'FREEZE.json'))[:16]


def say(tag, ok, msg):
    print(f"{tag}: {'OK' if ok else 'FAIL'} - {msg}")
    return ok


def cmd_freeze(loop_dir):
    loop_dir, ws = paths(loop_dir)
    rub, frz = os.path.join(loop_dir, "RUBRIC.md"), os.path.join(loop_dir, "FREEZE.json")
    if os.path.exists(frz):
        return say("FREEZE", False, "FREEZE.json already exists; refusing to re-freeze") and 0 or 2
    req = os.path.join(loop_dir, "REQUEST.md")
    if not os.path.isfile(req) or not os.path.getsize(req):
        return say("FREEZE", False, "REQUEST.md missing or empty") and 0 or 2
    if not os.path.isfile(rub):
        return say("FREEZE", False, "RUBRIC.md missing") and 0 or 2
    _, protected, criteria = parse_rubric(open(rub, encoding="utf-8").read())
    if not any(c["id"].startswith("C") for c in criteria):
        return say("FREEZE", False, "no '### C<n>:' criteria") and 0 or 2
    files = {}
    for p in protected:
        full = os.path.normpath(os.path.join(ws, p))
        if not full.startswith(ws + os.sep) or not os.path.isfile(full):
            return say("FREEZE", False, f"protected path missing or outside workspace: {p}") and 0 or 2
        files[p] = sha256(full)
    data = {"rubric_sha256": sha256(rub), "request_sha256": sha256(req),
            "protected": files, "anchors": {p: git_anchor(ws, p) for p in protected}}
    with open(frz, "x", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    say("FREEZE", True, f"RUBRIC.md + REQUEST.md + {len(files)} protected file(s) frozen digest={freeze_digest(loop_dir)}")
    return 0


def guards(loop_dir, expect=None):
    loop_dir, ws = paths(loop_dir)
    frz = os.path.join(loop_dir, "FREEZE.json")
    if not os.path.isfile(frz):
        say("GUARDS", False, "FREEZE.json missing (rubric was never frozen)")
        return False
    data = json.load(open(frz, encoding="utf-8"))
    ok = True
    rub = os.path.join(loop_dir, "RUBRIC.md")
    if not os.path.isfile(rub) or sha256(rub) != data["rubric_sha256"]:
        ok = say("GUARDS", False, "RUBRIC.md changed after freeze") and ok
    for p, want in data["protected"].items():
        full = os.path.join(ws, p)
        if not os.path.isfile(full):
            ok = say("GUARDS", False, f"protected file missing: {p}") and ok
        elif sha256(full) != want:
            ok = say("GUARDS", False, f"protected file modified: {p}") and ok
        else:
            say("GUARDS", True, f"{p} unchanged")
    req = os.path.join(loop_dir, "REQUEST.md")
    if not os.path.isfile(req):
        ok = say("GUARDS", False, "REQUEST.md missing") and ok
    if os.path.isfile(req) and sha256(req) != data.get('request_sha256'):
        ok = say('GUARDS', False, 'REQUEST.md changed after freeze') and ok
    for p, item in data.get('anchors', {}).items():
        if item.get('anchor') == 'git':
            if not anchor_ok(ws, p, item):
                ok = say('GUARDS', False, f'git anchor broken: {p} no longer matches the commit recorded at freeze') and ok
        else:
            print(f"GUARDS: NOTE - unanchored: {p} ({item.get('reason')})")
    if expect and freeze_digest(loop_dir) != expect:
        ok = say('GUARDS', False, f'FREEZE.json digest {freeze_digest(loop_dir)} != expected {expect}') and ok
    if ok:
        say("GUARDS", True, f"rubric + request + {len(data['protected'])} protected file(s) match FREEZE.json")
    return ok


def checks(loop_dir):
    loop_dir, ws = paths(loop_dir)
    _, _, criteria = parse_rubric(open(os.path.join(loop_dir, "RUBRIC.md"), encoding="utf-8").read())
    ok = True
    for c in criteria:
        if c["manual"] and not c["check"]:
            print(f"{c['id']}: MANUAL - {c['manual']}")
            continue
        if not c["check"]:
            ok = say(c["id"], False, "neither CHECK nor MANUAL") and ok
            continue
        try:
            r = subprocess.run(shlex.split(c["check"]), cwd=ws, capture_output=True, text=True, timeout=TIMEOUT)
            out = (r.stdout or "") + (r.stderr or "")
            missing = [e for e in c["expect"] if e not in out]
            last = (out.strip().splitlines() or [""])[-1][:200]
            passed = r.returncode == 0 and not missing
            detail = f"exit={r.returncode}" + (f", missing EXPECT {missing!r}" if missing else "") + f" | {last}"
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            passed, detail = False, f"could not run: {e}"
        ok = say(c["id"], passed, f"{c['check']} -> {detail}") and ok
    return ok


def preflight(loop_dir):
    loop_dir, _ = paths(loop_dir)
    ok = True
    for f in ("STATE.json", "REQUEST.md", "RUBRIC.md", "EXPERIMENTS.md", "FREEZE.json"):
        p = os.path.join(loop_dir, f)
        ok = say("PREFLIGHT", os.path.isfile(p) and os.path.getsize(p) > 0, f"{f} present") and ok
    if not ok:
        return False
    sections, _, criteria = parse_rubric(open(os.path.join(loop_dir, "RUBRIC.md"), encoding="utf-8").read())
    for s in ("Goal", "Protected files", "Criteria"):
        ok = say("PREFLIGHT", s in sections, f"RUBRIC.md section '## {s}'") and ok
    n_c = sum(c["id"].startswith("C") for c in criteria)
    ok = say("PREFLIGHT", n_c > 0, f"{n_c} criteria") and ok
    exp = open(os.path.join(loop_dir, "EXPERIMENTS.md"), encoding="utf-8").read()
    ok = say("PREFLIGHT", "## Baseline" in exp, "EXPERIMENTS.md '## Baseline'") and ok
    blocks = re.split(r'^## ', exp, flags=re.M)[1:]
    iters = [b for b in blocks if re.match(r'Iteration \d+', b)]
    ok = say('PREFLIGHT', len(iters) >= 1, f'{len(iters)} iteration block(s)') and ok
    for b in iters:
        name = b.splitlines()[0].strip()
        missing = [f for f in ('CHANGE:', 'WHY:', 'RESULT:', 'DECISION:')
                   if not re.search(rf'^{f}\s*\S', b, re.M)]
        ok = say('PREFLIGHT', not missing, f"{name}: {'complete' if not missing else 'missing ' + ' '.join(missing)}") and ok
    ok = guards(loop_dir) and ok
    ok = checks(loop_dir) and ok
    print("PREFLIGHT: ALL OK - ready for the verifier" if ok else "PREFLIGHT: FAILED - fix before spawning the verifier")
    return ok


def read_verdict(run_dir):
    """Return the highest-numbered verdict and its last non-empty line's result."""
    names = sorted(f for f in os.listdir(run_dir) if re.match(r"VERDICT-\d{2}\.md$", f))
    if not names:
        return None, None
    with open(os.path.join(run_dir, names[-1]), encoding="utf-8") as f:
        lines = [line.strip() for line in f.read().splitlines() if line.strip()]
    overall = "PASS" if lines and lines[-1] == "OVERALL: PASS" else None
    return names[-1], overall


def cmd_finish(run_dir, status, note):
    p = os.path.join(os.path.abspath(run_dir), "STATE.json")
    if status not in ("pass", "stopped", "failed") or not os.path.isfile(p):
        print("FINISH: FAIL - usage: finish <run_dir> {pass|stopped|failed} [note]")
        return 2
    st = json.load(open(p, encoding="utf-8"))
    if status == "pass":
        run = os.path.dirname(p)
        name, overall = read_verdict(run)
        why = None
        if name is None:
            why = "no VERDICT-NN.md in the run directory (save the verifier's reply first)"
        elif overall != "PASS":
            why = f"{name} does not end with 'OVERALL: PASS'"
        elif not guards(run):
            why = "guards failed after the verdict"
        if why:
            print(f"FINISH: FAIL - pass refused: {why}. STATE.json unchanged.")
            return 1
    st.update({"status": status, "finished_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
               "note": note,
               "verdicts": sorted(f for f in os.listdir(os.path.dirname(p)) if re.match(r"VERDICT-\d{2}\.md$", f))})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
    print(f"FINISH: OK - status={status}")
    return 0


def main():
    a = sys.argv[1:]
    if len(a) == 5 and a[0] == "init" and a[3] == "--request-file":
        return cmd_init(a[1], a[2], a[4])
    if len(a) == 2 and a[0] == "freeze":
        return cmd_freeze(a[1])
    if a and a[0] == "guards" and (len(a) == 2 or (len(a) == 4 and a[2] == "--expect")):
        return 0 if guards(a[1], a[3] if len(a) == 4 else None) else 1
    if len(a) == 2 and a[0] == "checks":
        return 0 if checks(a[1]) else 1
    if len(a) == 2 and a[0] == "preflight":
        return 0 if preflight(a[1]) else 1
    if len(a) >= 3 and a[0] == "finish":
        return cmd_finish(a[1], a[2], " ".join(a[3:]) or None)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
