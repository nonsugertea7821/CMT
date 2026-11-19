"""h_interval_cut_raises_midpoint を確かめる: 量のひと続きの区間で切ると、中点が成員に落ちやすいか。

仮説（exp.yaml）: v_raise(interval_cut, midpoint_membership)。
  読み: まとまりを決めるのは切り方の形である。ひと続きの区間（下・中・上）で切ると一かたまりを保ち、
  両端で切ると崩れる。対になる仮説 h_midpoint_depends_genus（もともとの上位概念のかたまりが効く）と分けるため、
  上位概念が一つしかない量だけで判定する。上位概念が一つなら、上位概念の違いでは区間と両端の差を説明できない。

手順（モデル・語の通し方・中点の判定・層は geo_axis_readout_midpoint と同じ。関数はそのスクリプトから読み込み、
     その main は走らせない）:
  判定に使う量（上位概念が一つ。語は前の実験と重ならないよう新しく作った。値はおおよそ）:
    乗り物の速さ（km/h、20 語）、果物の重さ（g、16 語）、国の人口（人、20 語）。どれも常用対数を取る。
  記録だけの量（上位概念が混ざる。h_midpoint_depends_genus のために測っておく。判定には使わない）:
    物の重さ（kg、20 語）、物の温度（℃、16 語、対数を取らない）、物の古さ（年前、20 語）。
  量ごとに、その量の語だけを語彙とし、中心化する。値の順に並べた n 語（n は 4 の倍数）を四つに分ける（q1 < q2 < q3 < q4）。
  切り方（どれも n/2 語）:
    lower  = q1 + q2、middle = q2 + q3、upper = q3 + q4（ひと続きの区間）
    ends   = q1 + q4（両端）
  interval_L = lower・middle・upper の率の平均。gap_L = interval_L − ends_L。
  行（geo_interval_cut_midpoint.json）: "axis <名前>": {kind: single/mixed, n, words, values, lower_L8, middle_L8, upper_L8, ends_L8, gap_L8, ...（層 14・20 も）},
      "summary 要約": {gap_single（判定に使う 3 つの量の gap_L8 の平均）、all_single_above（3 つとも gap_L8 > 0 なら 1）、
                       middle_single（3 つの middle_L8 の平均）、ends_single、gap_mixed（記録だけの量の平均）、verdict_support}
判定（事前に決める。層 8、上位概念が一つの 3 つの量だけで）:
  gap_single ≥ 0.15 かつ all_single_above = 1 なら支持。そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - 前の実験（#354、geo_axis_readout_midpoint）で、上半分（lin）と両端（bent）の差は 6 つの量のうち 5 つで正だった。
    その中で上位概念が一つの量は、体重（差 0.53）と緯度（0.16）。だから、支持の向きは予想できる。
    予想が立たないのは、middle（両端どちらにも触れない真ん中の区間）がまとまるかどうか。
    middle がまとまらず upper・lower だけがまとまるなら、効いているのは区間の形ではなく両端のかたまり（大きいもの・小さいもの）。
    その場合でも、この判定（3 区間の平均）は支持になりうる。そのため middle_single を記録して、判定とは別に報告する。
  - 語を文脈なしで通すので、多義の語は意味が定まらない。
使い方:
  python exp/experiments/geo_interval_cut_midpoint.py
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_interval_cut_midpoint.json"

AXES = {
    "乗り物の速さ": ("single", "log", {"三輪車": 5, "一輪車": 8, "帆船": 15, "自転車": 20, "気球": 20, "漁船": 30,
                                       "路面電車": 40, "フェリー": 40, "潜水艦": 40, "スクーター": 50, "バス": 80,
                                       "バイク": 100, "自動車": 120, "電車": 120, "ヘリコプター": 250, "新幹線": 300,
                                       "リニア": 500, "飛行機": 900, "戦闘機": 2000, "ロケット": 28000}),
    "果物の重さ": ("single", "log", {"ブルーベリー": 1, "さくらんぼ": 8, "いちご": 15, "ライチ": 20, "梅": 20,
                                     "すもも": 60, "キウイ": 100, "みかん": 100, "レモン": 120, "バナナ": 150,
                                     "柿": 200, "桃": 250, "りんご": 300, "梨": 400, "パイナップル": 1500, "スイカ": 5000}),
    "国の人口": ("single", "log", {"モナコ": 39000, "アイスランド": 380000, "ニュージーランド": 5100000,
                                   "デンマーク": 5900000, "スイス": 8800000, "オランダ": 18000000,
                                   "オーストラリア": 26000000, "カナダ": 39000000, "スペイン": 48000000,
                                   "韓国": 52000000, "イギリス": 67000000, "フランス": 68000000, "ドイツ": 84000000,
                                   "日本": 125000000, "メキシコ": 130000000, "ロシア": 140000000,
                                   "ブラジル": 210000000, "アメリカ": 330000000, "インド": 1400000000,
                                   "中国": 1410000000}),
    "物の重さ": ("mixed", "log", {"硬貨": 0.005, "鉛筆": 0.006, "りんご": 0.3, "本": 0.5, "傘": 0.6, "猫": 4,
                                  "椅子": 5, "自転車": 12, "犬": 15, "テレビ": 20, "人": 60, "ピアノ": 250, "馬": 500,
                                  "自動車": 1500, "象": 5000, "トラック": 10000, "バス": 12000, "飛行機": 70000,
                                  "船": 1000000, "ビル": 100000000}),
    "物の温度": ("mixed", "lin", {"液体窒素": -196, "ドライアイス": -78, "南極": -50, "冷凍庫": -18, "氷": 0,
                                  "冷蔵庫": 4, "井戸水": 15, "人の体": 37, "風呂": 41, "コーヒー": 70, "熱湯": 100,
                                  "天ぷら油": 180, "オーブン": 220, "ろうそく": 1000, "溶岩": 1100, "太陽": 5500}),
    "物の古さ": ("mixed", "log", {"スマートフォン": 15, "インターネット": 50, "東京タワー": 66, "テレビ": 70,
                                  "飛行機": 120, "電話": 150, "鉄道": 200, "活版印刷": 580, "法隆寺": 1400,
                                  "紙": 1900, "万里の長城": 2200, "ピラミッド": 4500, "文字": 5000, "車輪": 5500,
                                  "農業": 10000, "火": 1000000, "恐竜": 66000000, "月": 4500000000,
                                  "地球": 4540000000, "宇宙": 13800000000}),
}


def first():
    spec = importlib.util.spec_from_file_location("geo1", ROOT / "exp/experiments/geo_axis_readout_midpoint.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    g = first()
    allwords = sorted({w for _, (_, _, d) in AXES.items() for w in d})
    vec = g.vectors(allwords)
    rows = {}
    for name, (kind, scale, d) in AXES.items():
        words = sorted(d, key=lambda w: d[w])
        n = len(words)
        assert n % 4 == 0, name
        k = n // 4
        q = [words[i * k:(i + 1) * k] for i in range(4)]
        cuts = {"lower": q[0] + q[1], "middle": q[1] + q[2], "upper": q[2] + q[3], "ends": q[0] + q[3]}
        row = {"kind": kind, "n": n, "words": words, "values": [d[w] for w in words]}
        for L in g.LAYERS:
            X = torch.stack([vec[L][w] for w in words])
            X = X - X.mean(0, keepdim=True)
            for c, ws in cuts.items():
                row[f"{c}_L{L}"] = g.rate(ws, words, X)
            row[f"interval_L{L}"] = (row[f"lower_L{L}"] + row[f"middle_L{L}"] + row[f"upper_L{L}"]) / 3
            row[f"gap_L{L}"] = row[f"interval_L{L}"] - row[f"ends_L{L}"]
        rows[f"axis {name}"] = row

    def mean(xs):
        return sum(xs) / len(xs)

    J = g.JUDGE
    single = [r for r in rows.values() if r["kind"] == "single"]
    mixed = [r for r in rows.values() if r["kind"] == "mixed"]
    s = {"gap_single": mean([r[f"gap_L{J}"] for r in single]),
         "all_single_above": 1 if all(r[f"gap_L{J}"] > 0 for r in single) else 0,
         "middle_single": mean([r[f"middle_L{J}"] for r in single]),
         "ends_single": mean([r[f"ends_L{J}"] for r in single]),
         "gap_mixed": mean([r[f"gap_L{J}"] for r in mixed])}
    s["verdict_support"] = 1 if s["gap_single"] >= 0.15 and s["all_single_above"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": g.MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k_, v in rows.items():
        print(k_, json.dumps({a: b for a, b in v.items() if a not in ("words", "values")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
