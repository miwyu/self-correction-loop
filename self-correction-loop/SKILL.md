---
name: self-correction-loop
description: >
  Required for any request phrased "loop / iterate / hillclimb / keep fixing
  / keep going until <measurable condition>" — e.g. "loop on this until the
  tests pass", "hillclimb until the score hits 20/20", "iterate until it
  satisfies the rubric" — and for any other request for verified,
  rubric-driven iteration. Runs the loop: write a rubric with mechanical
  checks, iterate with an experiment log, and claim completion only after an
  independent verifier sub-agent returns OVERALL: PASS. The trigger is the
  shape of the request ("... until <condition>"), never the task's
  difficulty: solving in one attempt does not satisfy such a request, because
  the deliverables include the rubric, the experiment log, and the
  independent verdict — do not skip this skill because the fix looks obvious.
---

# Self-Correction Loop

Loop: attempt → measure → improve, stopping only when an independent verifier
confirms every criterion. Three roles in three separate contexts: a **rubric
author** decides what "done" means and freezes it, the **worker** (you)
iterates, a **verifier** judges. You never write the rubric and never declare
success on your own. The reasoning behind each rule is in
`references/rationale.md` (read it when curious, not to run the loop).

`<skill_dir>` = the directory containing this SKILL.md.
`GUARD` = `python3 <skill_dir>/scripts/loop_guard.py` (use the absolute path).
`<ws>` = the workspace root chosen in Step 0.
`<run>` = this loop's run directory, `<ws>/.loop/<date>-<slug>`; `GUARD init`
prints it. Its files have fixed names: `STATE.json`, `REQUEST.md`,
`RUBRIC.md`, `FREEZE.json`, `EXPERIMENTS.md`, `VERDICT-01.md`, `VERDICT-02.md`, ...

## MUST / NEVER

- **MUST M1:** claim success only after, in this session and in this order:
  `GUARD preflight <run>` exited 0, **then** a verifier sub-agent's reply ended
  `OVERALL: PASS`, **then** `GUARD finish <run> pass --expect <digest>`
  exited 0. An edit to the deliverable after a verdict voids that verdict
  (and lifts N6): go back to Step 4.
- **MUST M2:** pass the two prompts in `<skill_dir>/references/role-prompts.md`
  verbatim; replace only the `{{...}}` placeholders. Never add your summary,
  diff, or reasoning.
- **MUST M3:** change one thing per iteration, and log every iteration in
  `EXPERIMENTS.md` before moving on.
- **NEVER N1:** modify `RUBRIC.md`, `REQUEST.md`, `FREEZE.json`, a
  `VERDICT-NN.md` you saved, or any file listed under `## Protected files`.
- **NEVER N2:** delete, rename or "clean up" anything under `.loop/` — it is
  the user's audit trail; the user removes it after review.
- **NEVER N3:** copy expected outputs, test cases, or scorer internals into
  the solution, and never make the solution detect that it is under test.
- **NEVER N4:** write helper or checker files. Besides the task's own
  deliverables, the only files you create are `<ws>/.loop/request.txt` and
  the `<run>` files listed above. Caches that the check commands create by
  themselves are fine.
- **NEVER N5:** `git init` a repo the user didn't ask for, or commit to the
  user's branch.
- **NEVER N6:** once you have saved a verdict ending `OVERALL: PASS`, run
  nothing except `GUARD finish` and the read-only git commands the Step 5
  report needs. (`finish` re-runs the checks itself; if it refuses, see
  Step 5.)

## Step 0: Choose the workspace

