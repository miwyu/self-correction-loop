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
confirms every criterion. The procedure is below; the reasoning behind each
rule is in `references/rationale.md` (read it when curious, not to run the loop).

`<skill_dir>` = the directory containing this SKILL.md.
`<ws>` = the workspace root chosen in Step 0. `<ws>/.loop/` holds all loop
artifacts. Run every CHECK command from `<ws>`.

## MUST / NEVER

- **MUST M1:** claim success only after, in this session, `preflight.sh`
  exited 0 **and then** a verifier sub-agent's report ended `OVERALL: PASS`
  — in that order, both against the current state of the artifacts.
- **MUST M2:** copy the three templates in `<skill_dir>/references/`
  verbatim; replace only their placeholders.
- **MUST M3:** change one thing per iteration, and log every iteration in
  `EXPERIMENTS.md` before moving on.
- **NEVER N1:** modify a file listed under `## Protected files` in RUBRIC.md.
- **NEVER N2:** delete or "clean up" `.loop/`, RUBRIC.md, or EXPERIMENTS.md —
  they are the user's audit trail; the user removes them after review.
- **NEVER N3:** copy expected outputs, test cases, or scorer internals into
  RUBRIC.md or into the solution.
- **NEVER N4:** paraphrase, extend, or summarize-into the verifier prompt.
- **NEVER N5:** `git init` a repo the user didn't ask for, or commit to the
  user's branch.
- **NEVER N6:** re-run rubric checks or re-inspect artifacts after the
  verifier returns `OVERALL: PASS` — the verdict is final and already in your
  context. The only tool use allowed after PASS is the git commands Step 5's
  hand-back itself needs (diff summary, status check), nothing else.

## Step 0: Choose the workspace

1. If the cwd is **not** a git repository (or worktree isolation is
   impossible/too heavy — e.g. heavy env setup a fresh checkout can't rerun):
   `<ws>` = cwd. Skip to Step 1.
2. If the cwd **is** a git repository: work in a disposable worktree — via
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

## Step 1: Set up the loop workspace (before any work on the task)

1. One command block (if `.loop/` already exists, stop and report instead;
   skip the exclude line outside a git repo):
   ```bash
   test ! -e <ws>/.loop && mkdir -p <ws>/.loop \
     && cp -R <skill_dir>/scripts <ws>/.loop/scripts \
     && echo '.loop/' >> "$(git -C <ws> rev-parse --path-format=absolute --git-common-dir)/info/exclude" \
     ; shasum -a 256 <ws>/<each protected file>
   ```
2. Read `<skill_dir>/references/rubric-template.md` and
   `<skill_dir>/references/experiments-template.md` (both, now); create
   `<ws>/.loop/RUBRIC.md` and `<ws>/.loop/EXPERIMENTS.md` from them.
   Criteria must be objectively checkable; put the user's stated command
   verbatim in a CHECK line. Add guard criteria for the ways the goal could
   be gamed (test edits, scorer edits, hardcoded outputs): list each such
   file under `## Protected files` with the sha256 recorded in step 1 —
   **before any work**. Keep every CHECK a one-line command (pipe to
   `grep -q`/`diff` as needed); if a check can't be one line, make it a
   MANUAL criterion instead — do not write helper checker files. The loop's
   only files are RUBRIC.md, EXPERIMENTS.md, and the copied `scripts/`.

## Step 2: Baseline

Run the core CHECK command once before changing anything; record the verbatim
result under `## Baseline` in EXPERIMENTS.md. The baseline is what later
results are compared against, and what you reconcile in Step 0's guard.

## Step 3: Iterate

Per iteration:

1. Change **one** thing (M3) — the change you expect to help most.
2. Run the relevant CHECK commands yourself (cheap, no sub-agent).
3. Append an `## Iteration N` block to EXPERIMENTS.md
   (CHANGE / WHY / RESULT / DECISION — the template fixes the fields).
4. In a worktree: commit the iteration — only files the task is supposed to
   change (`.loop/` is excluded and stays untracked).

**Plateau rule:** if the metric has not improved for 3 consecutive
iterations, the next iteration must be a structural change (different
algorithm, representation, or framing), not another tweak. **Budget:** honor
any user-given iteration/time budget; with none, stop and report after 3
consecutive non-improving iterations that already include a structural
change.

## Step 4: Preflight, then verify

1. Run `bash <ws>/.loop/scripts/preflight.sh <ws>/.loop`.
   Exit 0 required; on failure, fix and return to Step 3. Do not spawn a
   verifier while preflight fails.
2. Read `<skill_dir>/references/verifier-prompt.md`. Replace `{{LOOP_DIR}}`
   with the absolute path of `<ws>/.loop` — the only edit allowed (N4) — and
   spawn a verifier sub-agent (Agent tool) with that text. Never include your
   summary, diff, or reasoning.
3. Last line `OVERALL: PASS` → Step 5. Any FAIL → treat its evidence as the
   next iteration's input and return to Step 3. Don't re-grade or argue with
   the verdict; if a criterion itself seems wrong rather than unmet, surface
   that to the user instead of dropping it.

## Step 5: Report

The verifier's PASS is final — do not re-run checks or re-inspect files after
it; write the report and stop.

- **Success** (M1 satisfied): report the verifier's verdict, baseline → final
  result, and iterations used.
  - Worktree mode: hand back the fix only — branch name, diff summary, exact
    landing steps (merge, or `git checkout <branch> -- <files>`). Prescribing
    is the default; apply it yourself only when losing user work is provably
    impossible (clean checkout, or the diff contains the user's uncommitted
    content), and say which you did. Give cleanup commands for after review:
    `git worktree remove --force <path>` (the `--force` deletes the untracked
    `.loop/`), then delete the branch.
  - Fallback mode: note in one line that `<ws>/.loop/` remains (rubric +
    experiment log) and how to remove it. Do not remove it yourself (N2).
- **Budget exhausted / stopped:** report best-so-far, the experiment log, and
  what you'd try next. Leave the workspace in place — worktree included —
  and report its path.
