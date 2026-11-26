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

## Why a separate rubric author, and why the rubric is frozen

A worker that writes its own rubric decides what it will be graded on while
already holding a plan for the work; criteria drift toward what the plan
happens to satisfy. A rubric author in a fresh context sees only the user's
request and the workspace, runs every CHECK once so broken checks surface
before any work depends on them, and then freezes: `loop_guard.py freeze`
records the sha256 of RUBRIC.md, of the request text, and of every protected
file in FREEZE.json. "The test file was not modified" is uncheckable as
prose; a recorded hash turns it into a mechanical comparison.

## Why two references live outside the run records

Everything under `.loop/` is writable by the worker, so hashes stored there
only catch accidents: a worker could edit a test and rewrite the recorded
hash to match. Two references are out of its quiet reach. A protected file
that matches a committed git blob is checked against that commit, not against
FREEZE.json. And the digest of FREEZE.json itself is never stored in the run:
it exists in the rubric author's reply, and the verifier compares against it
with `guards --expect`. Rewriting the records then requires an explicit lie
in a verbatim prompt, which the session transcript shows.

A protected file with no committed counterpart is reported as unanchored
rather than failed: workspaces outside git are legitimate. The verifier names
such files, and reads the diff when a file differs from HEAD.

What this does not stop: a worker that passes a false digest to the verifier,
one that rewrites git objects, or — outside git — one that edits a protected
file before the rubric author ever runs. The first two leave evidence; the
third is why the author is spawned before any work.

## Why expected outputs stay out of the rubric

Copying a scorer's case table into RUBRIC.md puts a lookup table one step from
the solution and biases the verifier toward checking the copy instead of
running the scorer. The rubric records commands and required results, never
the test data itself.

## Why preflight before the verifier, and why CHECKs run without a shell

A verifier run spent on an attempt that visibly fails its own CHECK commands
is a wasted sub-agent. The mechanical gate (records exist, formats parse,
guards hold, every CHECK passes) filters those out; the verifier then adds
what a script cannot — skeptical judgment on MANUAL criteria and on whether
the rubric covers the request. CHECKs run as plain argument lists: a shell
would let `|| true` or a pipe to a lenient filter turn a failure into exit 0,
and worker and verifier would each quote the line differently. `EXPECT:`
covers the common need to match output.

## Why the verdict is saved and `finish` is a gate

A verdict that lives only in the conversation cannot be audited later, and
"the verifier passed it" is easy to say about an earlier attempt. The reply
is saved verbatim as VERDICT-NN.md, and `finish pass` refuses unless the
newest one ends with `OVERALL: PASS` and the guards still hold — the verifier
has tool access too, so the guards are re-checked after it.

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
