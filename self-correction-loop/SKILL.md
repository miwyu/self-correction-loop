---
name: self-correction-loop
description: >
  Run a rubric-driven self-correction loop: iterate on a task, grade each
  attempt with an independent verifier sub-agent, and keep going until every
  criterion passes. Use this whenever the user explicitly asks to loop,
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
  the final verdict and the baseline-to-final improvement.
- **Budget:** if the user gave an iteration or time budget, honor it. If not,
  and several consecutive iterations (including at least one structural bet)
  show no progress, stop and report the best result so far, the experiment
  log, and what you'd try next with more budget.

Never claim success without a passing verifier verdict from this session.
