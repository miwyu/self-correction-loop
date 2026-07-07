#!/bin/bash
# Verify the protected files recorded in RUBRIC.md against their sha256 anchors.
#
# Usage: check_guards.sh <loop_dir>
#   <loop_dir> contains RUBRIC.md; protected-file paths are relative to the
#   workspace root (the parent of <loop_dir>).
#
# Exit 0  = every protected file exists and matches its recorded hash.
# Exit 1  = a file is missing or its hash differs (details on stdout).
# Exit 2  = usage error or RUBRIC.md has no parseable Protected files section.
set -u

LOOP_DIR="${1:-}"
[ -n "$LOOP_DIR" ] && [ -f "$LOOP_DIR/RUBRIC.md" ] || { echo "GUARDS: FAIL - usage: check_guards.sh <loop_dir with RUBRIC.md>"; exit 2; }
WS="$(cd "$LOOP_DIR/.." && pwd)"

if command -v sha256sum >/dev/null 2>&1; then
  HASH() { sha256sum "$1" | awk '{print $1}'; }
else
  HASH() { shasum -a 256 "$1" | awk '{print $1}'; }
fi

# Lines like "- path/to/file sha256=<64 hex>" inside "## Protected files".
LINES=$(awk '/^## Protected files/{flag=1; next} /^## /{flag=0} flag && /^- /' "$LOOP_DIR/RUBRIC.md")
PARSED=0
FAILED=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  if [ "$line" = "- (none)" ]; then
    echo "GUARDS: OK - no protected files declared"
    PARSED=$((PARSED+1)); continue
  fi
  path=$(echo "$line" | sed -E 's/^- +([^ ]+) +sha256=[0-9a-fA-F]{64}.*$/\1/')
  want=$(echo "$line" | sed -E 's/^.*sha256=([0-9a-fA-F]{64}).*$/\1/')
  if [ "$path" = "$line" ] || [ "$want" = "$line" ]; then
    echo "GUARDS: FAIL - unparseable protected-file line: $line"
    FAILED=1; continue
  fi
  PARSED=$((PARSED+1))
  if [ ! -f "$WS/$path" ]; then
    echo "GUARDS: FAIL - protected file missing: $path"
    FAILED=1; continue
  fi
  got=$(HASH "$WS/$path")
  if [ "$got" = "$want" ]; then
    echo "GUARDS: OK - $path unchanged (sha256 match)"
  else
    echo "GUARDS: FAIL - $path was modified (sha256 $got != recorded $want)"
    FAILED=1
  fi
done <<EOF
$LINES
EOF

if [ "$PARSED" -eq 0 ] && [ "$FAILED" -eq 0 ]; then
  echo "GUARDS: FAIL - no protected-file lines found in $LOOP_DIR/RUBRIC.md"
  exit 2
fi
[ "$FAILED" -eq 0 ] && { echo "GUARDS: ALL OK ($PARSED files)"; exit 0; }
exit 1
