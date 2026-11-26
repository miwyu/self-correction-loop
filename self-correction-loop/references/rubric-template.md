<!-- TEMPLATE. Write <run_dir>/RUBRIC.md from this file: replace only the
     <angle-bracket placeholders> and add/remove criterion blocks. Keep the
     section headings and the "- <path>", "### C<n>:", "CHECK: ", "EXPECT: ",
     "MANUAL: " line formats — loop_guard.py parses them. Delete every comment
     like this one from the copy. -->
# RUBRIC

## Goal
<one sentence: what the user asked for, with the measurable finish line>

## Protected files
<!-- Every file the goal forbids changing or that defines success (test files,
     scorer scripts, fixture data, the user's own rubric). One line per file,
     path relative to the workspace root, no hash — `loop_guard.py freeze`
     records the hashes. If the goal protects nothing, write exactly one line:
     "- (none)". NEVER copy expected outputs, test cases, or scorer internals
     from these files into this rubric. -->
- <path>

## Criteria
<!-- One "### C<n>:" block per criterion, numbered C1, C2, ...
     CHECK: one command, run from the workspace root WITHOUT a shell: pipes,
     redirects, globs, `&&`, `||` and $VARS are not interpreted. It passes
     when it exits 0 and every EXPECT substring appears in its output.
       CHECK: python3 -m pytest test_foo.py -q
       CHECK: python3 score.py
       EXPECT: SCORE: 20/20
       CHECK: python3 -c "from foo import f; assert f(3) == 9"
     Copy the user's stated command verbatim into a CHECK when it is a plain
     command (no pipe, redirect or `NAME=value` prefix).
     MANUAL: only for criteria no command can decide; phrase it as a yes/no
     question a fresh reader can answer from the artifacts alone. -->
### C1: <short name>
CHECK: <command>
EXPECT: <substring that must appear in the output; delete this line if the exit code decides>

### C2: <short name>
MANUAL: <yes/no question>
