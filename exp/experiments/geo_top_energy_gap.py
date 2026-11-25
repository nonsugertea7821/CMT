"""h_top_energy_holds_gap を確かめる: eq と low の差は、上の帯に残る大きさに従うか。

仮説（exp.yaml）: {v_depend, from: magnitude, to: midpoint_membership}。
  読み（#812・#815 から）: 上位 256 次元（top）の平方和を下の帯とそろえる eq で L8 lift 0.057、top を捨てる low で 0.111。
  top を同じ大きさの雑音にしても 0.051 で、差は向きからではない（#815、反証）。残る差は、top に残る平方和から来る、という読み。

系列: #802、#806、#808、#812、#815、#819。

手順:
  読みと条件（orig・swap・mixed、各条件で中心化）、ばらつきの順位と帯の分け方、倍率 a0 は #812 と同じ。
  読み方: base（そのまま）と、top に f・a0 を掛けたもの（f = 1, 0.7, 0.5, 0.35, 0.25, 0.1, 0）。名前は f100, f70, …, f0（f の百倍）。
    f = 1 は #812 の eq、f = 0 は low と同じ（一致を記録する）。f = 0.7 は eq_half（0.707）に近い。
  lift(f) = ((G(swap, f) − G(swap, base)) + (G(mixed, f) − G(mixed, base))) / 2。
判定（事前に決める。L8 だけで）:
  f を 1 から 0 へ減らす順に lift を並べる。
  支持: どの隣り合う段でも、lift の下がりが 0.015 を越えない（top に残る大きさが減るほど、帰属が下がらずに上がっていく）、
    かつ lift(0) − lift(1) ≥ 0.03。
  反証: ある段で lift が 0.03 以上下がる（大きさを減らして帰属が下がる段がある）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #812 の値（L8 lift: eq 0.057、eq_half 0.064、low 0.111）と #815 の noise（0.051）を知っている。f = 1 と f = 0 の値は分かっている。
  - 余弦は f について連続なので、f が 0 に近づけば lift は low に近づく。「low に近づくか」は判定に使わず、途中の段が単調かを見る。
  - 中点の帰属は語の数の比なので、段ごとの値は 1/140 ほどの刻みで揺れる。許しの 0.015 はその 2 刻みほど。
使い方:
  python exp/experiments/geo_top_energy_gap.py
  出力: exp/experiments/results/geo_top_energy_gap.json
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
OUT = ROOT / "exp/experiments/results/geo_top_energy_gap.json"
K = 256
FS = [100, 70, 50, 35, 25, 10, 0]
READS = ["base"] + [f"f{f}" for f in FS]


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
        a = {f"f{f}": a0 * f / 100 for f in FS}
        info = {"top_var_share": float(var[top].sum() / var.sum()), "a_eq": a0}

        def mats(rd):
            out = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = (R - R.mean(0, keepdim=True)).clone()
                if rd in a:
                    X[:, top] = X[:, top] * a[rd]
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
    seq = [lifts[f"f{f}"] for f in FS]
    steps = [y - x for x, y in zip(seq, seq[1:])]
    if min(steps) <= -0.03:
        v = "refuted"
    elif min(steps) >= -0.015 and seq[-1] - seq[0] >= 0.03:
        v = "supported"
    else:
        v = "not_judged"
    res["judgment"] = {"lift": lifts, "min_step": min(steps), "span": seq[-1] - seq[0], "top_energy_holds_gap": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
