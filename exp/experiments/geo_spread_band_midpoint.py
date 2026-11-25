"""h_genus_below_spread_band を確かめる: 類の成分は、ばらつきの大きな帯より下の次元にあるか。

仮説（exp.yaml）: {v_lower, from: magnitude, to: midpoint_membership}。
  読み（#802 から）: ばらつきの上位 256 次元の大きな帯が余弦を引きずり、類の成分はそれより下の次元に散っている。
  #802 で、上位 256 次元を 257 番目の大きさまで縮めると、書き替えた語の帰属が上がった（L8 lift 0.093）。

系列:
  #364（geo_cross_genus_midpoint）、#779（geo_genus_region_immune_display）、#788（geo_rogue_dimension_midpoint）、
  #799（geo_spread_dimension_midpoint）、#802（geo_spread_profile_midpoint）。

手順:
  読みと条件（orig・swap・mixed、各条件で中心化）とばらつきの順位は #802 と同じ（240 語の mixed で、層ごと）。
  読み方:
    base: そのまま。
    comp: 上位 256 次元を s_257 の大きさまで縮める（#802 の comp_256 と同じ。一致を記録する）。
    low: 上位 256 次元を 0 にし、下の 1280 次元だけを残す。
    top: 下の 1280 次元を 0 にし、上位 256 次元だけを残す（縮めない）。
  lift(x) = ((G(swap, x) − G(swap, base)) + (G(mixed, x) − G(mixed, base))) / 2。
判定（事前に決める。L8 だけで）:
  支持: lift(low) ≥ 0.05 かつ lift(top) < lift(low)（下の帯だけで、もとより帰属が上がり、上の帯だけよりも高い）。
  反証: lift(low) < 0（下の帯だけでは、もとより帰属が下がる）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #802 の comp_256 の値（L8 swap 0.279、mixed 0.571）を知っている。
  - #799 で、上位 16 次元を 0 にしても上がらなかった（lift −0.018）。low は 256 次元を捨てるので、それとは量が違う。
  - low と top の値はまだどれも見ていない。
  - 上位 256 次元は、中心化した分散の多くを占めるはず（割合を記録する）。low はその分を捨てる。
使い方:
  python exp/experiments/geo_spread_band_midpoint.py
  出力: exp/experiments/results/geo_spread_band_midpoint.json
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
OUT = ROOT / "exp/experiments/results/geo_spread_band_midpoint.json"
K = 256
READS = ["base", "comp", "low", "top"]


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
        info = {"top_var_share": float(var[top].sum() / var.sum()), "s_at": float(sd[order[K]])}

        def mats(rd):
            out = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = (R - R.mean(0, keepdim=True)).clone()
                if rd == "comp":
                    scale = torch.ones_like(sd)
                    scale[top] = sd[order[K]] / sd[top]
                    X = X * scale
                elif rd == "low":
                    X[:, top] = 0
                elif rd == "top":
                    X[:, low] = 0
                out[c] = X
            return out

        row = {"band": info}
        for rd in READS:
            M = mats(rd)
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
                    Rr = mean([f(ws) for ws in rsets])
                    r[c].update(R_rate=Rr, holds=1 if G - Rr >= 0.15 else 0)
            row[rd] = r
            print(L, rd, json.dumps(r), flush=True)
        print(L, json.dumps(info), flush=True)
        res["layers"][str(L)] = row
    j = res["layers"][str(g.JUDGE)]

    def lift(rd):
        return ((j[rd]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
                + (j[rd]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2

    lifts = {rd: lift(rd) for rd in READS[1:]}
    v = ("supported" if lifts["low"] >= 0.05 and lifts["top"] < lifts["low"]
         else "refuted" if lifts["low"] < 0 else "not_judged")
    res["judgment"] = {"lift": lifts, "genus_below_spread_band": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
