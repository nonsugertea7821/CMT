"""h_band_energy_sets_midpoint を確かめる: 帯の平方和の釣り合いが、中点の帰属を決めるか。

仮説（exp.yaml）: {v_depend, from: midpoint_membership, to: magnitude}。
  読み（#806・#808 から）: 上位 256 次元（top）と残り 1280 次元（low）とで、表示・語・類の割合はほぼ同じだった（#808）。
  それでも low だけで読むと帰属が上がった（#806、L8 lift 0.111）。top が平方和の 7〜8 割を占めて余弦を支配するから、という読み。

系列: #364、#779、#788、#799、#802、#806、#808。

手順:
  読みと条件（orig・swap・mixed、各条件で中心化）、ばらつきの順位と帯の分け方は #806 と同じ（240 語の mixed で、層ごと）。
  読み方:
    base: そのまま。
    low: top を 0 にする（#806 の low と同じ。一致を記録する）。
    eq: top の次元すべてに同じ倍率 a を掛け、mixed の 240 語で top の平方和が low の平方和と等しくなるようにする。
      向きと、top の中の次元どうしの比は変えない。a は mixed で決め、orig・swap・mixed に同じ a を掛ける。
    eq_half: 同じく、top の平方和が low の半分になるよう縮める（釣り合いをさらに low の側に寄せる）。
  lift(x) = ((G(swap, x) − G(swap, base)) + (G(mixed, x) − G(mixed, base))) / 2。
判定（事前に決める。L8 だけで）:
  支持: lift(eq) ≥ 0.05（帯の平方和を揃えるだけで、帰属が上がる）。
  反証: lift(eq) < 0.02（揃えても上がらない。low の上がりは、平方和の大きさ以外のもの、たとえば top の中の向きから来る）。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #806 の low の値（L8 swap 0.279、mixed 0.607、lift 0.111）と、#802 の comp_256（lift 0.093）を知っている。
  - #806 の top の平方和の割合（L8 0.728）を知っている。eq の a は、そこからおよそ sqrt(0.272 / 0.728) ≈ 0.61 になるはず。
  - eq と eq_half の値はまだ見ていない。
使い方:
  python exp/experiments/geo_band_energy_midpoint.py
  出力: exp/experiments/results/geo_band_energy_midpoint.json
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
OUT = ROOT / "exp/experiments/results/geo_band_energy_midpoint.json"
K = 256
READS = ["base", "low", "eq", "eq_half"]


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
        a = {"eq": a0, "eq_half": a0 * 0.5 ** 0.5}
        info = {"top_var_share": float(var[top].sum() / var.sum()), "a_eq": a["eq"], "a_eq_half": a["eq_half"]}

        def mats(rd):
            out = {}
            for c, R in (("orig", Ro), ("swap", Rs), ("mixed", Rm)):
                X = (R - R.mean(0, keepdim=True)).clone()
                if rd == "low":
                    X[:, top] = 0
                elif rd in a:
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
    v = "supported" if lifts["eq"] >= 0.05 else "refuted" if lifts["eq"] < 0.02 else "not_judged"
    res["judgment"] = {"lift": lifts, "band_energy_sets_midpoint": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    res["K"] = K
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
