"""h_midpoint_depends_model を確かめる: 上位概念の集まりと上位をまたぐ性質の集まりの差は、モデルを変えても出るか。

仮説（exp.yaml）: v_depend(midpoint_membership, model)。
  読み: 中点の検査の結果は、モデルが事前学習で得た特徴量に依存する。
  geo_cross_genus_midpoint（#353 で支持）は Qwen2.5-1.5B-Instruct だけで測った。
  系統の違うモデルで同じ手順を測り、その差（diff_GC）が同じ判定の基準を満たすかを問う。

手順（ここに書かないことは geo_cross_genus_midpoint と同じ。語の表と率の関数はそのスクリプトから読み込み、その main は走らせない）:
  モデル（どれもローカルのキャッシュ、float32、CPU、チャットの雛形なし）:
    判定に使う（Qwen と系統が違う）: llm-jp/llm-jp-3-1.8b-instruct（24 層）、sbintuitions/sarashina2.2-1b-instruct-v0.1（24 層）
    記録だけ（Qwen の系統）: Qwen/Qwen2.5-1.5B-Instruct（28 層。#353 と同じ値が出るかの確かめ）、Qwen/Qwen2.5-0.5B-Instruct（24 層）
  層: モデルの層の数 N に対する相対の深さで揃える。判定は round(N × 8/28)、記録は round(N × 14/28)・round(N × 20/28)。
    Qwen2.5-1.5B ではちょうど 8・14・20 になる。24 層のモデルでは 7・12・17。
  語の通し方: 「w を通し、「 だけの符号化の長さから「w の符号化の長さまでのトークン位置で、隠れ状態を平均する。
    結果を見る前に、4 つのモデルすべてで、120 語のどれについても「w の符号化の先頭が「 だけの符号化と一致し、w の分のトークンが 1 つ以上あることを確かめた。
  モデルごとに: G_rate・C_rate・R_rate（でたらめな 8 語 200 個、seed 0）・diff_GC・perm_p（252 通り）・precondition（G_rate − R_rate ≥ 0.15）、
    holds（precondition = 1 かつ diff_GC ≥ 0.15 かつ perm_p ≤ 0.05 なら 1。#353 の支持の基準と同じ）。
  行（geo_cross_genus_midpoint_models.json）: "model <名前>": {lineage, layers, G_rate, C_rate, R_rate, diff_GC, perm_p, precondition, holds, 層ごとの G・C}
    "summary 要約": {n_judged（判定に使うモデルのうち precondition = 1 の数）、n_hold（そのうち holds = 1 の数）、
                     diff_llmjp、diff_sarashina、diff_qwen15、diff_qwen05、verdict_support}
判定（事前に決める。判定の層だけで、系統の違う 2 つのモデルだけで）:
  n_judged = 0 なら、中点の検査がかたまりを捉えていないので、未検証のまま残す。
  n_judged ≥ 1 で、n_hold < n_judged（前提を満たすのに差が基準に届かないモデルが 1 つでもある）なら支持（モデルに依存する）。
  n_hold = n_judged なら反証（差は系統の違うモデルでも出る）。

開示（結果を見る前に分かっていること）:
  - この判定は、差が「出るか出ないか」だけを問う。差の大きさがモデルで違っても、どのモデルでも基準を超えれば反証になる。
    大きさの違いは diff_* として記録し、判定とは別に報告する。
  - Qwen3-4B もキャッシュにあるが、float32 では手元のメモリ（15GB）に載らないので使わない。
  - sarashina の語の区切りを読むため、sentencepiece と protobuf を入れた（モデルの計算には関わらない）。
  - 語の表は日本語で手で作った。日本語の学習の量はモデルで違うので、差が出ないことが「日本語に弱い」ことによる場合もある。
    それを分けるのが precondition（上位概念の集まりがでたらめより 0.15 以上まとまるか）。
使い方:
  python exp/experiments/geo_cross_genus_midpoint_models.py
"""
import importlib.util
import itertools
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_cross_genus_midpoint_models.json"
MODELS = [
    ("llmjp", "llm-jp/llm-jp-3-1.8b-instruct", "other"),
    ("sarashina", "sbintuitions/sarashina2.2-1b-instruct-v0.1", "other"),
    ("qwen15", "Qwen/Qwen2.5-1.5B-Instruct", "qwen"),
    ("qwen05", "Qwen/Qwen2.5-0.5B-Instruct", "qwen"),
]
FRACS = [8 / 28, 14 / 28, 20 / 28]


