#!/bin/bash
# 実行待ちの実験を順に回す。どれも途中保存から再開できる。
cd "$(dirname "$0")"
export PY=${PY:-python}
$PY -u e8_multilayer.py --model Qwen/Qwen2.5-1.5B-Instruct --layers 2-13 --decay 0.001 > results/e8_L2-13.log 2>&1
./run_layers.sh 20 4
