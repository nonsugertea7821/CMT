"""h_spread_band_by_display を確かめる: ばらつきの大きな帯は、表示（書き方）に沿って動くか。

仮説（exp.yaml）: {v_depend, from: spread_dimension, to: syntax.display}。
  読み（#806 から）: 上位 256 次元（分散の 7〜8 割）だけで読むと書き替えた語の帰属が下がり、それを捨てると上がった。
  上の帯が類ではなく書き方を運んでいるなら、この差が説明できる。

系列: #364、#779、#788、#799、#802、#806。

手順:
  #806 と同じく、元の 120 語と書き替えの 120 語を mixed（240 語）で中心化し、次元ごとの標準偏差で上位 256 次元（top）と
  残り 1280 次元（low）に分ける（層ごと）。
  帯ごとに、中心化した 240 語の行列 X_b（その帯の次元だけ）について、全体の平方和 T_b = Σ‖x‖² をとり、次の割合を測る:
    disp_share: 表示（orig か swap か）の 2 群の、群の平均による平方和 Σ_g n_g‖mean_g‖² / T_b。
    word_share: 語（元と書き替えの対、120 群）の平均による平方和 / T_b。表示をまたいで同じ語がまとまる度合い。
    genus_share: 類の語（GENUS の語、元と書き替えの両方）で、類の平均による平方和 / その語の平方和。
  記録: 帯ごとの 3 つの割合と、帯の差 disp_share(top) − disp_share(low)。
判定（事前に決める。L8 だけで）:
  d = disp_share(top) − disp_share(low)。
  支持: d ≥ 0.05（上の帯は、下の帯より表示に沿って分かれる）。
  反証: d ≤ 0（上の帯の表示の割合が、下の帯を越えない）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #806 の G_rate（top で swap 0.179、low で 0.279）を知っている。割合の値は、どの帯でもまだ見ていない。
  - 表示の 2 群の平均は、mixed の中心化のあとでも残る（orig と swap の平均の差）。
  - 表示の割合は、書き替えが語ごとに違う向きに動く分（語ごとの表示）を数えない。それは word_share の残りに入る。
使い方:
  python exp/experiments/geo_spread_band_display.py
  出力: exp/experiments/results/geo_spread_band_display.json
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_spread_band_display.json"
K = 256


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def between(X, groups):
    return sum(len(ix) * float(X[ix].mean(0).pow(2).sum()) for ix in groups)


def main():
    g = module("geo_cross_genus_midpoint")
    s = module("geo_genus_region_immune_display")
    sets = {**g.GENUS, **g.CROSS}
    base = [w for ws in sets.values() for w in ws] + g.FILLER
    n = len(base)
    SWAP = s.SWAP
    vec = g.vectors(base + [SWAP[w] for w in base])
    idx = {w: i for i, w in enumerate(base)}
    disp_groups = [list(range(n)), list(range(n, 2 * n))]
    word_groups = [[i, n + i] for i in range(n)]
    genus_words = [[idx[w] for w in ws] + [n + idx[w] for w in ws] for ws in g.GENUS.values()]
    gw = sorted(i for ix in genus_words for i in ix)
    pos = {i: k for k, i in enumerate(gw)}
    res = {"layers": {}}
    for L in g.LAYERS:
        Rm = torch.cat([torch.stack([vec[L][w] for w in base]), torch.stack([vec[L][SWAP[w]] for w in base])])
        Cm = Rm - Rm.mean(0, keepdim=True)
        order = torch.argsort(Cm.std(0), descending=True)
        row = {}
        for b, dims in (("top", order[:K]), ("low", order[K:])):
            X = Cm[:, dims]
            T = float(X.pow(2).sum())
            Xg = X[gw] - X[gw].mean(0, keepdim=True)
            Tg = float(Xg.pow(2).sum())
            row[b] = {
                "disp_share": between(X, disp_groups) / T,
                "word_share": between(X, word_groups) / T,
                "genus_share": between(Xg, [[pos[i] for i in ix] for ix in genus_words]) / Tg,
            }
        row["diff"] = {k: row["top"][k] - row["low"][k] for k in row["top"]}
        print(L, json.dumps(row), flush=True)
        res["layers"][str(L)] = row
    d = res["layers"][str(g.JUDGE)]["diff"]["disp_share"]
    v = "supported" if d >= 0.05 else "refuted" if d <= 0 else "not_judged"
    res["judgment"] = {"d": d, "spread_band_by_display": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
