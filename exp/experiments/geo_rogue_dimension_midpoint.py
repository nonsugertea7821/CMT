"""h_rogue_dimension_lowers_midpoint を確かめる: 桁違いに大きな値をとる次元は、中点の帰属を下げるか。

仮説（exp.yaml）: {v_lower, from: rogue_dimension, to: midpoint_membership}。
  読み: トランスフォーマーの隠れ状態には、少数の次元が他より桁違いに大きな値をとることがある。
  余弦はその次元に引きずられ、類の成分の向きが見えにくくなる。

系列:
  #364（geo_cross_genus_midpoint）: 120 語、平均で読み、L8 の G_rate 0.779。
  #779（geo_genus_region_immune_display）: 書き替えた語で L8 の G_rate 0.229、混ぜると 0.436（反証）。
  #782（geo_midpoint_by_token_position）: 最後のトークンで読んでも swap は 0.314（判定なし）。

手順:
  geo_cross_genus_midpoint の GENUS・CROSS・FILLER・vectors・rate・LAYERS・JUDGE と、
  geo_genus_region_immune_display の SWAP・mixed_rate を読み込む（どちらの main も走らせない）。
  元の 120 語と書き替えの 120 語を、#364 と同じく「w で通し、語のトークン位置の平均で読む。
  外れの次元（層ごと）: 240 語の中心化する前の状態で、次元ごとの |値| の平均 a_d をとる。
    a_d ≥ 10 × median(a) の次元を外れの次元とする（「桁違い」を 10 倍で切る）。
    記録: 外れの次元の番号と数、a_d / median(a)、中心化した後の分散に占める外れの次元の割合。
  読み方 3 つ（どれも #779 と同じ中心化のあと）:
    base: そのまま（#779 の値の一致を記録する）。
    drop: 外れの次元を 0 にする。
    zscore: 次元ごとに、その条件の語彙の標準偏差で割る（記録のみ）。
  条件は #779 と同じ orig・swap・mixed。G_rate・C_rate を各層で、R_rate・holds を L8 で。
判定（事前に決める。L8 だけで）:
  lift = ((G(swap, drop) − G(swap, base)) + (G(mixed, drop) − G(mixed, base))) / 2。
  L8 に外れの次元がなければ判定しない。
  支持: lift ≥ 0.10 かつ holds(swap, drop)。
  反証: lift < 0.03。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #364・#779・#782 の値を知っている。
  - Qwen2.5-1.5B の L8 に外れの次元があるかは、まだ見ていない。大きな値は文の先頭のトークンに出やすいと聞くが、
    ここでは「の位置を読みから外しているので、残るかは分からない。
  - 中心化で、どの語でも同じ大きな値は消える。外れの次元が中点を動かすのは、語ごとに値が変わる分だけ。
  - drop は次元を捨てるので、その次元に類の成分があれば、それも捨てる。
使い方:
  python exp/experiments/geo_rogue_dimension_midpoint.py
  出力: exp/experiments/results/geo_rogue_dimension_midpoint.json
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
OUT = ROOT / "exp/experiments/results/geo_rogue_dimension_midpoint.json"
FACTOR = 10.0


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def rogue(raw):
    a = raw.abs().mean(0)
    med = a.median()
    dims = [int(d) for d in torch.nonzero(a >= FACTOR * med).flatten()]
    return dims, {str(d): float(a[d] / med) for d in dims}


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
        dims, ratio = rogue(Rm)
        Cm = Rm - Rm.mean(0, keepdim=True)
        var = Cm.pow(2).sum(0)
        share = float(var[dims].sum() / var.sum()) if dims else 0.0
        info = {"rogue_dims": dims, "ratio_to_median": ratio, "centered_var_share": share}
        row = {"rogue": info}
        for rd in ["base", "drop", "zscore"]:
            mats = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = R - R.mean(0, keepdim=True)
                if rd == "drop" and dims:
                    X = X.clone()
                    X[:, dims] = 0
                if rd == "zscore":
                    X = X / X.std(0, keepdim=True).clamp_min(1e-8)
                mats[c] = X
            conds = {
                "orig": (lambda ws, X=mats["orig"]: g.rate(ws, base, X, idx)),
                "swap": (lambda ws, X=mats["swap"]: g.rate(ws, base, X, idx)),
                "mixed": (lambda ws, X=mats["mixed"]: s.mixed_rate(ws, mixed_vocab, X, form)),
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
    if not j["rogue"]["rogue_dims"]:
        lift, v = None, "not_judged"
    else:
        lift = ((j["drop"]["swap"]["G_rate"] - j["base"]["swap"]["G_rate"])
                + (j["drop"]["mixed"]["G_rate"] - j["base"]["mixed"]["G_rate"])) / 2
        v = ("supported" if lift >= 0.10 and j["drop"]["swap"]["holds"] else "refuted" if lift < 0.03 else "not_judged")
    res["judgment"] = {"lift": lift, "rogue_dimension_lowers_midpoint": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["factor"] = FACTOR
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
