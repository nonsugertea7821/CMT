#!/bin/bash
# 定義と適用の両方を教師にした概念ベクトルを、層を変えて学習し、
# 「適用する」側（e3 の評価）と「定義する」側（e6）を測る。
cd "$(dirname "$0")"
PY=${PY:-python}
M=Qwen/Qwen2.5-1.5B-Instruct
for L in "$@"; do
  $PY -u e3_concept_vectors.py --model $M --layer $L --steps 30 --objective defqa --tag _defqa > results/e3_defqa_L$L.log 2>&1
  $PY -u e6_cross_use.py --model $M --layer $L --tag _defqa_L$L \
      --vectors results/e3_Qwen2.5-1.5B-Instruct_L${L}_defqa.pt > results/e6_defqa_L$L.log 2>&1
done
