"""h_spread_dimension_lowers_midpoint を確かめる: 語のあいだのばらつきが大きな次元は、中点の帰属を下げるか。

仮説（exp.yaml）: {v_lower, from: spread_dimension, to: midpoint_membership}。
  spread_dimension: {extends: state_feature_direction, mod: {of: [v_vary, to], with: word}}。
  読み: #788 で、平均の大きさで切った外れの次元を 0 にしても G_rate は上がらなかった（lift 0.004）。
  一方、次元ごとに標準偏差で割る（zscore）と、どの層でも上がった（L8 swap 0.229 → 0.314、mixed 0.436 → 0.593）。
  平均の大きさではなく、語のあいだのばらつきが大きな少数の次元が、余弦を引きずっている。

系列:
  #364（geo_cross_genus_midpoint）: 120 語、平均で読み、L8 の G_rate 0.779。
  #779（geo_genus_region_immune_display）: 書き替えた語で L8 の G_rate 0.229、混ぜると 0.436（反証）。
  #788（geo_rogue_dimension_midpoint）: 外れの次元を 0 にしても上がらない（反証）。zscore は上がる（記録のみ）。

手順:
  geo_cross_genus_midpoint の GENUS・CROSS・FILLER・vectors・rate・LAYERS・JUDGE と、
  geo_genus_region_immune_display の SWAP・mixed_rate を読み込む（どちらの main も走らせない）。
  元の 120 語と書き替えの 120 語を、#364 と同じく「w で通し、語のトークン位置の平均で読む。
  ばらつきの次元（層ごと）: 240 語（mixed）を中心化し、次元ごとの標準偏差 s_d をとる。
    s_d の大きい順に上位 K = 16 次元（隠れ状態 1536 次元の約 1%）を、ばらつきの次元とする。
    記録: 番号、s_d / median(s)、中心化した分散に占める割合、#788 の外れの次元との重なり。
  読み方:
    base: そのまま（#779・#788 の値の一致を記録する）。
    drop: ばらつきの次元を 0 にする。
    rand: ばらつきの次元を除いた次元から、同じ K 個をでたらめに選んで 0 にする（20 回、seed 0。G の平均を記録）。
  条件は #779 と同じ orig・swap・mixed（各条件の中心化は #779 と同じ）。G_rate・C_rate を各層で、R_rate・holds を L8 で。
判定（事前に決める。L8 だけで）:
  lift = ((G(swap, drop) − G(swap, base)) + (G(mixed, drop) − G(mixed, base))) / 2。
  支持: lift ≥ 0.10 かつ holds(swap, drop)。
  反証: lift < 0.03。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #364・#779・#788 の値を知っている。zscore で上がることは知っているが、どの次元が効いているかは見ていない。
  - K = 16 は、ばらつきの分布を見ずに決めた。上位 16 のばらつきが中央値の何倍かは、まだ見ていない。
  - zscore は全部の次元の重みを変えるので、上位の次元を 0 にすることとは同じでない。
    上がりがばらつきの裾の広い範囲から来ているなら、drop では上がらず、仮説は反証になりうる。
  - drop は次元を捨てるので、その次元に類の成分があれば、それも捨てる。rand はその分の比べ。
  - ばらつきの次元は、orig と swap を混ぜた 240 語で決める。swap と mixed の両方で同じ次元を落とす。
使い方:
  python exp/experiments/geo_spread_dimension_midpoint.py
  出力: exp/experiments/results/geo_spread_dimension_midpoint.json
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
OUT = ROOT / "exp/experiments/results/geo_spread_dimension_midpoint.json"
K = 16
N_RAND = 20
ROGUE_L8 = [147, 222, 520, 609, 713, 969, 1073, 1166, 1173, 1222, 1421]


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
        med = sd.median()
        dims = [int(d) for d in torch.argsort(sd, descending=True)[:K]]
        var = Cm.pow(2).sum(0)
        info = {"spread_dims": dims, "ratio_to_median": {str(d): float(sd[d] / med) for d in dims},
                "centered_var_share": float(var[dims].sum() / var.sum()),
                "overlap_rogue_l8": sorted(set(dims) & set(ROGUE_L8))}
        others = [d for d in range(Rm.shape[1]) if d not in set(dims)]
        drng = random.Random(0)
        rand_dims = [drng.sample(others, K) for _ in range(N_RAND)]

        def mats(zero):
            out = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = R - R.mean(0, keepdim=True)
                if zero:
                    X = X.clone()
                    X[:, zero] = 0
                out[c] = X
            return out

        def rates(M, with_r):
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
                if with_r:
                    Rr = mean([f(ws) for ws in rsets])
                    r[c].update(R_rate=Rr, holds=1 if G - Rr >= 0.15 else 0)
            return r

        row = {"spread": info}
        row["base"] = rates(mats(None), L == g.JUDGE)
        row["drop"] = rates(mats(dims), L == g.JUDGE)
        rr = [rates(mats(rd), False) for rd in rand_dims]
        row["rand"] = {c: {"G_rate": mean([x[c]["G_rate"] for x in rr]), "C_rate": mean([x[c]["C_rate"] for x in rr])}
                       for c in ("orig", "swap", "mixed")}
        for rd in ("base", "drop", "rand"):
            print(L, rd, json.dumps(row[rd]), flush=True)
        print(L, json.dumps(info), flush=True)
        res["layers"][str(L)] = row
    j = res["layers"][str(g.JUDGE)]
    lift = ((j["drop"]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
            + (j["drop"]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2
    lift_rand = ((j["rand"]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
                 + (j["rand"]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2
    v = ("supported" if lift >= 0.10 and j["drop"]["swap"]["holds"] else "refuted" if lift < 0.03 else "not_judged")
    res["judgment"] = {"lift": lift, "lift_rand": lift_rand, "spread_dimension_lowers_midpoint": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
