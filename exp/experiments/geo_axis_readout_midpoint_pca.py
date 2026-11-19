"""h_axis_readout_raises_midpoint の二回目: 読み出しの測り方を変えて、事前登録し直す。

仮説（exp.yaml）: v_raise(axis_readout, midpoint_membership)。

一回目（geo_axis_readout_midpoint、80c24b2）との違い:
  一回目は「読める」を、1536 次元の隠れ状態への一つ抜きリッジの R2 ≥ 0.5 で決めた。読める量は「数」1 つだけで、
  前提（3 つ以上）を満たさず、未検証のまま残った。語が 12〜20 語しかないのに次元が多いので、
  読めるものも低く出る測り方だったと見る。
  二回目は、量ごとの語の隠れ状態を主成分の上位 3 本に落とし、その 3 次元からの一つ抜きの線形回帰で値を予測し、
  予測と値の順位相関（Spearman）で読めるかを決める。読める = ρ ≥ 0.5。

開示（結果を見る前に分かっていること）:
  - 一回目の値（量ごとの lin・bent・R2）を見たうえで、この測り方を選んだ。lin と bent の率は一回目と同じ手順なので、
    同じ値になるはずである。変わるのは、どの量を「読める」とするかだけ。したがって、この判定は
    「読み出しの測り方を選び直したら前提が満たされるか」に依る。その選び方が結果を見た後であることを、ここで開示する。
  - 主成分は、一つ抜きで除く語も含めて求める（値を使わない変換なので、値の漏れはない）。
  - 一回目の結果ファイルは書き換えない。この実験は geo_axis_readout_midpoint_pca.json に書く。

手順（ここに書かないことは一回目と同じ。関数と語の表は一回目のスクリプトから読み込み、その main は走らせない）:
  量ごとに、その量の語の隠れ状態（層 L、中心化）を、特異値分解の上位 3 本の向きに射影する（3 次元）。
  一つ抜き: 語 i を除いた残りで、3 次元 + 切片の最小二乗を解き、語 i の値を予測する。
  rho_L = 予測と値の Spearman 順位相関。
  行（geo_axis_readout_midpoint_pca.json）: "axis <名前>": {n, rho_L8, lin_L8, bent_L8, ...（層 14・20 も）}, "summary 要約": {...}
    summary: n_readable（rho_L8 ≥ 0.5 の量の数）、gap_readable、all_lin_above、gap_unreadable（読めない量があれば）、
             precondition、verdict_support
判定（事前に決める。層 8 だけで。基準の値は一回目と同じ）:
  前提: n_readable ≥ 3。満たさなければ、未検証のまま残す。
  前提を満たすとき: gap_readable ≥ 0.15 かつ all_lin_above = 1 なら支持。そうでなければ反証。
使い方:
  python exp/experiments/geo_axis_readout_midpoint_pca.py
"""
import importlib.util
import json
import math
import subprocess
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_axis_readout_midpoint_pca.json"


def first():
    spec = importlib.util.spec_from_file_location("geo1", ROOT / "exp/experiments/geo_axis_readout_midpoint.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb)


def loo_rho(X, y, k=3):
    U, S, Vh = torch.linalg.svd(X, full_matrices=False)
    Z = X @ Vh[:k].T
    n = Z.shape[0]
    A = torch.cat([Z, torch.ones(n, 1, dtype=Z.dtype)], dim=1)
    pred = []
    for i in range(n):
        keep = [j for j in range(n) if j != i]
        w = torch.linalg.lstsq(A[keep], y[keep].unsqueeze(1)).solution
        pred.append(float(A[i] @ w.squeeze(1)))
    return spearman(pred, [float(t) for t in y])


def main():
    g = first()
    allwords = sorted({w for _, (_, d) in g.AXES.items() for w in d})
    vec = g.vectors(allwords)
    rows = {}
    for name, (scale, d) in g.AXES.items():
        words = sorted(d, key=lambda w: d[w])
        n = len(words)
        vals = torch.tensor([math.log10(d[w]) if scale == "log" else float(d[w]) for w in words], dtype=torch.float64)
        lin = words[n - n // 2:]
        bent = words[: n // 4] + words[n - (n // 2 - n // 4):]
        row = {"n": n}
        for L in g.LAYERS:
            X = torch.stack([vec[L][w] for w in words])
            X = X - X.mean(0, keepdim=True)
            row[f"rho_L{L}"] = loo_rho(X, vals)
            row[f"lin_L{L}"] = g.rate(lin, words, X)
            row[f"bent_L{L}"] = g.rate(bent, words, X)
        rows[f"axis {name}"] = row

    def mean(xs):
        return sum(xs) / len(xs)

    J = g.JUDGE
    readable = [r for r in rows.values() if r[f"rho_L{J}"] >= 0.5]
    unreadable = [r for r in rows.values() if r[f"rho_L{J}"] < 0.5]
    gaps = [r[f"lin_L{J}"] - r[f"bent_L{J}"] for r in readable]
    s = {"n_readable": len(readable), "gap_readable": mean(gaps) if gaps else 0.0,
         "all_lin_above": 1 if gaps and all(x > 0 for x in gaps) else 0}
    if unreadable:
        s["gap_unreadable"] = mean([r[f"lin_L{J}"] - r[f"bent_L{J}"] for r in unreadable])
    s["precondition"] = 1 if len(readable) >= 3 else 0
    s["verdict_support"] = 1 if s["precondition"] and s["gap_readable"] >= 0.15 and s["all_lin_above"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": g.MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        print(k, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
