# Design rationale

Why the loop is shaped the way it is. Read this when you want the reasoning;
SKILL.md deliberately carries only the procedure.

## Why an independent verifier

After working on something you are anchored on your intentions rather than on
the artifact, so self-critique tends to pass work that isn't done. A verifier
sub-agent with a fresh context reads only the rubric and the artifacts — never
your reasoning — so its judgment reflects what is actually there. This is also
why the verifier prompt is a verbatim template: every paraphrase is a chance
to smuggle in your interpretation of a criterion (measured on weaker models:
rewritten prompts dropped the overall-PASS rule in 3/8 runs and weakened a
guard criterion in 1/8), and why you never pass the verifier a summary of
what you did.

## Why guards carry sha256 anchors

"The test file was not modified" is uncheckable as prose: with nothing to
compare against, verifiers fall back to weak proxies ("no skip markers, looks
normal") and pass them. Recording the hash before work starts turns the guard
into a mechanical comparison — `check_guards.sh` either matches or it doesn't.
Guards exist because the loop's pressure to pass is exactly the pressure that
produces test edits, scorer tweaks, and hardcoded expected outputs; naming
protected files up front is what keeps the shortcut visible.

## Why expected outputs stay out of the rubric

Copying a scorer's case table into RUBRIC.md puts a lookup table one step from
the solution and biases the verifier toward checking the copy instead of
running the scorer. The rubric records commands and required results, never
the test data itself.

## Why preflight before the verifier

A verifier run spent on an attempt that visibly fails its own CHECK commands
is a wasted sub-agent. The mechanical gate (artifacts exist, formats parse,
guards hold, every CHECK exits 0) filters those out; the verifier then adds
what a script cannot — skeptical judgment on MANUAL criteria and independent
re-execution.

## Why one change per iteration

If you change several things and the score moves, you don't know why, so the
experiment log stops accumulating knowledge. Scalar tweaks flatten out
quickly; the 3-iterations-without-improvement threshold forces the switch to
a structural bet (different algorithm, different representation) instead of
letting the loop grind on dead tuning.

## Why a worktree, and why the artifacts stay untracked

The loop makes many speculative edits; a disposable worktree keeps them off
the user's branch and index entirely. Worktrees start from the committed
state — uncommitted changes do not come along — hence the dirty-state guard:
copy uncommitted target files in, or you will "fix" a stale version (the
baseline-contradiction check exists to catch exactly that). RUBRIC.md and
EXPERIMENTS.md are process artifacts, not product: they live in `.loop/`,
excluded via `.git/info/exclude` (never the user's .gitignore), so no later
merge can carry them into the user's branch. They are also the user's audit
trail — deleting them after the run destroys the only evidence of what was
tried; leave the cleanup to the user.

## Why success requires the verifier's OVERALL: PASS from this session

A stale verdict (from an earlier attempt) or a self-graded "all checks pass"
is how loops stop early. The one non-negotiable rule is that the last state
of the artifacts is what got verified.
