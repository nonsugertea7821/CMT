"""h_top_band_direction_lowers_midpoint を確かめる: 上の帯の向き（中身）そのものが、中点の帰属を下げるか。

仮説（exp.yaml）: {v_lower, from: spread_dimension, to: midpoint_membership}。
  読み（#812 から）: 上位 256 次元（top）の平方和を残り（low）とそろえる eq で L8 lift 0.057、
  さらに半分にする eq_half で 0.064、top を捨てる low で 0.111。平方和をそろえても low に届かないのは、
  top の向きそのものが帰属を引き下げているから、という読み。

系列: #364、#779、#788、#799、#802、#806、#808、#812。

訂正（登録の PR #813 の本文の案から）:
  #813 では「top の中を無作為に回す・次元を入れ替える」案を書いた。これは直交変換で、語どうしの余弦を変えないので、
  何も測れない。代わりに、top を同じ大きさの雑音に置き換え、向きの中身だけを消す。

手順:
  読みと条件（orig・swap・mixed、各条件で中心化）、ばらつきの順位と帯の分け方、倍率 a（eq）は #812 と同じ。
  読み方:
    base: そのまま。
    low: top を 0 にする（#806・#812 と同じ。一致を記録する）。
    eq: top に a を掛ける（#812 と同じ。一致を記録する）。
    noise: top を、語ごとに独立な正規の雑音に置き換える。次元ごとの標準偏差は、その条件で中心化した top の列の標準偏差に a を掛けたもの。
      雑音は列ごとに中心化する。平方和は eq とほぼ同じで、語ごとの向きの中身だけがない。
      種を 0, 1, 2 の 3 つで作り、G_rate・C_rate・R_rate は 3 つの平均をとる。
  lift(x) = ((G(swap, x) − G(swap, base)) + (G(mixed, x) − G(mixed, base))) / 2。
判定（事前に決める。L8 だけで）:
  d = lift(noise) − lift(eq)。
  支持: d ≥ 0.03（中身のない同じ大きさの雑音のほうが、top の中身より帰属を下げない。top の向きが帰属を引き下げている）。
  反証: d ≤ 0（top の中身は、同じ大きさの雑音より帰属を下げない）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #812 の値（L8 lift: low 0.111、eq 0.057、eq_half 0.064、a 0.611）を知っている。
  - noise の値はまだ見ていない。
  - 雑音は類の語どうしの余弦にも無作為な揺れを足すので、top の中身が帰属に中立でも、noise は eq より下がりうる。
    だから d ≤ 0 は「中身が害をしない」とまでは言えず、「同じ大きさの雑音より害が小さい」までを言う。
使い方:
  python exp/experiments/geo_top_band_noise_midpoint.py
  出力: exp/experiments/results/geo_top_band_noise_midpoint.json
"""
import importlib.util
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_top_band_noise_midpoint.json"
K = 256
READS = ["base", "low", "eq", "noise"]
SEEDS = [0, 1, 2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def main():
    g = module("geo_cross_genus_midpoint")
    s = module("geo_genus_region_immune_display")
    sets = {**{k: ("G", v) for k, v in g.GENUS.items()}, **{k: ("C", v) for k, v in g.CROSS.items()}}
    base = [w for _, ws in sets.values() for w in ws] + g.FILLER
    SWAP = s.SWAP
    vec = g.vectors(base + [SWAP[w] for w in base])
    mixed_vocab = [("o", w) for w in base] + [("s", w) for w in base]
    form = {k: i for i, k in enumerate(mixed_vocab)}
    idx = {w: i for i, w in enumerate(base)}
    rng = random.Random(0)
    rsets = [rng.sample(base, 8) for _ in range(200)]
    res = {"layers": {}}
    for L in g.LAYERS:
        Ro = torch.stack([vec[L][w] for w in base])
        Rs = torch.stack([vec[L][SWAP[w]] for w in base])
        Rm = torch.cat([Ro, Rs])
        Cm = Rm - Rm.mean(0, keepdim=True)
        sd = Cm.std(0)
        order = torch.argsort(sd, descending=True)
        top, low = order[:K], order[K:]
        var = Cm.pow(2).sum(0)
        a0 = float((var[low].sum() / var[top].sum()).sqrt())
        info = {"top_var_share": float(var[top].sum() / var.sum()), "a_eq": a0}

        def mats(rd, seed=0):
            out = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = (R - R.mean(0, keepdim=True)).clone()
                if rd == "low":
                    X[:, top] = 0
                elif rd == "eq":
                    X[:, top] = X[:, top] * a0
                elif rd == "noise":
                    gen = torch.Generator().manual_seed(seed * 1000 + L * 10 + len(c))
                    Z = torch.randn(X.shape[0], len(top), generator=gen, dtype=X.dtype)
                    Z = Z - Z.mean(0, keepdim=True)
                    Z = Z / Z.std(0, keepdim=True) * X[:, top].std(0, keepdim=True) * a0
                    X[:, top] = Z
                out[c] = X
            return out

        row = {"band": info}
        for rd in READS:
            per = []
            for seed in (SEEDS if rd == "noise" else [0]):
                M = mats(rd, seed)
                conds = {
                    "orig": (lambda ws, X=M["orig"]: g.rate(ws, base, X, idx)),
                    "swap": (lambda ws, X=M["swap"]: g.rate(ws, base, X, idx)),
                    "mixed": (lambda ws, X=M["mixed"]: s.mixed_rate(ws, mixed_vocab, X, form)),
                }
                r = {}
                for c, f in conds.items():
                    G = mean([f(ws) for k, (_, ws) in sets.items() if k in g.GENUS])
                    C = mean([f(ws) for k, (_, ws) in sets.items() if k in g.CROSS])
                    r[c] = {"G_rate": G, "C_rate": C}
                    if L == g.JUDGE:
                        r[c]["R_rate"] = mean([f(ws) for ws in rsets])
                per.append(r)
            r = {c: {k: mean([p[c][k] for p in per]) for k in per[0][c]} for c in per[0]}
            if L == g.JUDGE:
                for c in r:
                    r[c]["holds"] = 1 if r[c]["G_rate"] - r[c]["R_rate"] >= 0.15 else 0
            if rd == "noise":
                r["seeds"] = {str(sd): {c: p[c]["G_rate"] for c in p} for sd, p in zip(SEEDS, per)}
            row[rd] = r
            print(L, rd, json.dumps(r), flush=True)
        print(L, json.dumps(info), flush=True)
        res["layers"][str(L)] = row
    j = res["layers"][str(g.JUDGE)]

    def lift(rd):
        return ((j[rd]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
                + (j[rd]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2

    lifts = {rd: lift(rd) for rd in READS[1:]}
    d = lifts["noise"] - lifts["eq"]
    v = "supported" if d >= 0.03 else "refuted" if d <= 0 else "not_judged"
    res["judgment"] = {"lift": lifts, "d": d, "top_band_direction_lowers_midpoint": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
