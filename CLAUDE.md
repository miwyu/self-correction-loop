# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A skill-development project for the **self-correction-loop** Claude Code skill
([self-correction-loop/SKILL.md](self-correction-loop/SKILL.md)): a rubric-driven
iterate-until-verified loop (isolate work in a disposable worktree → write
checkable rubric with anti-gaming guards → baseline → one change per iteration
with an experiment log → independent verifier sub-agent → stop only on a
passing verdict). The skill is developed
with the skill-creator plugin's eval loop: run test prompts with and without
the skill, grade against assertions, review in a browser viewer, revise,
repeat.

## Layout

- `self-correction-loop/` — the skill itself; the product of this repo.
  `SKILL.md` (numbered steps + MUST/NEVER rules + thresholds, ~145 lines),
  `references/` (verbatim templates: rubric, experiments log, verifier
  prompt; plus `rationale.md` holding the design "why"), and `scripts/`
  (`check_guards.sh` — sha256 verification of protected files;
  `preflight.sh` — format + guards + CHECK-command gate run before the
  verifier). `jp/self-correction-loop/` is its Japanese mirror: every skill
  change lands in both trees in the same commit, kept in exact structural
  sync (same heading/bullet skeleton; scripts code-identical with translated
  comments; the verifier-prompt body stays English because its verdict
  format is parsed — verify with a structural diff before committing).
- `evals/evals.json` — 4 test cases with prompts and assertions; input
  fixtures live in `evals/files/<eval-name>/`. Assertions cover task success,
  anti-gaming guards (fixture files byte-identical, no hardcoded answers,
  generalizes to unseen inputs), and process checks (loop artifacts exist in
  whichever workspace the run used: outputs dir, `.loop/`, or a worktree).
  `dirty-state-fix` is a regression guard for the skill's Step 0: its
  `setup.sh` commits an old v1 and leaves the buggy current v2 uncommitted;
  version-marker assertions catch a fix made against stale HEAD.
- `self-correction-loop-workspace/` (gitignored, regenerable) — eval run
  results, one `iteration-N/` per skill revision. Headline benchmark numbers
  are preserved in commit messages instead.

## Running the eval loop

Follow the skill-creator skill's process. Repo-specific details:

- For each eval, spawn a with-skill and a baseline subagent in the same turn;
  each copies its fixtures from `evals/files/<eval-name>/` into
  `iteration-N/eval-<id>-<name>/<config>/outputs/` and works there
  (`config` = `with_skill` | `without_skill`).
- Save `timing.json` from each task notification immediately; it can't be
  recovered later.
- Most assertions are scripted: `self-correction-loop-workspace/grade_checks.py`
  checks all 8 runs programmatically (pytest, scorer, byte-identity diffs,
  generalization probes, dirty-state version markers, git-status pollution).
  README/doc criteria need inspection. Write results to `grading.json` per
  run (fields: `text`, `passed`, `evidence`).
- Subagents cannot use EnterWorktree (cwd-override error), so with-skill runs
  take the skill's `.loop/` fallback on evals 0–2 and exercise a real worktree
  only inside eval-3's own fixture repo. Fallback runs may append `.loop/` to
  this repo's `.git/info/exclude` — remove that line after grading, and check
  `git worktree list` / `git branch` for strays left by runs.
- **Dual layout requirement**: the viewer (`generate_review.py`) wants
  `outputs/` + `grading.json` at the config level with `eval_metadata.json`
  in the eval dir; the aggregator (`scripts.aggregate_benchmark`) wants
  `eval-*` dir names containing `<config>/run-1/{grading.json,timing.json}`.
  Satisfy both: name eval dirs `eval-<id>-<name>` and copy grading.json +
  timing.json into a `run-1/` subdir of each config dir.
- Aggregate and view (skill-creator plugin paths):
  ```bash
  cd ~/.claude/plugins/cache/claude-plugins-official/skill-creator/unknown/skills/skill-creator
  python3 -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name self-correction-loop
  python3 eval-viewer/generate_review.py <workspace>/iteration-N \
    --skill-name self-correction-loop --benchmark <workspace>/iteration-N/benchmark.json
  ```
  For iteration 2+, pass `--previous-workspace <workspace>/iteration-<N-1>`.

Quick fixture sanity checks: `python3 -m pytest test_intervals.py -q` in the
fix-failing-tests fixture dir (5 of 13 must fail on the pristine fixture);
`python3 score.py` in hillclimb-slugify (exits 1 until solved). For
dirty-state-fix, copy the fixture elsewhere first (`setup.sh` creates a git
repo — never run it in the pristine dir), then after `sh setup.sh` HEAD/v1
must fail only the bulk-discount test and the uncommitted v2 only the
rounding test.

## Commit conventions

- One commit per skill iteration, after user review: prefix `skill:`, body
  states what feedback drove the change and the before/after benchmark
  numbers (e.g. "with-skill 100% vs baseline 78.6%").
- Eval changes that alter what's being measured get their own `evals:` commit,
  never folded into a skill commit — otherwise benchmark deltas across
  iterations are uninterpretable.
- Commit straight to `main`.

## Sonnet optimization round (2026-07, branch tuning/sonnet-robustness)

The skill was restructured for weaker executors, measured headless with
`claude -p --model {claude-fable-5,claude-sonnet-5} --effort high`:
mechanical rules moved into `scripts/`, formats into verbatim `references/`
templates, guards anchored by sha256 recorded before work starts, a
preflight gate before the verifier, and a hardened trigger description.
Headline (4 evals × N=3, all-assertion pass rate): current skill — fable
100% / sonnet 92.1% (4/12 undertriggered runs, 4 unverified success claims,
1 deleted `.loop/`); revised — sonnet 100%, unverified-success 0, verifier
exactly 1/run, fable 100% (no regression). Cost: sonnet wall median 110s →
160s; the +10% speed target was not met — the added turns are the price of
the compliance gains. The harness lives in
`self-correction-loop-workspace/sonnet-opt/` (`bin/run_one.sh` spawns
per-run isolated `claude -p` sessions **outside this repo** so Step 0
doesn't worktree the repo itself; `grade_run.py` / `analyze_transcript.py`
/ `check_r1_r2.py` score assertions, Q2/verifier counts, and template
compliance). The subagent-based eval protocol above still works for
fable-side iteration.

## Known eval caveats (as of the sonnet-optimization round)

- Task success is 100% in every measured config; what discriminates is
  process compliance (artifacts left, triggering, verified-before-claiming).
- `hillclimb-slugify` and `dirty-state-fix` are one-shottable — which makes
  them the *undertrigger* probes: a model that skips the skill still solves
  them but leaves no artifacts and claims success unverified (baseline
  sonnet did exactly this 4/12 times).
- `rubric-readme`'s prompt itself demands independent verification, so it
  measures artifact-leaving, not verification behavior.
- Sonnet triggering stays probabilistic even with the hardened description:
  12/12 in the final full measurement but 11/12 in an intermediate revision
  — treat ~1-in-12 undertrigger as residual risk N=3 evals may miss.
- The former open item (unanchored guard criteria) is closed: Protected
  files carry sha256 anchors recorded pre-work, checked mechanically by
  `check_guards.sh` from worker, preflight, and verifier alike.
