"""h_knee_scatter_from_span を確かめる: 層ごとの knee のばらつきは、語の対の引き直しの揺れに収まるか。

仮説（exp.yaml）: {v_depend, from: observation, to: [magnitude, layer]}。
  読み（#830 から）: knee は L6 40、L8 50、L10 60、L14 30、L20 30、L22 60、L24 35 と散らばり、層の順には並ばない。
  span が小さい層ほど、刻み 1 つで knee が大きく動く。

系列: #827、#830、#834。

手順（モデルは走らせない）:
  入力は #834 の結果ファイル geo_partial_top_boot.json の、対ごとの当たり（11 層 × 15 読み × 5 類 × 28 対 × swap・mixed）。
  lift(f) = ((swap(f) − swap(base)) + (mixed(f) − mixed(base))) / 2 を 140 の対で平均する（#830 と同じ値）。
  span = lift(f0) − lift(f100)。knee: span ≥ 0.03 の層で、f を 100 から下げ、はじめて lift(f) − lift(f100) ≥ 0.75・span になる f。
  ブートストラップ: 類ごとに 28 の対の番号を復元抽出し（全読み・両条件で同じ番号を使う）、span* と knee* を出す。
  2000 回（乱数の種 0）。span* < 0.03 の回は knee なしとして数える。
  knee のある層（元の値で span ≥ 0.03）ごとに、knee* のある回での 2.5% 点と 97.5% 点（段の値）を区間とする。
判定（事前に決める）:
  knee のある層が 6 未満: 判定しない。
  支持: すべての knee のある層の区間に共通に入る段の値がある（散らばりは引き直しの揺れで説明できる）。
  反証: 共通に入る段の値がない（少なくとも二つの層の区間が重ならない）。

開示（結果を見る前に分かっていること）:
  - knee の元の値は #830 と同じになる（L6 40、L8 50、L10 60、L14 30、L20 30、L22 60、L24 35）。新しい情報は区間。
  - #834 で、f35 と f0 の差は引き直しの揺れの中にあった。lift の曲線が平らな側では knee が動きやすいと予想している。
    そのため支持が出やすい手順だと分かったうえで決めている。
  - 判定が見るのは「揺れで説明できるか」だけで、「span が小さいほど揺れる」という依存は記述（span と区間の幅の順位相関）に留める。
使い方:
  python exp/experiments/geo_knee_scatter_boot.py
  出力: exp/experiments/results/geo_knee_scatter_boot.json
"""
import json
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "exp/experiments/results/geo_partial_top_boot.json"
OUT = ROOT / "exp/experiments/results/geo_knee_scatter_boot.json"
FS = [100, 80, 60, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
NB = 2000


def mean(xs):
    return sum(xs) / len(xs)


def lifts(h, genera, picks):
    def g(rd, c):
        return mean([h[rd][k][c][i] for k in genera for i in picks[k]])
    bs, bm = g("base", "swap"), g("base", "mixed")
    return {f: ((g(f"f{f}", "swap") - bs) + (g(f"f{f}", "mixed") - bm)) / 2 for f in FS}


def knee_of(lf):
    span = lf[0] - lf[100]
    if span < 0.03:
        return span, None
    return span, next(f for f in FS if lf[f] - lf[100] >= 0.75 * span)


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


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rng = random.Random(0)
    per = {}
    for L, row in src["layers"].items():
        h = row["hits"]
        genera = list(h["base"])
        n = {k: len(h["base"][k]["swap"]) for k in genera}
        span, knee = knee_of(lifts(h, genera, {k: range(n[k]) for k in genera}))
        ks = []
        for _ in range(NB):
            picks = {k: [rng.randrange(n[k]) for _ in range(n[k])] for k in genera}
            ks.append(knee_of(lifts(h, genera, picks))[1])
        got = sorted(k for k in ks if k is not None)
        p = {"span": span, "knee": knee, "no_knee_share": 1 - len(got) / NB}
        if knee is not None and got:
            p["lo"] = got[int(0.025 * len(got))]
            p["hi"] = got[int(0.975 * len(got)) - 1]
            p["width"] = p["hi"] - p["lo"]
        per[L] = p
        print(L, json.dumps(p), flush=True)
    kl = [L for L, p in per.items() if p["knee"] is not None]
    common = [f for f in FS if all(per[L]["lo"] <= f <= per[L]["hi"] for L in kl)]
    if len(kl) < 6:
        v = "not_judged"
    elif common:
        v = "supported"
    else:
        v = "refuted"
    rho = pearson(ranks([per[L]["span"] for L in kl]), ranks([per[L]["width"] for L in kl])) if len(kl) >= 2 else None
    res = {"judgment": {"layers": per, "n_knee": len(kl), "common": common, "rho_span_width": rho,
                        "knee_scatter_from_span": v}}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["source"] = SRC.name
    res["NB"] = NB
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
