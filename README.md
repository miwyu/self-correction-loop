**English** | [日本語](README.jp.md)

# self-correction-loop

A Claude Code skill that structures work as a **self-correction loop**: keep
iterating on a task until an **independent verifier** — not the model that did
the work — confirms that every success criterion is met.

## Why

Two observations about working with current models motivate the design:

1. **Models improve reliably when they can hillclimb on feedback.** Given a
   checkable goal (a test suite, a scorer, a rubric), a model can run, measure,
   adjust, and run again — and this loop outperforms one-shot prompting on
   hard tasks.
2. **Models grade their own work poorly.** After working on something, the
   model is anchored on its intentions rather than the artifact, so
   self-critique tends to declare victory early. Grading in a _separate
   context window_ — a verifier sub-agent that sees only the rubric and the
   artifacts, never the worker's reasoning — is markedly more reliable.

The skill packages both ideas into a repeatable procedure, plus guard rails
against the failure mode that loops invite: gaming the metric (weakening
tests, editing the scorer, hardcoding expected outputs). The worker never
writes its own finish line: a separate rubric author does, and the result is
frozen before work starts. Work also stays out
of your checkout: the loop runs in a disposable git worktree (with a
dirty-state guard for uncommitted changes), falling back to a `.loop/`
directory where worktrees aren't possible.

## When to use it

Use it when a task has a **measurable definition of done** and is unlikely to
be solved in one attempt:

- "Loop on this until all the tests pass."
- "Hillclimb on this benchmark / scorer until it reports 100."
- "Iterate on this document until it satisfies the rubric."

It is _not_ useful for one-shot tasks or tasks with no checkable goal — the
loop's overhead (two extra sub-agents: about 3–5 minutes on tasks a bare
model finishes in 1–2) only pays off when there is something objective to
converge on.

## How the loop works

```
┌──────────────────────────────────────────────────────────┐
│ 0. ISOLATE    Work in a disposable git worktree — or a   │
│               .loop/ dir when worktrees aren't possible  │
│               — so the loop never dirties your checkout  │
├──────────────────────────────────────────────────────────┤
│ 1. RUBRIC     A separate rubric-author sub-agent writes  │
│               the CHECK commands and protected files,    │
│               then freezes them. The worker never edits  │
├──────────────────────────────────────────────────────────┤
│ 2. BASELINE   One honest attempt; record the starting    │
│               measurement in EXPERIMENTS.md              │
├──────────────────────────────────────────────────────────┤
│ 3. ITERATE    Change ONE thing → run the cheap checks →  │
│   ▲           log it (CHANGE/WHY/RESULT/DECISION). No    │
│   │           improvement for 3 iterations → make a      │
│   │           structural bet instead of another tweak    │
├───┼──────────────────────────────────────────────────────┤
│ 4.│PREFLIGHT  loop_guard.py preflight must exit 0 (logs  │
│   │+ VERIFY   parse, freeze intact, every CHECK passes)  │
│   │           then spawn a fresh-context verifier from   │
│   └──────     the verbatim prompt template. Any FAIL:    │
│               its evidence feeds the next iteration      │
├──────────────────────────────────────────────────────────┤
│ 5. STOP       loop_guard.py finish closes the run: pass  │
│               only with a saved PASS verdict and intact  │
│               freeze; otherwise stopped, with the log    │
└──────────────────────────────────────────────────────────┘
```

The mechanical parts are one script, not prose: `scripts/loop_guard.py`
(Python 3 standard library only) freezes the rubric, request and protected
files, runs the CHECK commands, gates the verifier, and refuses to close a
run as passed unless the freeze is intact, every CHECK passes and a PASS
verdict is on file. It is run from the skill directory, never copied into
the workspace, so the worker cannot swap it.

The freeze is tied to two things the worker's run records cannot rewrite:
the committed git blob of each protected file, and a freeze digest that the
rubric author returns and the verifier and `finish` must be given. What this
does not stop: a worker that passes a made-up digest to the verifier, edits
made before the freeze outside git (these are disclosed as `unanchored`, not
blocked), and a hand-written verdict file — `finish` checks a verdict's
form, not who wrote it. Design rationale lives in `references/rationale.md`.

The rubric, experiment-log and role-prompt formats are verbatim templates in
`references/` (fill placeholders only).

Every run leaves an audit trail in its own directory,
`.loop/<date>-<slug>/`: `REQUEST.md`, `RUBRIC.md` (what "done" means),
`FREEZE.json`, `EXPERIMENTS.md` (every attempt and its measured result),
each verifier verdict as `VERDICT-NN.md`, and `STATE.json` — kept out of
your checkout, in the worktree's `.loop/` (excluded via
`.git/info/exclude`) or the cwd's. A second loop in the same place gets a
new run directory.
On success the report includes the branch, a diff summary, and how to merge;
on failure the worktree is left in place for inspection.

The full instructions live in
[self-correction-loop/SKILL.md](self-correction-loop/SKILL.md).

## This repository

This repo is the skill's development project, iterated with the
skill-creator eval loop (run test prompts with and without the skill, grade
against assertions, review, revise):

- `self-correction-loop/` — the skill itself
- `tests/` — unit tests for `loop_guard.py`
  (`python3 -m unittest discover -s tests`)
- `evals/` — test cases and fixtures used to benchmark it
- `self-correction-loop-workspace/` (gitignored) — generated run results

See [CLAUDE.md](CLAUDE.md) for the development workflow and benchmark
commands.
