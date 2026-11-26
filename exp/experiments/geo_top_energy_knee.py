"""h_top_energy_gap_saturates を確かめる: 上の帯の大きさの効き目は、下の帯との比のある所で頭打ちになるか。

仮説（exp.yaml）: {v_depend, from: magnitude, to: spread_dimension}。
  読み（#822 から）: L8 で上の帯に f・a0 を掛けたとき、lift は f100 0.057 → f35 0.118 と上がり、f35 以下は 0.107〜0.118 で横ばい。
  上の帯の大きさは、下の帯の大きさ（a0 で合わせた）のおよそ 35% を切ると効かなくなる、という読み。

系列: #806、#812、#815、#819、#822。

手順:
  読みと条件、帯の分け方、倍率 a0 は #822 と同じ。段を細かくする: f = 100, 80, 60, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0。
  lift を層ごとに（L8・L14・L20）出す: lift_L(f) = ((G(swap, f) − G(swap, base)) + (G(mixed, f) − G(mixed, base))) / 2。
  span_L = lift_L(0) − lift_L(100)。
  層ごとの頭打ち sat_L: span_L ≥ 0.03、かつ f ∈ {0, 5, 10, 15, 20, 25} での lift の幅（最大 − 最小）が 0.02 以下、
    かつ lift_L(35) − lift_L(100) ≥ 0.75・span_L。
  層ごとの頭打ちなし nosat_L: span_L ≥ 0.03、かつ lift_L(25) − lift_L(100) < 0.5・span_L（上がりの半分以上が 25% より下で起きる）。
判定（事前に決める。三つの層で）:
  支持: 三つの層すべてで sat_L。
  反証: 二つ以上の層で nosat_L。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #822 の L8 の粗い段（f100, 70, 50, 35, 25, 10, 0）の lift を知っている。L8 の sat は、ほぼ成り立つと分かっている。
    新しい情報は、L14・L20 と、細かい段。
  - #822 の計測ログで、L20 の f25・f10・f0 の G_rate を見た。L14 と L20 の lift は計算していない。
  - 中点の帰属は語の数の比なので、段ごとの値は 1/140 ほどの刻みで揺れる。幅 0.02 は約 3 刻み。
  - 判定の閾（0.75・0.5・0.02）は、#822 の L8 を見たあとに決めた。
使い方:
  python exp/experiments/geo_top_energy_knee.py
  出力: exp/experiments/results/geo_top_energy_knee.json
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
OUT = ROOT / "exp/experiments/results/geo_top_energy_knee.json"
K = 256
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
    for L in g.LAYERS:
        j = res["layers"][str(L)]
        lifts = {rd: ((j[rd]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
                      + (j[rd]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2 for rd in READS[1:]}
        span = lifts["f0"] - lifts["f100"]
        tail = [lifts[f"f{f}"] for f in (0, 5, 10, 15, 20, 25)]
        width = max(tail) - min(tail)
        early = lifts["f35"] - lifts["f100"]
        late = lifts["f25"] - lifts["f100"]
        sat = int(span >= 0.03 and width <= 0.02 and early >= 0.75 * span)
        nosat = int(span >= 0.03 and late < 0.5 * span)
        per[str(L)] = {"lift": lifts, "span": span, "tail_width": width, "early": early, "late": late, "sat": sat, "nosat": nosat}
    if all(p["sat"] for p in per.values()):
        v = "supported"
    elif sum(p["nosat"] for p in per.values()) >= 2:
        v = "refuted"
    else:
        v = "not_judged"
    res["judgment"] = {"layers": per, "top_energy_gap_saturates": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
