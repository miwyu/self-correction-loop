<!-- TEMPLATE. Copy this file to <workspace>/.loop/RUBRIC.md, then replace only
     the <angle-bracket placeholders> and add/remove criterion blocks. Do not
     rename the section headings, and do not change the "CHECK: " / "MANUAL: " /
     "- <path> sha256=" line formats — scripts/preflight.sh and the verifier
     parse them. Delete every comment like this one from the copy. -->
# RUBRIC

## Goal
<one sentence: what the user asked for, with the measurable finish line>

## Protected files
<!-- Every file the goal forbids changing (test files, scorer scripts, fixture
     data). One line per file, path relative to the workspace root, hash from:
       shasum -a 256 <file>   (or sha256sum <file>)
     recorded BEFORE any work starts. If the goal protects nothing, write
     exactly one line: "- (none)".
     NEVER copy expected outputs, test cases, or scorer internals from these
     files into this rubric — record only paths and hashes. -->
- <path> sha256=<64-hex-digest>

## Criteria
<!-- One "### C<n>:" block per criterion, numbered C1, C2, ...
     CHECK: one shell command, run from the workspace root, that exits 0 if and
     only if the criterion holds. If the signal is in the output rather than
     the exit code, make it the exit code, e.g.:
       CHECK: python3 score.py | grep -q 'SCORE: 20/20'
       CHECK: python3 -m pytest test_foo.py -q
     Copy the user's stated command verbatim into the CHECK where one exists.
     MANUAL: only for criteria no command can decide; phrase it as a yes/no
     question a fresh reader can answer from the artifacts alone. -->
### C1: <short name>
CHECK: <command>

### C2: <short name>
MANUAL: <yes/no question>