1. If the cwd is **not** a git repository (or worktree isolation is
   impossible/too heavy — e.g. heavy env setup a fresh checkout can't rerun):
   `<ws>` = cwd. Skip to Step 1.
2. If the cwd **is** a git repository — judged after any setup command the
   user told you to run first: work in a disposable worktree — via
   EnterWorktree in Claude Code, else `git worktree add ../<repo>-loop -b <branch>`
   (sibling of the repo). `<ws>` = the worktree.
   - **Dirty-state guard:** worktrees start from the committed state. Run
     `git status` first; copy any uncommitted files the task touches into the
     worktree (prefer copying over a WIP commit — it leaves the user's branch
     and index untouched).
   - Run the task's measurement command once early; a worktree is a fresh
     checkout (no `.env`, no deps). Do minimal setup, or fall back to rule 1.
   - **Baseline reconciliation:** if the Step 2 baseline contradicts the
     user's description (a test that "should fail" passes), suspect a stale
     base: inspect the original checkout's uncommitted changes.

## Step 1: Start the run and get the rubric frozen (before any work on the task)

1. Write the user's request, word for word, to `<ws>/.loop/request.txt`
   (create the `.loop` directory if it is missing).
2. Run `GUARD init <ws> <slug> --request-file <ws>/.loop/request.txt`
   (`<slug>`: lowercase words joined by `-`, at most 30 characters, e.g.
   `cart-rounding`). The first line it prints is `<run>`.
3. Read `<skill_dir>/references/role-prompts.md`. Take the **Rubric author**
   prompt, replace `{{WS}}`, `{{RUN_DIR}}`, `{{TEMPLATE}}` (absolute path of
   `<skill_dir>/references/rubric-template.md`) and `{{GUARD}}` (absolute path
   of `loop_guard.py`), and spawn a sub-agent (Agent tool) with that text.
   Do no work on the task until it replies.
4. If its reply has no `FREEZE: OK` line, fix nothing yourself: run
   `GUARD finish <run> stopped "rubric not frozen"` and report the author's
   error to the user.
5. Otherwise note the `digest=` value on the `FREEZE: OK` line; Steps 4 and 5
   need it. Run `GUARD guards <run> --expect <digest>`; exit 0 is required.
   Tell the user the digest and every `GUARDS: NOTE` line in one short message.

## Step 2: Baseline

Copy `<skill_dir>/references/experiments-template.md` to
`<run>/EXPERIMENTS.md`. Run `GUARD checks <run>` once before changing
anything and record its output lines under `## Baseline`. If every CHECK
already passes, make no change: fill `## Iteration 1` with
`CHANGE: none (baseline already passes)`, `WHY: nothing to change`,
`RESULT:` the same output, `DECISION: keep`, and go to Step 4. That block is
Iteration 1; any later change is Iteration 2.

## Step 3: Iterate

Per iteration:

1. Change **one** thing (M3) — the change you expect to help most. One thing
   = one cause: one bug, one parameter, one algorithm swap.
2. Run `GUARD checks <run>` (cheap, no sub-agent).
3. Log it in EXPERIMENTS.md (CHANGE / WHY / RESULT / DECISION): fill the
   template's `## Iteration 1` block for the first iteration, then append
   `## Iteration 2`, `## Iteration 3`, ... Leave no template placeholder or
   comment; DECISION is exactly `keep` or `revert`.
4. In a worktree: commit the iteration — only files the task is supposed to
   change (`.loop/` is excluded and stays untracked).

**Plateau rule:** if the metric has not improved for 3 consecutive
iterations, the next iteration must be a structural change (different
algorithm, representation, or framing), not another tweak. **Budget:** honor
any user-given iteration/time budget; with none, stop and report after 3
consecutive non-improving iterations that already include a structural
change.

**Impossible criterion:** if you can show that no deliverable can satisfy the
frozen criteria (two checks demand opposite results, a CHECK cannot run), do
not wait for the plateau rule and do not touch the rubric. Keep the changes
that fix real defects, log them as iterations, then go to Step 5 as
**stopped** and ask the user which criterion is right.

## Step 4: Preflight, then verify

1. Run `GUARD preflight <run>`. Exit 0 required. A failing CHECK is yours to
   fix: return to Step 3. A log format error is too: correct those lines of
   EXPERIMENTS.md, keeping what they record. A failure about RUBRIC.md,
   REQUEST.md, FREEZE.json or a protected file is not: go to Step 5 as
   **stopped**. Do not spawn a verifier while preflight fails.
2. Take the **Verifier** prompt from `role-prompts.md`, replace `{{WS}}`,
   `{{RUN_DIR}}`, `{{GUARD}}` and `{{FREEZE_DIGEST}}` (the digest from Step 1),
   and spawn a fresh sub-agent with that text (M2).
3. Save its whole reply, unchanged, as `<run>/VERDICT-NN.md` (01, 02, ...).
   A reply without an `OVERALL:` line is not a verdict: save nothing and
   spawn a fresh verifier with the same prompt, at most twice; after that go
   to Step 5 as **stopped**.
4. Last line `OVERALL: PASS` → Step 5. Any FAIL → its evidence is the next
   iteration's input; return to Step 3. Don't re-grade or argue with the
   verdict. If a FAIL says the rubric itself is wrong (`rubric gap`, a
   criterion that cannot hold), do not iterate: go to Step 5 as **stopped**
   and ask the user. A changed rubric needs a new run (Step 1) with the
   user's answer added to the request; the old run stays as it is.

## Step 5: Finish and report

Run exactly one of:

- `GUARD finish <run> pass --expect <digest>` — only after `OVERALL: PASS`.
  It re-runs preflight against the Step 1 digest and refuses unless that
  passes and the newest `VERDICT-NN.md` ends with `OVERALL: PASS`.
- `GUARD finish <run> stopped "<one-line reason>"` — budget exhausted,
  impossible criterion, or a question for the user.
- `GUARD finish <run> failed "<one-line reason>"` — the work cannot meet the
  criteria.

If `finish pass` refuses, the saved PASS no longer stands and N6 is lifted.
Read what failed: a CHECK or the log → fix it and repeat Step 4 for a new
verdict; a frozen file → `finish <run> stopped` with that reason.

Then report, and stop:

- **Success** (M1 satisfied): the verdict lines, baseline → final result,
  iterations used, the freeze digest, any `GUARDS: NOTE` lines, and `<run>`.
  - Worktree mode: hand back the fix only — branch name, diff summary, exact
    landing steps (merge, or `git checkout <branch> -- <files>`). Prescribe
    them; do not land the fix yourself. Give cleanup commands for after review:
    `git worktree remove --force <path>` (the `--force` deletes the untracked
    `.loop/`), then delete the branch.
  - Fallback mode: note in one line that `<ws>/.loop/` remains and how to
    remove it. Do not remove it yourself (N2).
- **Stopped / failed:** say first that the goal was not reached. Then
  best-so-far, what is in the experiment log, the open question or what you'd
  try next. Leave the workspace in place — worktree included — and report
  its path.
