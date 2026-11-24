"""h_refer_ops_share_direction を確かめる: v_refer の下の動詞は、隠れ状態で一つの向きを共有するか。

仮説（exp.yaml）: {v_depend, from: hidden_state, to: [syntax.from, syntax.to]}。
  登録（92e7f2d）の読み: v_refer の下の動詞の変換は一つの向きを共有し、違いは端の種類だけ。
  ここでは前半（一つの向きを共有する）だけを測る。後半（違いは端の種類だけ）は測らない。

手順:
  モデル Qwen/Qwen2.5-1.5B-Instruct（ローカルのキャッシュ、float32、CPU）。チャットの雛形は使わない。
  動詞の集まり: cscl.yaml・cscl/library・cscl/design・exp/src の yaml から、
    行の形「  v_<名前>: {...}」で display を持つ動詞を、最初に出たものだけ拾う（実行のときの main の体系）。
    親 = extends の値（接頭辞を除く）。
  動詞 v ごとに、文字列「<display>」を通し、層 L の隠れ状態を display のトークン位置で平均する
    （geo_cross_genus_midpoint と同じ取り方）。判定に使う層は L=8。層 14、20 も記録だけする。
  全動詞の平均を引いて（中心化）、余弦を測る。
  coh(S) = S の中のすべての対の余弦の平均。
  R = 親が v_refer の動詞。C = 親が v_compose の動詞（対照として記録する。判定には使わない）。
  帰無: 全動詞から |R| 個をでたらめに選んだ集まり 2000 個（seed 0）の coh。
    null_mean = その平均、p = coh が coh(R) 以上になる割合。
判定（事前に決める。L8 だけで）:
  支持: coh(R) − null_mean ≥ 0.10 かつ p ≤ 0.05。
  そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - 表示語は式から訳した名前で、v_refer の下には「述べる」を含むものがあり（v_presume、v_state、v_metric_of）、
    v_compose の下には「部分になる」を含むものが多い。語の重なりだけでまとまる見込みがある。
    そのため「述べる」を含むものを除いた R でも coh と p を記録する（記録だけ。判定には使わない）。
  - 動詞の数と顔ぶれは、実行のときの体系で決まる（登録のときに数えると、v_refer の下は 15、v_compose の下は 10、全 90）。
  - 測るのは表示語の隠れ状態で、文の中で動詞が端を変換するところは測らない。
使い方:
  python exp/experiments/geo_refer_ops_share_direction.py
  出力: exp/experiments/results/geo_refer_ops_share_direction.json
"""
import glob
import itertools
import json
import os
import random
import re
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_refer_ops_share_direction.json"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LAYERS = [8, 14, 20]
JUDGE = 8
N_NULL = 2000


def collect():
    files = [ROOT / "cscl.yaml"]
    for pat in ("cscl/library/**/*.yaml", "cscl/design/*.yaml", "exp/src/*.yaml"):
        files += sorted(Path(p) for p in glob.glob(str(ROOT / pat), recursive=True))
    verbs = {}
    for f in files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^  (v_[a-z_0-9]+): (\{.*\})\s*$", line)
            if not m or m.group(1) in verbs:
                continue
            try:
                d = yaml.safe_load(m.group(2))
            except yaml.YAMLError:
                continue
            if isinstance(d, dict) and isinstance(d.get("display"), str):
                verbs[m.group(1)] = {"display": d["display"], "parent": str(d.get("extends", "")).split(".")[-1]}
    return verbs


def vectors(texts):
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
    model.eval()
    p = len(tok("「", add_special_tokens=False)["input_ids"])
    out = {L: [] for L in LAYERS}
    with torch.no_grad():
        for t in texts:
            q = len(tok("「" + t, add_special_tokens=False)["input_ids"])
            ids = tok("「" + t + "」", return_tensors="pt", add_special_tokens=False)
            hs = model(**ids, output_hidden_states=True).hidden_states
            for L in LAYERS:
                out[L].append(hs[L][0, p:q].mean(0))
    return {L: torch.stack(v) for L, v in out.items()}


def coh(X, idx):
    return sum(float(X[a] @ X[b]) for a, b in itertools.combinations(idx, 2)) / (len(idx) * (len(idx) - 1) / 2)


def stats(X, idx, n, rng):
    c = coh(X, idx)
    null = [coh(X, rng.sample(range(n), len(idx))) for _ in range(N_NULL)]
    return {"coh": c, "null_mean": sum(null) / N_NULL, "p": sum(x >= c for x in null) / N_NULL}


def main():
    verbs = collect()
    names = list(verbs)
    V = vectors([verbs[k]["display"] for k in names])
    R = [i for i, k in enumerate(names) if verbs[k]["parent"] == "v_refer"]
    C = [i for i, k in enumerate(names) if verbs[k]["parent"] == "v_compose"]
    R_lex = [i for i in R if "述べる" not in verbs[names[i]]["display"]]
    res = {"verbs": verbs, "R": [names[i] for i in R], "C": [names[i] for i in C],
           "R_without_noberu": [names[i] for i in R_lex], "layers": {}}
    for L in LAYERS:
        X = V[L] - V[L].mean(0)
        X = X / X.norm(dim=1, keepdim=True)
        res["layers"][str(L)] = {key: stats(X, idx, len(names), random.Random(0))
                                 for key, idx in (("R", R), ("C", C), ("R_without_noberu", R_lex))}
    j = res["layers"][str(JUDGE)]["R"]
    res["judgment"] = {"diff": j["coh"] - j["null_mean"], "p": j["p"],
                       "refer_ops_share_direction": "supported" if j["coh"] - j["null_mean"] >= 0.10 and j["p"] <= 0.05 else "refuted"}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({L: res["layers"][L] for L in res["layers"]}, indent=1))
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
