"""h_midpoint_depends_genus を確かめる: 中点のまとまりを決めるのは、もともとの上位概念か、量の区間の形か。

仮説（exp.yaml）: v_depend(midpoint_membership, genus_concept)。
  読み: 中点が成員に落ちる度合いは、集まりが上位概念に沿うかで決まる。量のひと続きの区間に沿うかではない。
  #361（h_interval_cut_raises_midpoint、反証）では、区間の効きは量ごとに偏り、もともとのかたまりが効くように見えた。
  ここでは、二つの上位概念の語を同じ量の上で交互に並べ、二つの切り方を直接比べる。
    上位概念の切り方: 一方の上位概念の 8 語（量の上では飛び飛び）
    区間の切り方: 量の下半分・上半分の 8 語（量の上ではひと続き、上位概念は混ざる）

手順（モデル・語の通し方・中点の判定・層は geo_axis_readout_midpoint と同じ。関数はそのスクリプトから読み込み、その main は走らせない）:
  組（この実験のために手で作った。値はおおよそ。二つの上位概念が量の上で混ざるように選んだ）:
    重さ（kg）: 動物 8 語 と 乗り物 8 語
    値段（円）: 楽器 8 語 と 家具 8 語
    人口（人）: 国 8 語 と 都市 8 語
  組ごとに、その 16 語だけを語彙とし、中心化する。
  genus_L = 二つの上位概念の集まりの率の平均。interval_L = 下半分・上半分の率の平均（値の順に並べた 16 語の前 8・後 8）。
  gap_L = genus_L − interval_L。
  purity = 下半分・上半分それぞれで多いほうの上位概念の語の割合、の平均（0.5 なら半々に混ざる、1 なら区間が上位概念と一致する）。
  行（geo_genus_vs_interval_midpoint.json）: "pair <名前>": {words, values, genus_of, purity, genus_L8, interval_L8, gap_L8, ...（層 14・20 も）},
    "summary 要約": {gap（3 組の gap_L8 の平均）、all_above（3 組とも gap_L8 > 0 なら 1）、purity（3 組の平均）、precondition、verdict_support}
判定（事前に決める。層 8 だけで）:
  前提: purity ≤ 0.75（区間が上位概念と重なりすぎていない）。満たさなければ、二つの切り方が分かれていないので、未検証のまま残す。
  前提を満たすとき: gap ≥ 0.15 かつ all_above = 1 なら支持（上位概念が決める）。そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - #353 で上位概念の集まりがまとまることは分かっているので、上位概念の切り方の率が高いことは予想できる。
    予想が立たないのは、上位概念が混ざる区間がどれだけまとまるか（量の軸が上位概念と同じくらい強い向きなら、差は出ない）。
  - 語彙が 16 語と小さいので、でたらめな 8 語でも率は 0.5 前後になる。比べるのは二つの切り方の差だけ。
  - 語を文脈なしで通すので、多義の語は意味が定まらない。
  - モデルを通す前に、値だけから purity を計算した。3 組とも下半分・上半分が 4 語ずつに混ざる（purity = 0.5）。
使い方:
  python exp/experiments/geo_genus_vs_interval_midpoint.py
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_genus_vs_interval_midpoint.json"

PAIRS = {
    "重さ": {"動物": {"ネズミ": 0.02, "ウサギ": 2, "イヌ": 15, "ブタ": 150, "ウマ": 500, "キリン": 1200, "ゾウ": 5000, "クジラ": 50000},
             "乗り物": {"スケートボード": 3, "自転車": 12, "スクーター": 80, "バイク": 200, "自動車": 1500, "トラック": 10000,
                        "電車": 40000, "飛行機": 70000}},
    "値段": {"楽器": {"カスタネット": 300, "ハーモニカ": 2000, "ギター": 30000, "フルート": 80000, "サックス": 150000,
                      "バイオリン": 300000, "ピアノ": 1000000, "ハープ": 2000000},
             "家具": {"座布団": 1000, "椅子": 5000, "棚": 10000, "机": 40000, "ベッド": 100000, "ソファ": 200000,
                      "タンス": 500000, "食器棚": 700000}},
    "人口": {"国": {"モナコ": 39000, "アイスランド": 380000, "ルクセンブルク": 650000, "デンマーク": 5900000,
                    "オランダ": 18000000, "カナダ": 39000000, "ドイツ": 84000000, "インド": 1400000000},
             "都市": {"軽井沢": 20000, "鎌倉": 170000, "京都": 1460000, "ロンドン": 9000000, "ソウル": 9500000,
                      "上海": 25000000, "東京": 37000000, "デリー": 32000000}},
}


def first():
    spec = importlib.util.spec_from_file_location("geo1", ROOT / "exp/experiments/geo_axis_readout_midpoint.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def main():
    g = first()
    allwords = sorted({w for p in PAIRS.values() for d in p.values() for w in d})
    vec = g.vectors(allwords)
    rows = {}
    for name, pair in PAIRS.items():
        genus_of = {w: k for k, d in pair.items() for w in d}
        value = {w: v for d in pair.values() for w, v in d.items()}
        words = sorted(value, key=lambda w: value[w])
        assert len(words) == 16 == len(set(words)), name
        halves = [words[:8], words[8:]]
        purity = mean([max(sum(1 for w in h if genus_of[w] == k) for k in pair) / 8 for h in halves])
        row = {"words": words, "values": [value[w] for w in words], "genus_of": [genus_of[w] for w in words], "purity": purity}
        for L in g.LAYERS:
            X = torch.stack([vec[L][w] for w in words])
            X = X - X.mean(0, keepdim=True)
            row[f"genus_L{L}"] = mean([g.rate(list(d), words, X) for d in pair.values()])
            row[f"interval_L{L}"] = mean([g.rate(h, words, X) for h in halves])
            row[f"gap_L{L}"] = row[f"genus_L{L}"] - row[f"interval_L{L}"]
        rows[f"pair {name}"] = row
    J = g.JUDGE
    ps = [r for k, r in rows.items()]
    s = {"gap": mean([r[f"gap_L{J}"] for r in ps]),
         "all_above": 1 if all(r[f"gap_L{J}"] > 0 for r in ps) else 0,
         "purity": mean([r["purity"] for r in ps])}
    s["precondition"] = 1 if s["purity"] <= 0.75 else 0
    s["verdict_support"] = 1 if s["precondition"] and s["gap"] >= 0.15 and s["all_above"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": g.MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        print(k, json.dumps({a: b for a, b in v.items() if a not in ("words", "values", "genus_of")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