def first():
    spec = importlib.util.spec_from_file_location("geo0", ROOT / "exp/experiments/geo_cross_genus_midpoint.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def vectors(name, words):
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float32)
    model.eval()
    N = model.config.num_hidden_layers
    layers = [round(N * f) for f in FRACS]
    pre = tok("「", add_special_tokens=False)["input_ids"]
    p = len(pre)
    out = {L: {} for L in layers}
    with torch.no_grad():
        for w in words:
            ids = tok("「" + w, add_special_tokens=False, return_tensors="pt")["input_ids"]
            q = ids.shape[1]
            assert q > p and ids[0, :p].tolist() == pre, w
            hs = model(ids, output_hidden_states=True).hidden_states
            for L in layers:
                out[L][w] = hs[L][0, p:q].mean(0)
    del model
    return layers, out


def mean(xs):
    return sum(xs) / len(xs)


def main():
    g = first()
    sets = {**{k: ("G", v) for k, v in g.GENUS.items()}, **{k: ("C", v) for k, v in g.CROSS.items()}}
    vocab = [w for _, ws in sets.values() for w in ws] + g.FILLER
    assert len(vocab) == len(set(vocab)) == 120
    idx = {w: i for i, w in enumerate(vocab)}
    names = list(sets)
    splits = list(itertools.combinations(names, 5))
    rows = {}
    for key, name, lineage in MODELS:
        layers, vec = vectors(name, vocab)
        J = layers[0]
        rates = {}
        for L in layers:
            X = torch.stack([vec[L][w] for w in vocab])
            X = X - X.mean(0, keepdim=True)
            rates[L] = {k: g.rate(ws, vocab, X, idx) for k, (_, ws) in sets.items()}
            if L == J:
                XJ = X
        G = mean([rates[J][k] for k in g.GENUS])
        C = mean([rates[J][k] for k in g.CROSS])
        rng = random.Random(0)
        R = mean([g.rate(rng.sample(vocab, 8), vocab, XJ, idx) for _ in range(200)])
        obs = G - C
        ge = sum(1 for s in splits
                 if mean([rates[J][k] for k in s]) - mean([rates[J][k] for k in names if k not in s]) >= obs - 1e-12)
        perm_p = ge / len(splits)
        pre = 1 if G - R >= 0.15 else 0
        row = {"lineage": lineage, "model": name, "layers": layers, "G_rate": G, "C_rate": C, "R_rate": R,
               "diff_GC": obs, "perm_p": perm_p, "precondition": pre,
               "holds": 1 if pre and obs >= 0.15 and perm_p <= 0.05 else 0}
        for L in layers[1:]:
            row[f"G_rate_L{L}"] = mean([rates[L][k] for k in g.GENUS])
            row[f"C_rate_L{L}"] = mean([rates[L][k] for k in g.CROSS])
        rows[f"model {key}"] = row
        print(key, json.dumps(row, ensure_ascii=False), flush=True)
    judged = [r for r in rows.values() if r["lineage"] == "other" and r["precondition"]]
    s = {"n_judged": len(judged), "n_hold": sum(r["holds"] for r in judged)}
    for key, _, _ in MODELS:
        s[f"diff_{key}"] = rows[f"model {key}"]["diff_GC"]
    s["verdict_support"] = 1 if judged and s["n_hold"] < s["n_judged"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
