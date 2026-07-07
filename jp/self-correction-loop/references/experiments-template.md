<!-- テンプレート。このファイルを <workspace>/.loop/EXPERIMENTS.md にコピーし、
     <山括弧のプレースホルダ> だけを置換する。iteration ごとに
     "## Iteration N" ブロックを 1 つ追記する — 過去のブロックを書き換えたり
     削除したりしない。フィールド名は書いてあるとおりに保つ
     (CHANGE:/WHY:/RESULT:/DECISION:) — scripts/preflight.sh がチェックする。
     コピーからはこのようなコメントをすべて削除すること。 -->
# EXPERIMENTS

## Baseline
COMMAND: <RUBRIC.md の中核 CHECK コマンド>
RESULT: <何も変更する前の、その verbatim な出力行>

## Iteration 1
CHANGE: <この iteration で変えた 1 つのこと>
WHY: <この変更に期待する効果>
RESULT: <変更後の計測結果。verbatim な出力行>
DECISION: <keep | revert>
