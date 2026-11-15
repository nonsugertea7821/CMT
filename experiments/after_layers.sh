#!/bin/bash
# run_layers.sh が終わるのを待って、E10 と E11 を順に走らせる
cd "$(dirname "$0")"
PY=${PY:-python}
while pgrep -f run_layers.sh > /dev/null; do sleep 60; done
$PY e10_expression_given.py --model Qwen/Qwen2.5-1.5B-Instruct > results/e10.log 2>&1
$PY e11_expression_scratchpad.py --model Qwen/Qwen2.5-1.5B-Instruct > results/e11.log 2>&1
$PY e3_concept_vectors.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8 --objective defqa --def-source expr --tag _exprdefqa > results/e3_exprdefqa_L8.log 2>&1
