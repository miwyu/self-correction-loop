# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A skill-development project for the **self-correction-loop** Claude Code skill
([self-correction-loop/SKILL.md](self-correction-loop/SKILL.md)): a rubric-driven
iterate-until-verified loop (write checkable rubric with anti-gaming guards →
baseline → one change per iteration with an experiment log → independent
verifier sub-agent → stop only on a passing verdict). The skill is developed
with the skill-creator plugin's eval loop: run test prompts with and without
the skill, grade against assertions, review in a browser viewer, revise,
repeat. `local/` (gitignored) holds the reference article the skill is based on.

## Layout

- `self-correction-loop/SKILL.md` — the skill itself; the product of this repo.
- `evals/evals.json` — 3 test cases with prompts and assertions; input
  fixtures live in `evals/files/<eval-name>/`. Assertions cover task success,
  anti-gaming guards (fixture files byte-identical, no hardcoded answers,
  generalizes to unseen inputs), and one process check (loop artifacts exist).
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
  checks all 6 runs programmatically (pytest, scorer, byte-identity diffs,
  generalization probes). README/doc criteria need inspection. Write results
  to `grading.json` per run (fields: `text`, `passed`, `evidence`).
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
`python3 score.py` in hillclimb-slugify (exits 1 until solved).

## Commit conventions

- One commit per skill iteration, after user review: prefix `skill:`, body
  states what feedback drove the change and the before/after benchmark
  numbers (e.g. "with-skill 100% vs baseline 78.6%").
- Eval changes that alter what's being measured get their own `evals:` commit,
  never folded into a skill commit — otherwise benchmark deltas across
  iterations are uninterpretable.
- Commit straight to `main`.

## Known eval caveats (iteration 1)

- Task success was 100% in both configs; the measured skill value is process
  artifacts (RUBRIC.md, EXPERIMENTS.md, verifier verdict), at ~2.4× wall time.
- `hillclimb-slugify` was one-shot by the baseline — too easy to exercise
  actual hillclimbing.
- `rubric-readme`'s prompt itself demands independent verification, so it
  measures artifact-leaving, not verification behavior.
