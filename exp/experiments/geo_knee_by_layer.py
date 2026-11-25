"""h_knee_moves_with_layer を確かめる: lift が頭打ちになる倍率は、層によって動くか。

仮説（exp.yaml）: {v_depend, from: magnitude, to: layer}。
  読み（#827 から）: 上の帯に f・a0 を掛けたときの lift は、三つの層とも f ≤ 25 で横ばい。曲がる位置は L8 で 35〜50%、
  L14・L20 で 25% 前後に見えた。

系列: #812、#815、#822、#827。

手順:
  読みと条件、帯の分け方、倍率 a0、段（f = 100, 80, 60, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0）は #827 と同じ。
  層を 11 にふやす: L = 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24。
  層ごとに lift_L(f)、span_L = lift_L(0) − lift_L(100)。
  曲がる位置 knee_L: span_L ≥ 0.03 の層で、f を 100 から下げていき、はじめて lift_L(f) − lift_L(100) ≥ 0.75・span_L になる f。
  span_L < 0.03 の層は knee なし（数えない）。
判定（事前に決める）:
  knee のある層が 6 未満: 判定しない。
  幅 = max knee − min knee、rho = 層の順と knee の順位相関（Spearman、同順位は平均順位）。
  支持: 幅 ≥ 20、かつ |rho| ≥ 0.6（曲がる位置が、層の順に一方向へ動く）。
  反証: 幅 ≤ 10（曲がる位置が、層によらず段の 1〜2 刻みに収まる）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #827 の L8・L14・L20 の値を知っている。この定義での knee は、L8 で 50、L14 で 30、L20 で 30 になる。
    新しい情報は、ほかの 8 つの層。
  - 定義の 0.75 は #827 の判定と同じ値。
  - 中点の帰属は語の数の比なので、lift は 1/140 ほどの刻みで揺れる。span が小さい層ほど knee は揺れやすい。
使い方:
  python exp/experiments/geo_knee_by_layer.py
  出力: exp/experiments/results/geo_knee_by_layer.json
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
OUT = ROOT / "exp/experiments/results/geo_knee_by_layer.json"
K = 256
LAYERS = [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
FS = [100, 80, 60, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
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
    g.LAYERS = LAYERS
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
    per = {}
    for L in LAYERS:
        j = res["layers"][str(L)]
        lifts = {rd: ((j[rd]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
                      + (j[rd]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2 for rd in READS[1:]}
        span = lifts["f0"] - lifts["f100"]
        knee = None
        if span >= 0.03:
            knee = next(f for f in FS if lifts[f"f{f}"] - lifts["f100"] >= 0.75 * span)
        per[str(L)] = {"lift": lifts, "span": span, "knee": knee}
    pts = [(L, per[str(L)]["knee"]) for L in LAYERS if per[str(L)]["knee"] is not None]

    def ranks(xs):
        srt = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(xs):
            k = i
            while k + 1 < len(xs) and xs[srt[k + 1]] == xs[srt[i]]:
                k += 1
            for t in range(i, k + 1):
                r[srt[t]] = (i + k) / 2
            i = k + 1
        return r

    def pearson(x, y):
        mx, my = mean(x), mean(y)
        sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
        sx = sum((a - mx) ** 2 for a in x) ** 0.5
        sy = sum((b - my) ** 2 for b in y) ** 0.5
        return sxy / (sx * sy) if sx > 0 and sy > 0 else 0.0

    n = len(pts)
    width = (max(k for _, k in pts) - min(k for _, k in pts)) if pts else None
    rho = pearson(ranks([L for L, _ in pts]), ranks([k for _, k in pts])) if n >= 2 else None
    if n < 6:
        v = "not_judged"
    elif width >= 20 and abs(rho) >= 0.6:
        v = "supported"
    elif width <= 10:
        v = "refuted"
    else:
        v = "not_judged"
    res["judgment"] = {"layers": per, "n_knee": n, "width": width, "rho": rho, "knee_moves_with_layer": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
