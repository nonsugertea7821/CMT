"""h_partial_top_beats_removal を確かめる: 上の帯を途中まで縮めたほうが、捨てきるより中点の帰属が上がるか。

仮説（exp.yaml）: {v_raise, from: magnitude, to: midpoint_membership}。
  読み（#830 から）: 11 の層のうち 6 つで lift(f35) > lift(f0)。差は 0.01〜0.04 ほどで、語の対の数で決まる刻みに近い。

系列: #812、#815、#822、#827、#830。

手順:
  読みと条件、帯の分け方、倍率 a0、段、層は #830 と同じ（L = 4, 6, …, 24、f = 100, 80, …, 0）。
  #830 との違いは、平均にする前の当たりを残すこと。類（5）ごとの語の対（28）ごとに、swap と mixed の当たり（0 か 1）を持つ。
  対の差 d = (hit_swap(f35) − hit_swap(f0) + hit_mixed(f35) − hit_mixed(f0)) / 2。
  D_L = 140 の対での d の平均（= #830 の lift(f35) − lift(f0) と同じ値）。
  ブートストラップ: 類ごとに 28 の対を復元抽出し（類の重みを保つ）、D_L を 2000 回引き直す（乱数の種 0）。
  95% 区間 = 2.5% 点と 97.5% 点。
判定（事前に決める）:
  上 = 区間の下端 > 0 の層の数、下 = 区間の上端 < 0 の層の数。
  支持: 上 ≥ 4、かつ 下 = 0。
  反証: 上 ≤ 1。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - 計算は決まっているので、D_L の値は #830 の結果から分かる（L4・L8・L10・L12・L16・L18 で正、L22 で 0）。
    新しい情報は区間の幅だけ。
  - 4 という数は、#830 の 6 層のうち、差が刻み 1 つ（1/140）より大きいものがいくつあるかを見ずに決めた。
  - 当たりを対ごとに残すので、h_knee_scatter_from_span の確かめにも使える（その判定は別の事前登録で決める）。
使い方:
  python exp/experiments/geo_partial_top_boot.py
  出力: exp/experiments/results/geo_partial_top_boot.json
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

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_partial_top_boot.json"
K = 256
LAYERS = [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
FS = [100, 80, 60, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
READS = ["base"] + [f"f{f}" for f in FS]
NB = 2000


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def hits_plain(members, vocab, X, idx):
    out = []
    for a, b in itertools.combinations(members, 2):
        m = (X[idx[a]] + X[idx[b]]) / 2
        sims = torch.nn.functional.cosine_similarity(X, m.unsqueeze(0), dim=1)
        sims[idx[a]] = -2
        sims[idx[b]] = -2
        out.append(1 if vocab[int(sims.argmax())] in members else 0)
    return out


def hits_mixed(members, vocab, X, form):
    out = []
    for a, b in itertools.combinations(members, 2):
        m = (X[form[("o", a)]] + X[form[("s", b)]]) / 2
        sims = torch.nn.functional.cosine_similarity(X, m.unsqueeze(0), dim=1)
        for w in (a, b):
            for k in ("o", "s"):
                sims[form[(k, w)]] = -2
        out.append(1 if vocab[int(sims.argmax())][1] in members else 0)
    return out


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
    genera = list(g.GENUS)
    res = {"layers": {}}
    for L in LAYERS:
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
        row = {"a_eq": a0, "hits": {}}
        for rd in READS:
            Xs = (Rs - Rs.mean(0, keepdim=True)).clone()
            Xm = (Rm - Rm.mean(0, keepdim=True)).clone()
            if rd in a:
                Xs[:, top] = Xs[:, top] * a[rd]
                Xm[:, top] = Xm[:, top] * a[rd]
            row["hits"][rd] = {k: {"swap": hits_plain(g.GENUS[k], base, Xs, idx),
                                   "mixed": hits_mixed(g.GENUS[k], mixed_vocab, Xm, form)} for k in genera}
        res["layers"][str(L)] = row
        print(L, flush=True)
    rng = random.Random(0)
    per = {}
    for L in LAYERS:
        h = res["layers"][str(L)]["hits"]
        d = {k: [(h["f35"][k]["swap"][i] - h["f0"][k]["swap"][i] + h["f35"][k]["mixed"][i] - h["f0"][k]["mixed"][i]) / 2
                 for i in range(len(h["f0"][k]["swap"]))] for k in genera}
        D = mean([x for k in genera for x in d[k]])
        boots = []
        for _ in range(NB):
            xs = []
            for k in genera:
                n = len(d[k])
                xs += [d[k][rng.randrange(n)] for _ in range(n)]
            boots.append(mean(xs))
        boots.sort()
        lo, hi = boots[int(0.025 * NB)], boots[int(0.975 * NB) - 1]
        per[str(L)] = {"D": D, "lo": lo, "hi": hi, "above": 1 if lo > 0 else 0, "below": 1 if hi < 0 else 0}
        print(L, json.dumps(per[str(L)]), flush=True)
    up = sum(p["above"] for p in per.values())
    dn = sum(p["below"] for p in per.values())
    if up >= 4 and dn == 0:
        v = "supported"
    elif up <= 1:
        v = "refuted"
    else:
        v = "not_judged"
    res["judgment"] = {"layers": per, "n_above": up, "n_below": dn, "partial_top_beats_removal": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    res["NB"] = NB
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
