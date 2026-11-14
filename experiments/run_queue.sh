#!/bin/bash
# 実行待ちの実験を順に回す。
cd "$(dirname "$0")"
export PY=${PY:-python}
$PY -u e7_dilution.py --model Qwen/Qwen3-4B --dtype bfloat16 --set b --groups G2c > results/e7b_4b.log 2>&1
./run_layers.sh 14 4 20
