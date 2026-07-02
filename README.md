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
tests, editing the scorer, hardcoding expected outputs). Work also stays out
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
loop's overhead (roughly 2–4× wall time in our benchmarks, mostly the
verifier sub-agent) only pays off when there is something objective to
converge on.

## How the loop works

```
┌──────────────────────────────────────────────────────────┐
│ 0. ISOLATE   Work in a disposable git worktree — or a    │
│              .loop/ dir when worktrees aren't possible   │
│              — so the loop never dirties your checkout   │
├──────────────────────────────────────────────────────────┤
│ 1. RUBRIC    Turn the goal into RUBRIC.md: objectively   │
│              checkable criteria + anti-gaming guards     │
│              ("tests not modified", "scorer untouched")  │
├──────────────────────────────────────────────────────────┤
│ 2. BASELINE  One honest attempt; record the starting     │
│              measurement                                 │
├──────────────────────────────────────────────────────────┤
│ 3. ITERATE   Change ONE thing → run the cheap checks →   │
│   ▲          log it in EXPERIMENTS.md (what/why/result/  │
│   │          keep-or-revert). When tuning plateaus,      │
│   │          make a structural bet instead               │
├───┼──────────────────────────────────────────────────────┤
│ 4.│VERIFY    Spawn a fresh-context verifier sub-agent    │
│   │          given ONLY the rubric + artifact paths.     │
│   └──────    Any FAIL: its evidence feeds the next       │
│              iteration                                   │
├──────────────────────────────────────────────────────────┤
│ 5. STOP      Only on a passing verifier verdict — or on  │
│              an explicit budget, reporting best-so-far   │
│              and the experiment log                      │
└──────────────────────────────────────────────────────────┘
```

Every run leaves an audit trail: `RUBRIC.md` (what "done" means, including
the guards) and `EXPERIMENTS.md` (every attempt and its measured result),
alongside the verifier's per-criterion verdict — kept out of your checkout,
in the worktree (committed once per iteration) or in `.loop/`. On success
the report includes the branch, a diff summary, and how to merge; on
failure the worktree is left in place for inspection.

The full instructions live in
[self-correction-loop/SKILL.md](self-correction-loop/SKILL.md).

## This repository

This repo is the skill's development project, iterated with the
skill-creator eval loop (run test prompts with and without the skill, grade
against assertions, review, revise):

- `self-correction-loop/` — the skill itself
- `evals/` — test cases and fixtures used to benchmark it
- `self-correction-loop-workspace/` (gitignored) — generated run results

See [CLAUDE.md](CLAUDE.md) for the development workflow and benchmark
commands.
