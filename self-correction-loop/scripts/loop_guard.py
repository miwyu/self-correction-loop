#!/usr/bin/env python3
"""Mechanical gate for self-correction-loop (stdlib only, Python 3.8+).

Usage: python3 loop_guard.py init <ws> <slug> --request-file F
       python3 loop_guard.py freeze <run_dir>
       python3 loop_guard.py guards <run_dir> [--expect D]
       python3 loop_guard.py checks <run_dir>
       python3 loop_guard.py preflight <run_dir> [--expect D]
       python3 loop_guard.py finish <run_dir> pass --expect D [note]
       python3 loop_guard.py finish <run_dir> {stopped|failed} [note]

Runs live in <ws>/.loop/YYYYMMDD-HHMM-<slug>; CHECKs run in <ws>
without a shell. EXPECT lines must occur in stdout + stderr.
Exit 0 = OK, 1 = check/guard failure, 2 = usage or format error.
"""
import contextlib, datetime, hashlib, io, json, os, re, shlex, subprocess, sys

try:
    TIMEOUT = int(os.environ.get("LOOP_CHECK_TIMEOUT", "600"))
    if TIMEOUT <= 0:
        TIMEOUT = 600
except ValueError:
    TIMEOUT = 600


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_object(path):
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise ValueError(os.path.basename(path) + " must be a JSON object")
    return data


