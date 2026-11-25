"""h_top_band_genus_bound_to_display を確かめる: 上の帯の類の成分は、元の書き方に結びついているか。

仮説（exp.yaml）: {v_lower, from: syntax.display, to: spread_dimension}。
  読み（#815 から）: 上位 256 次元（top）を同じ大きさの雑音に置き換えると、元の語（orig）の G_rate は 0.857（eq）から 0.743 に下がり、
  書き替えた語（swap・mixed）はほとんど動かなかった。top の類の成分は、元の書き方のときにだけ働く、という読み。

系列: #364、#779、#788、#799、#802、#806、#808、#812、#815。

手順:
  #806 と同じく、元の 120 語と書き替えの 120 語を mixed（240 語）で中心化し、次元ごとの標準偏差で top（上位 256 次元）と
  low（残り 1280 次元）に分ける（層ごと）。
  帯ごとに、類の語（5 類 × 8 語）について、最も近い重心で類を当てる（余弦）。
    acc_orig: 元の語を、元の語から作った類の重心で当てる。重心は、その語を除いた 7 語で作る（1 つ抜き）。
    acc_swap: 書き替えた語を、元の語から作った類の重心で当てる。重心は、その語の元の形を除いた 7 語で作る。
    drop = acc_orig − acc_swap（書き替えで、元の書き方の重心へ寄らなくなる分）。
  記録: 帯ごと、層ごとの acc_orig・acc_swap・drop と、t = drop(top) − drop(low)。
判定（事前に決める。L8 だけで）:
  支持: t ≥ 0.1（top の類の成分は、low より書き替えに移らない）。
  反証: t ≤ 0（top の類の成分は、low と同じかそれ以上に書き替えに移る）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #806 の top だけの読みで、L8 の G_rate が orig 0.593、swap 0.179 だったこと、low だけで orig 0.871、swap 0.279 だったことを知っている。
    中点の帰属の値で、最も近い重心で当てる値ではない。この手順の値はどの帯でもまだ見ていない。
  - 当てずっぽうの率は 0.2（5 類）。
使い方:
  python exp/experiments/geo_top_band_genus_transfer.py
  出力: exp/experiments/results/geo_top_band_genus_transfer.json
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_top_band_genus_transfer.json"
K = 256


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def nearest(x, cents):
    sims = {k: float(torch.nn.functional.cosine_similarity(x, c, dim=0)) for k, c in cents.items()}
    return max(sims, key=sims.get)


def accuracy(Xo, Xs, genus):
    hit_o, hit_s, n = 0, 0, 0
    for k, ix in genus.items():
        for i in ix:
            cents = {kk: Xo[[j for j in jx if j != i]].mean(0) for kk, jx in genus.items()}
            hit_o += nearest(Xo[i], cents) == k
            hit_s += nearest(Xs[i], cents) == k
            n += 1
    return hit_o / n, hit_s / n


def main():
    g = module("geo_cross_genus_midpoint")
    s = module("geo_genus_region_immune_display")
    sets = {**g.GENUS, **g.CROSS}
    base = [w for ws in sets.values() for w in ws] + g.FILLER
    n = len(base)
    SWAP = s.SWAP
    vec = g.vectors(base + [SWAP[w] for w in base])
    idx = {w: i for i, w in enumerate(base)}
    genus = {k: [idx[w] for w in ws] for k, ws in g.GENUS.items()}
    res = {"layers": {}}
    for L in g.LAYERS:
        Rm = torch.cat([torch.stack([vec[L][w] for w in base]), torch.stack([vec[L][SWAP[w]] for w in base])])
        Cm = Rm - Rm.mean(0, keepdim=True)
        order = torch.argsort(Cm.std(0), descending=True)
        row = {}
        for b, dims in (("top", order[:K]), ("low", order[K:])):
            X = Cm[:, dims]
            ao, as_ = accuracy(X[:n], X[n:], genus)
            row[b] = {"acc_orig": ao, "acc_swap": as_, "drop": ao - as_}
        row["diff"] = {k: row["top"][k] - row["low"][k] for k in row["top"]}
        print(L, json.dumps(row), flush=True)
        res["layers"][str(L)] = row
    t = res["layers"][str(g.JUDGE)]["diff"]["drop"]
    v = "supported" if t >= 0.1 else "refuted" if t <= 0 else "not_judged"
    res["judgment"] = {"t": t, "top_band_genus_bound_to_display": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
