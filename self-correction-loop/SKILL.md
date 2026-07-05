---
name: self-correction-loop
description: >
  Run a rubric-driven self-correction loop: iterate on a task, check each
  attempt against a measurable rubric, and claim completion only after an
  independent verifier sub-agent confirms every criterion passes. Use this
  whenever the user explicitly asks to loop,
  iterate, or hillclimb until something is done — e.g. "loop on this until
  the tests pass", "keep iterating until the score hits 100", "hillclimb on
  this benchmark", "iterate until it satisfies the rubric" — or otherwise
  asks for verified, rubric-driven iteration toward a measurable goal.
---

# Self-Correction Loop

Structure the work as a loop: attempt → measure → improve → repeat, and stop
only when an **independent verifier** confirms every criterion is satisfied.

Why the independence matters: after working on something, you are anchored on
your intentions rather than on the artifact itself, so self-critique tends to
pass work that isn't actually done. A verifier sub-agent with a fresh context
window reads only the rubric and the artifacts — never your reasoning — so its
judgment reflects what is actually there.

## Step 0: Isolate the workspace

If the cwd is a git repository, do the loop's work in a disposable worktree —
via EnterWorktree in Claude Code, or `git worktree add` from the CLI if that
tool isn't available (place CLI worktrees as a sibling of the repo, e.g.
`../<repo>-loop`). Use the fallback below only when worktree isolation
itself is impossible or too heavy, not merely because one tool is missing.

- **Dirty-state guard (required):** worktrees start from the committed state;
  uncommitted changes do not come along. Check `git status` before entering —
  prefer copying uncommitted target files into the worktree (it leaves the
  user's branch and index untouched); a WIP commit also works but changes
  their branch state, so reach for it only when a copy won't do.
- **Baseline reconciliation (required):** if the Step 2 baseline contradicts
  the user's description (a test that "should fail" passes), suspect a stale
  base first: inspect the original checkout's uncommitted changes.
- A worktree is a fresh checkout — no `.env`, no dependencies. Run the
  measurement command once early; do minimal setup for environment failures,
  and fall back if setup is too heavy.
- **Fallback** (no git / heavy environment / no worktree support): keep every
  loop artifact (RUBRIC.md, EXPERIMENTS.md) in `.loop/` under the cwd; in a
  git repo add `.loop/` to `.git/info/exclude`, never the user's .gitignore.
  If `.loop/` already exists, don't overwrite it — report it, then decide.
  In fallback mode, later steps read through this: `.loop/` is where
  Step 1's rubric lives, and the `EXPERIMENTS.md` entry stands in for
  Step 3's per-iteration commit — never `git init` a repo the user
  didn't ask for.

## Step 1: Write the rubric before doing any work

Turn the user's goal into a rubric file, `RUBRIC.md`, in the working
directory. Every criterion must be objectively checkable — by running a
command or by inspecting an artifact. A vague criterion ("code is clean")
gives the verifier nothing to check and lets the loop stop early.

- If the goal already comes with a checkable signal (a test suite, a scorer
  script, a lint command), that command is the core of the rubric. Record the
  exact command and the required result.
- Add **guard criteria** for the ways the goal could be satisfied by gaming
  rather than solving: "the test files were not modified", "the scorer script
  was not edited", "no expected outputs are hardcoded". The loop's pressure to
  pass is exactly the pressure that produces these shortcuts, so name them
  up front.
- If part of the goal is genuinely qualitative, phrase it so a fresh reader
  can answer yes/no from the artifact alone (e.g. "every CLI flag that appears
  in `--help` has a description in the README").

## Step 2: Establish a baseline

Make one honest first attempt, then run the measurable check and record the
result. The baseline tells you whether later changes are actually
improvements, and it tells the user what the starting point was.

## Step 3: Iterate

Each iteration:

1. **Change one thing.** Pick the idea you expect to help most. If you change
   several things at once and the score moves, you won't know why.
2. **Run the cheap checks yourself** (the test command, the scorer). Don't
   spend a verifier run on an attempt you can already see failing.
3. **Log the experiment** in `EXPERIMENTS.md`: what you tried, why, the
   measured result, and keep/revert. The log prevents repeating failed
   experiments and is the user's window into the run.
4. **Commit the iteration.** In the worktree, one iteration is one commit;
   the commit message summarizes that iteration's `EXPERIMENTS.md` entry.
   Commit only files the task is supposed to change — `RUBRIC.md` and
   `EXPERIMENTS.md` are process artifacts; keep them untracked so no later
   merge can carry them into the user's branch.

When choosing what to try next: scalar tweaks (adjust a constant, rename,
reorder) are cheap but flatten out quickly. When progress plateaus, make a
structural bet — a different algorithm, a different representation, a
reframing of the problem — even if it temporarily regresses the score. A
plateau on the log is the signal to switch from tuning to restructuring.

## Step 4: Verify independently

When you believe every criterion passes, spawn a verifier sub-agent with the
Agent tool. Give it only the rubric and the paths to the artifacts — not your
summary of what you did or why it should pass. A useful template:

> Read the rubric at `<path>/RUBRIC.md`. For each criterion, check the actual
> artifacts in `<path>` (run commands where the criterion specifies one) and
> return a verdict: PASS or FAIL per criterion, each with one line of
> concrete evidence (command output, file content, line numbers). Be
> skeptical: your job is to find the criterion that does NOT hold. Do not
> modify any files. End with an overall verdict: PASS only if every
> criterion passed.

If the verifier fails a criterion, treat its evidence as the next iteration's
input and return to Step 3. Don't argue with the verdict or re-grade it
yourself — if a criterion seems genuinely wrong rather than unmet, surface
that to the user instead of quietly dropping it.

## Step 5: Stop

- **Success:** the verifier passes every criterion. Report the result with
  the final verdict and the baseline-to-final improvement. If the work
  happened in a worktree, hand back the fix only: report the branch name, a
  summary of the diff, and the exact steps to land the product changes
  (merge the branch, or `git checkout <branch> -- <files>`). Prescribing
  those steps is the default; apply the fix yourself only when losing user
  work is provably impossible — the checkout is clean, or a diff shows the
  user's uncommitted content is contained in what you apply — and say which
  of the two you did. Give the user the cleanup commands to run once they
  have reviewed the log: `git worktree remove --force <path>` (the
  `--force` is expected — it is what deletes the untracked process
  artifacts), then delete the branch. Never claim success without giving
  the user a landing path — the fix already applied, or the branch plus
  exact landing steps — and never let process artifacts ride along into
  the user's checkout.
- **Budget:** if the user gave an iteration or time budget, honor it. If not,
  and several consecutive iterations (including at least one structural bet)
  show no progress, stop and report the best result so far, the experiment
  log, and what you'd try next with more budget. On failure or budget
  exhaustion, leave the worktree in place — don't delete it — and report
  its path.

In fallback mode, add one line noting that `.loop/` remains and how to
remove it.

Never claim success without a passing verifier verdict from this session.
