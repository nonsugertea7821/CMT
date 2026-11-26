"""h_midpoint_by_spread_profile（#801）を確かめる: 中点の帰属は、ばらつきの次元の大きさの並び方に依存するか。

仮説（exp.yaml）: {v_depend, from: midpoint_membership, to: [spread_dimension, magnitude]}。
  読み: #788 で、次元ごとに標準偏差で割る（zscore）と、G_rate はどの層でも上がった（L8 swap 0.229 → 0.314、mixed 0.436 → 0.593）。
  #799 で、ばらつきの上位 16 次元を 0 にしても上がらなかった（lift −0.018）。
  上がりは、ばらつきの大きな次元を消すことではなく、その大きさを他の次元に揃えることから出る。

系列:
  #364（geo_cross_genus_midpoint）、#779（geo_genus_region_immune_display）、#788（geo_rogue_dimension_midpoint）、
  #799（geo_spread_dimension_midpoint）。

手順:
  geo_cross_genus_midpoint の GENUS・CROSS・FILLER・vectors・rate・LAYERS・JUDGE と、
  geo_genus_region_immune_display の SWAP・mixed_rate を読み込む（どちらの main も走らせない）。
  読みと条件（orig・swap・mixed、各条件で中心化）は #779・#788・#799 と同じ。
  ばらつきの順位（層ごと）: 240 語（mixed）を中心化し、次元ごとの標準偏差 s_d の大きい順に並べる（#799 と同じ）。
  読み方:
    base: そのまま。
    comp_k（k = 16, 64, 256）: 上位 k 次元だけを、標準偏差が s_(k+1)（k+1 番目の値）になるよう縮める
      （その次元に s_(k+1) / s_d を掛ける）。ほかの次元は触らない。上位 k 次元の大きさを、次の次元に揃える。
    full: 全部の次元を s_d で割る（#788 の zscore と同じ尺度。余弦は全体の倍率によらない）。
  縮める倍率は mixed の 240 語で決め、orig・swap・mixed に同じ倍率を掛ける
  （full は #788 と同じく各条件の標準偏差で割る。#788 の値との一致を記録する）。
  lift(x) = ((G(swap, x) − G(swap, base)) + (G(mixed, x) − G(mixed, base))) / 2。
判定（事前に決める。L8 だけで）:
  支持: lift(comp_256) ≥ 0.05（ばらつきの大きな上位の次元の大きさを揃えるだけで上がる）。
  反証: lift(comp_256) < 0.02 かつ lift(full) ≥ 0.05（上がりは、上位を縮めることでなく、下位の小さな次元を持ち上げることから出る）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #788 の zscore の値（L8 swap 0.314、mixed 0.593）を知っている。full はそれと同じになるはず（lift 約 0.12）。
  - #799 の drop（上位 16 を 0）の値を知っている。comp_16 は 0 にするのではなく縮めるので、同じではない。
  - comp_k の値はまだどれも見ていない。
  - 下位の次元の持ち上げは、ノイズの次元も持ち上げる。full の上がりがそこから来るなら、それは類の成分が下位の次元にあることを示す。
使い方:
  python exp/experiments/geo_spread_profile_midpoint.py
  出力: exp/experiments/results/geo_spread_profile_midpoint.json
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
OUT = ROOT / "exp/experiments/results/geo_spread_profile_midpoint.json"
KS = [16, 64, 256]


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
        sd = (Rm - Rm.mean(0, keepdim=True)).std(0)
        order = torch.argsort(sd, descending=True)
        info = {"s_at": {str(k + 1): float(sd[order[k]]) for k in KS}, "s_top": float(sd[order[0]]),
                "s_median": float(sd.median())}

        def mats(rd):
            out = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = R - R.mean(0, keepdim=True)
                if rd.startswith("comp_"):
                    k = int(rd[5:])
                    top = order[:k]
                    scale = torch.ones_like(sd)
                    scale[top] = sd[order[k]] / sd[top]
                    X = X * scale
                elif rd == "full":
                    X = X / X.std(0, keepdim=True).clamp_min(1e-8)
                out[c] = X
            return out

        row = {"spread": info}
        for rd in ["base"] + [f"comp_{k}" for k in KS] + ["full"]:
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

    lifts = {rd: lift(rd) for rd in [f"comp_{k}" for k in KS] + ["full"]}
    l256, lfull = lifts["comp_256"], lifts["full"]
    v = "supported" if l256 >= 0.05 else "refuted" if l256 < 0.02 and lfull >= 0.05 else "not_judged"
    res["judgment"] = {"lift": lifts, "midpoint_by_spread_profile": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
