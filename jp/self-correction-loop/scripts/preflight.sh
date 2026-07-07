#!/bin/bash
# 検証前の機械ゲート。検証者を起動する前にこれを実行する。
# preflight が失敗している状態で検証者を起動するのは、FAIL が確定している
# 試行にサブエージェントを浪費することである。
#
# 使い方: preflight.sh <loop_dir>
#   <loop_dir> は RUBRIC.md、EXPERIMENTS.md、scripts/ を含む。ワークスペース
#   ルートはその親。CHECK コマンドはワークスペースルートから実行される。
#
# Exit 0 = 成果物が存在し、書式が正しく、ガードが成立し、全 CHECK が通る。
# Exit 1 = 何かが失敗(詳細は stdout に PREFLIGHT: 接頭辞で)。
set -u

LOOP_DIR="${1:-}"
[ -n "$LOOP_DIR" ] && [ -d "$LOOP_DIR" ] || { echo "PREFLIGHT: FAIL - usage: preflight.sh <loop_dir>"; exit 1; }
LOOP_DIR="$(cd "$LOOP_DIR" && pwd)"
WS="$(cd "$LOOP_DIR/.." && pwd)"
FAILED=0
fail() { echo "PREFLIGHT: FAIL - $1"; FAILED=1; }
ok()   { echo "PREFLIGHT: OK - $1"; }

# 1. 成果物の存在(削除は NEVER — ユーザーの監査証跡である)。
for f in RUBRIC.md EXPERIMENTS.md; do
  if [ -s "$LOOP_DIR/$f" ]; then ok "$f exists"; else fail "$f missing or empty in $LOOP_DIR"; fi
done
[ "$FAILED" -eq 0 ] || exit 1

# 2. RUBRIC.md の書式: 必須の節と、少なくとも 1 つの基準。
for sec in "## Goal" "## Protected files" "## Criteria"; do
  grep -q "^$sec" "$LOOP_DIR/RUBRIC.md" && ok "RUBRIC.md has '$sec'" || fail "RUBRIC.md lacks '$sec' section"
done
NCHECK=$(grep -c '^CHECK: ' "$LOOP_DIR/RUBRIC.md" || true)
NMANUAL=$(grep -c '^MANUAL: ' "$LOOP_DIR/RUBRIC.md" || true)
if [ "$((NCHECK + NMANUAL))" -ge 1 ]; then
  ok "RUBRIC.md has $NCHECK CHECK + $NMANUAL MANUAL criteria"
else
  fail "RUBRIC.md has no 'CHECK: ' or 'MANUAL: ' criterion lines"
fi

# 3. EXPERIMENTS.md の書式: ベースライン + 少なくとも 1 つの完全な iteration ブロック。
grep -q '^## Baseline' "$LOOP_DIR/EXPERIMENTS.md" && ok "EXPERIMENTS.md has '## Baseline'" || fail "EXPERIMENTS.md lacks '## Baseline'"
NITER=$(grep -c '^## Iteration ' "$LOOP_DIR/EXPERIMENTS.md" || true)
if [ "$NITER" -ge 1 ]; then
  ok "EXPERIMENTS.md has $NITER iteration block(s)"
  for field in "CHANGE: " "RESULT: " "DECISION: "; do
    NF=$(grep -c "^$field" "$LOOP_DIR/EXPERIMENTS.md" || true)
    [ "$NF" -ge "$NITER" ] && ok "every iteration has '$field'" || fail "only $NF/$NITER iterations have a '$field' line"
  done
else
  fail "EXPERIMENTS.md has no '## Iteration N' block"
fi

# 4. ガード: 保護ファイルが未変更であること。
if bash "$LOOP_DIR/scripts/check_guards.sh" "$LOOP_DIR"; then
  ok "guards hold"
else
  fail "check_guards.sh reported a violation (see lines above)"
fi

# 5. すべての CHECK コマンドがワークスペースルートから exit 0 になること。
i=0
while IFS= read -r cmd; do
  i=$((i+1))
  if (cd "$WS" && bash -c "$cmd" >/tmp/preflight_check_$$ 2>&1); then
    ok "CHECK #$i passes: $cmd"
  else
    fail "CHECK #$i exits non-zero: $cmd -> $(tail -1 /tmp/preflight_check_$$)"
  fi
done <<EOF
$(sed -n 's/^CHECK: //p' "$LOOP_DIR/RUBRIC.md")
EOF
rm -f /tmp/preflight_check_$$

if [ "$FAILED" -eq 0 ]; then
  echo "PREFLIGHT: ALL OK - ready to spawn the verifier"
  exit 0
fi
echo "PREFLIGHT: FAILED - fix the failures above before spawning the verifier"
exit 1
