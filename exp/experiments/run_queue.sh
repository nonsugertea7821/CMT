#!/bin/bash
# 実行待ちの実験を順に回す。どれも途中保存から再開できる。
# 第1引数に PID を渡すと、そのプロセスの終了を待ってから始める。
cd "$(dirname "$0")"
export PY=${PY:-python}
[ -n "$1" ] && tail --pid="$1" -f /dev/null
$PY -u e9_scratchpad.py --model Qwen/Qwen2.5-1.5B-Instruct > results/e9_15b.log 2>&1
$PY -u e9_scratchpad.py --model Qwen/Qwen3-4B --dtype bfloat16 > results/e9_4b.log 2>&1
./run_layers.sh 20 4