def read_state(path):
    data = read_object(path)
    for key in ("status", "started_at", "skill_sha256", "workspace"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError("STATE.json: missing or invalid " + key)
    if "git" not in data or (data["git"] is not None and not isinstance(data["git"], dict)):
        raise ValueError("STATE.json: missing or invalid git")
    info = data["git"]
    if info is not None:
        for key in ("head", "branch"):
            if key not in info or (info[key] is not None and not isinstance(info[key], str)):
                raise ValueError("STATE.json: missing or invalid git." + key)
        if (not isinstance(info.get("status_porcelain"), list)
                or any(not isinstance(v, str) for v in info["status_porcelain"])):
            raise ValueError("STATE.json: invalid git.status_porcelain")
    for key in ("finished_at", "note"):
        if key in data and not isinstance(data[key], str) and not (key == "note" and data[key] is None):
            raise ValueError("STATE.json: invalid " + key)
    if "verdicts" in data and (not isinstance(data["verdicts"], list)
                              or any(not isinstance(v, str) for v in data["verdicts"])):
        raise ValueError("STATE.json: invalid verdicts")
    return data


def read_freeze(path):
    data = read_object(path)
    if not isinstance(data.get("rubric_sha256"), str) or not isinstance(data.get("protected"), dict):
        raise ValueError("FREEZE.json: missing or invalid rubric_sha256/protected")
    if any(not isinstance(v, str) for v in data["protected"].values()):
        raise ValueError("FREEZE.json: invalid protected hash")
    if "request_sha256" in data and not isinstance(data["request_sha256"], str):
        raise ValueError("FREEZE.json: invalid request_sha256")
    if "anchors" in data:
        if not isinstance(data["anchors"], dict):
            raise ValueError("FREEZE.json: invalid anchors")
        for item in data["anchors"].values():
            if not isinstance(item, dict) or item.get("anchor") not in ("git", "none"):
                raise ValueError("FREEZE.json: invalid anchor entry")
            keys = ("head", "blob") if item["anchor"] == "git" else ("reason",)
            if any(not isinstance(item.get(k), str) or not item[k] for k in keys):
                raise ValueError("FREEZE.json: missing or invalid anchor fields")
    return data


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
        return r.returncode, r.stdout.rstrip("\n")
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


_TOKENS = None


def has_placeholder(value):
    """True if value still holds a placeholder token of the shipped templates.

    Only the templates' own tokens count, so literal text such as '<PASS>' or
    'a < b > c' in a command or an output line is not mistaken for one.
    """
    global _TOKENS
    if _TOKENS is None:
        refs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
        found = set()
        for name in ("rubric-template.md", "experiments-template.md"):
            try:
                with open(os.path.join(refs, name), encoding="utf-8") as f:
                    body = re.sub(r"<!--.*?-->", "", f.read(), flags=re.S)
            except (OSError, UnicodeDecodeError):
                continue
            found.update(re.findall(r"<[^<>\n]+>", body))
        _TOKENS = found
    return any(token in value for token in _TOKENS)


def parse_rubric(text):
    """Return (sections, protected_paths, criteria). criteria: list of dicts."""
    if "<!--" in text:
        raise ValueError("RUBRIC.md: HTML comment remains")
    sections = set()
    goal = []
    no_protected = False
    protected, criteria, cur, sec = [], [], None, None
    for line in text.splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
            if sec in sections and sec in ("Goal", "Protected files", "Criteria"):
                raise ValueError("RUBRIC.md: duplicate section " + sec)
            sections.add(sec)
            cur = None
            continue
        if sec == "Goal":
            if has_placeholder(line):
                raise ValueError("RUBRIC.md: placeholder in Goal")
            goal.append(line)
        if sec == "Protected files" and line.startswith("- "):
            p = line[2:].strip()
            if not p:
                raise ValueError("RUBRIC.md: empty protected path")
            if has_placeholder(p):
                raise ValueError("RUBRIC.md: placeholder in protected path")
            if p == "(none)":
                no_protected = True
            else:
                protected.append(p)
        if sec == "Criteria":
            m = re.match(r"^### (C\d+):\s*(.*)$", line)
            if m:
                if any(c["id"] == m.group(1) for c in criteria):
                    raise ValueError("RUBRIC.md: duplicate criterion " + m.group(1))
                cur = {"id": m.group(1), "name": m.group(2), "check": None, "expect": [], "manual": None}
                criteria.append(cur)
            elif line.startswith(("CHECK:", "EXPECT:", "MANUAL:")):
                if cur is None:
                    raise ValueError("RUBRIC.md: field without a criterion")
                field, value = line.split(":", 1)
                value = value.strip()
                if has_placeholder(value):
                    raise ValueError("RUBRIC.md: placeholder in " + cur["id"] + " " + field)
                if field in ("CHECK", "MANUAL") and not value:
                    raise ValueError("RUBRIC.md: empty " + field + " in " + cur["id"])
                if field == "CHECK":
                    if cur["check"] is not None:
                        raise ValueError("RUBRIC.md: duplicate CHECK in " + cur["id"])
                    cur["check"] = value
                elif field == "EXPECT":
                    cur["expect"].append(value)
                else:
                    if cur["manual"] is not None:
                        raise ValueError("RUBRIC.md: duplicate MANUAL in " + cur["id"])
                    cur["manual"] = value
    for required in ("Goal", "Protected files", "Criteria"):
        if required not in sections:
            raise ValueError("RUBRIC.md: missing section " + required)
    if not "".join(goal).strip():
        raise ValueError("RUBRIC.md: empty Goal")
    if not protected and not no_protected:
        raise ValueError("RUBRIC.md: Protected files requires a path or - (none)")
    if protected and no_protected:
        raise ValueError("RUBRIC.md: Protected files mixes (none) with paths")
    for number, c in enumerate(criteria, 1):
        if c["id"] != f"C{number}":
            raise ValueError(f"RUBRIC.md: expected C{number}, got {c['id']}")
        if bool(c["check"]) == bool(c["manual"]):
            raise ValueError("RUBRIC.md: " + c["id"] + " requires exactly one CHECK or MANUAL")
    return sections, protected, criteria


def git_anchor(ws, path):
    """Tie a protected file to a committed blob: a reference the run records cannot rewrite."""
    rc, head = git(ws, 'rev-parse', '--verify', 'HEAD')
    if rc:
        return {'anchor': 'none', 'reason': 'no git commit'}
    rc, blob = git(ws, 'rev-parse', '--verify', head + ':./' + path)
    if rc:
        return {'anchor': 'none', 'reason': 'not committed at HEAD', 'head': head}
    rc, cur = git(ws, 'hash-object', '--no-filters', '--', path)
    if rc or cur != blob:
        return {'anchor': 'none', 'reason': 'differs from HEAD', 'head': head}
    return {'anchor': 'git', 'head': head, 'blob': blob}


def anchor_ok(ws, path, item):
    rc, blob = git(ws, 'rev-parse', '--verify', item['head'] + ':./' + path)
    rc2, cur = git(ws, 'hash-object', '--no-filters', '--', path)
    return not rc and not rc2 and blob == item['blob'] == cur


def freeze_digest(loop_dir):
    return sha256(os.path.join(loop_dir, 'FREEZE.json'))[:16]


def say(tag, ok, msg):
    print(f"{tag}: {'OK' if ok else 'FAIL'} - {msg}")
    return ok


def protected_path(ws, path):
    """Use the same validated workspace-relative spelling at freeze and guard time."""
    if os.path.isabs(path) or ".." in path.split(os.sep):
        raise ValueError("unsafe protected path: " + path)
    ws = os.path.realpath(ws)
    full = os.path.join(ws, path)
    real = os.path.realpath(full)
    if os.path.commonpath((ws, real)) != ws or real == ws:
        raise ValueError("protected path outside workspace: " + path)
    if os.path.islink(full):
        raise ValueError("protected path is a symlink: " + path)
    if not os.path.isfile(full):
        raise ValueError("protected file missing: " + path)
    return full


def cmd_freeze(loop_dir):
    loop_dir, ws = paths(loop_dir)
    rub, frz = os.path.join(loop_dir, "RUBRIC.md"), os.path.join(loop_dir, "FREEZE.json")
    if os.path.exists(frz):
        say("FREEZE", False, "FREEZE.json already exists; refusing to re-freeze")
        return 2
    req = os.path.join(loop_dir, "REQUEST.md")
    if not os.path.isfile(req) or not os.path.getsize(req):
        say("FREEZE", False, "REQUEST.md missing or empty")
        return 2
    if not os.path.isfile(rub):
        say("FREEZE", False, "RUBRIC.md missing")
        return 2
    _, protected, criteria = parse_rubric(read_text(rub))
    if not any(c["id"].startswith("C") for c in criteria):
        say("FREEZE", False, "no '### C<n>:' criteria")
        return 2
    files = {}
    for p in protected:
        files[p] = sha256(protected_path(ws, p))
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
    data = read_freeze(frz)
    if ("anchors" not in data or "request_sha256" not in data
            or any(p not in data["anchors"] for p in data["protected"])):
        return say("GUARDS", False, "FREEZE.json is incomplete")
    ok = True
    rub = os.path.join(loop_dir, "RUBRIC.md")
    read_text(rub)
    if sha256(rub) != data["rubric_sha256"]:
        ok = say("GUARDS", False, "RUBRIC.md changed after freeze") and ok
    for p, want in data["protected"].items():
        try:
            full = protected_path(ws, p)
        except ValueError as e:
            ok = say("GUARDS", False, str(e)) and ok
            continue
        if sha256(full) != want:
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
    _, _, criteria = parse_rubric(read_text(os.path.join(loop_dir, "RUBRIC.md")))
    if not criteria:
        raise ValueError("RUBRIC.md: no criteria")
    frz = os.path.join(loop_dir, "FREEZE.json")
    if os.path.exists(frz):
        data = read_freeze(frz)
        if sha256(os.path.join(loop_dir, "RUBRIC.md")) != data["rubric_sha256"]:
            return say("CHECKS", False, "RUBRIC.md changed after freeze")
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


def preflight(loop_dir, expect=None):
    loop_dir, _ = paths(loop_dir)
    read_state(os.path.join(loop_dir, "STATE.json"))
    if os.path.exists(os.path.join(loop_dir, "FREEZE.json")):
        read_freeze(os.path.join(loop_dir, "FREEZE.json"))
    # Read required text before presence gates so unreadable input is a format error.
    rubric = read_text(os.path.join(loop_dir, "RUBRIC.md"))
    exp = read_text(os.path.join(loop_dir, "EXPERIMENTS.md"))
    ok = True
    for f in ("STATE.json", "REQUEST.md", "RUBRIC.md", "EXPERIMENTS.md", "FREEZE.json"):
        p = os.path.join(loop_dir, f)
        ok = say("PREFLIGHT", os.path.isfile(p) and os.path.getsize(p) > 0, f"{f} present") and ok
    if not ok:
        return False
    sections, _, criteria = parse_rubric(rubric)
    for s in ("Goal", "Protected files", "Criteria"):
        ok = say("PREFLIGHT", s in sections, f"RUBRIC.md section '## {s}'") and ok
    n_c = sum(c["id"].startswith("C") for c in criteria)
    ok = say("PREFLIGHT", n_c > 0, f"{n_c} criteria") and ok
    block_name = 'preamble'
    for line in exp.splitlines():
        if line.startswith('## '):
            block_name = line[3:]
        if '<!--' in line:
            ok = say('PREFLIGHT', False, f'{block_name}: HTML comment in EXPERIMENTS.md') and ok
        field = re.match(r'^(COMMAND|RESULT|CHANGE|WHY|DECISION):(.*)$', line)
        if field and has_placeholder(field.group(2)):
            ok = say('PREFLIGHT', False, f'{block_name}: placeholder in {field.group(1)}') and ok
    blocks = re.split(r'^## ', exp, flags=re.M)[1:]
    baselines = [b for b in blocks if b.startswith('Baseline')]
    ok = say('PREFLIGHT', bool(baselines), 'EXPERIMENTS.md Baseline block') and ok
    for b in baselines:
        missing = [f for f in ('COMMAND:', 'RESULT:')
                   if not re.search(rf'^{f}[ \t]*\S', b, re.M)]
        ok = say('PREFLIGHT', not missing, 'Baseline: ' +
                 ('missing ' + ' '.join(missing) if missing else 'complete')) and ok
    iters = [b for b in blocks if b.startswith('Iteration')]
    ok = say('PREFLIGHT', len(iters) >= 1, f'{len(iters)} iteration block(s)') and ok
    for number, b in enumerate(iters, 1):
        name = b.splitlines()[0]
        ok = say('PREFLIGHT', name == f'Iteration {number}',
                 f'{name}: expected ## Iteration {number}') and ok
        missing = [f for f in ('CHANGE:', 'WHY:', 'RESULT:', 'DECISION:')
                   if not re.search(rf'^{f}[ \t]*\S', b, re.M)]
        ok = say('PREFLIGHT', not missing, f"{name}: {'complete' if not missing else 'missing ' + ' '.join(missing)}") and ok
        decisions = re.findall(r'^DECISION:(.*)$', b, re.M)
        ok = say('PREFLIGHT', bool(decisions) and all(d.strip() in ('keep', 'revert') for d in decisions),
                 f'{name}: DECISION must be keep or revert') and ok
    ok = guards(loop_dir, expect) and ok
    ok = checks(loop_dir) and ok
    print("PREFLIGHT: ALL OK - ready for the verifier" if ok else "PREFLIGHT: FAILED - fix before spawning the verifier")
    return ok


def verdict_names(run_dir):
    names = [f for f in os.listdir(run_dir) if re.fullmatch(r"VERDICT-[0-9]+\.md", f)]
    return sorted(names, key=lambda f: (int(f[8:-3]), f))


def read_verdict(run_dir):
    """Return the highest-numbered verdict and its last non-empty line's result."""
    names = verdict_names(run_dir)
    if not names:
        return None, None
    with open(os.path.join(run_dir, names[-1]), encoding="utf-8") as f:
        lines = [line.strip() for line in f.read().splitlines() if line.strip()]
    if any(re.match(r"^\W*(GUARDS|C\d+)\W*:\s*FAIL", line) for line in lines):
        return names[-1], "FAIL"
    overall = "PASS" if lines and re.match(r"^\W*OVERALL:\s*PASS\W*$", lines[-1]) else None
    return names[-1], overall


def cmd_finish(run_dir, status, note, expect=None):
    p = os.path.join(os.path.abspath(run_dir), "STATE.json")
    if status not in ("pass", "stopped", "failed") or not os.path.isfile(p):
        print("FINISH: FAIL - usage: finish <run_dir> pass --expect <digest> [note]; "
              "finish <run_dir> {stopped|failed} [note]")
        return 2
    st = read_state(p)
    if st["status"] in ("pass", "stopped", "failed"):
        same = st["status"] == status
        say("FINISH", same, "run already finished: " + st["status"])
        return 0 if same else 1
    if status == "pass":
        if not expect:
            say("FINISH", False, "pass requires --expect <digest>; STATE.json unchanged")
            return 1
        run = os.path.dirname(p)
        name, overall = read_verdict(run)
        why = None
        if name is None:
            why = "no VERDICT-NN.md in the run directory (save the verifier's reply first)"
        elif overall == "FAIL":
            why = f"{name}: verdict contains a FAIL line"
        elif overall != "PASS":
            why = f"{name} does not end with 'OVERALL: PASS'"
        else:
            try:
                if not preflight(run, expect):
                    why = "preflight failed after the verdict (see failed part above)"
            except (OSError, ValueError) as e:
                why = "preflight failed: " + " ".join(str(e).splitlines())
        if why:
            print(f"FINISH: FAIL - pass refused: {why}. STATE.json unchanged.")
            return 1
    st.update({"status": status, "finished_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
               "note": note,
               "verdicts": verdict_names(os.path.dirname(p))})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
    print(f"FINISH: OK - status={status}")
    return 0


def dispatch(a):
    if len(a) == 5 and a[0] == "init" and a[3] == "--request-file":
        return cmd_init(a[1], a[2], a[4])
    if len(a) == 2 and a[0] == "freeze":
        return cmd_freeze(a[1])
    if a and a[0] == "guards" and (len(a) == 2 or (len(a) == 4 and a[2] == "--expect")):
        return 0 if guards(a[1], a[3] if len(a) == 4 else None) else 1
    if len(a) == 2 and a[0] == "checks":
        return 0 if checks(a[1]) else 1
    if a and a[0] == "preflight" and (len(a) == 2 or (len(a) == 4 and a[2] == "--expect")):
        return 0 if preflight(a[1], a[3] if len(a) == 4 else None) else 1
    if len(a) >= 3 and a[0] == "finish":
        if len(a) >= 4 and a[3] == "--expect":
            if len(a) < 5:
                say("FINISH", False, "--expect requires a digest")
                return 2
            return cmd_finish(a[1], a[2], " ".join(a[5:]) or None, a[4])
        return cmd_finish(a[1], a[2], " ".join(a[3:]) or None)
    print(__doc__)
    return 2


def main():
    a = sys.argv[1:]
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            result = dispatch(a)
    except Exception as e:
        say(a[0].upper() if a else "USAGE", False, " ".join(str(e).splitlines()))
        return 2
    print(output.getvalue(), end="")
    return result


if __name__ == "__main__":
    sys.exit(main())
