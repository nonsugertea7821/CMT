"""h_axis_readout_raises_midpoint を確かめる: まっすぐなものさしで切った集まりは、中点が成員に落ちやすいか。

仮説（exp.yaml）: v_raise(axis_readout, midpoint_membership)。
  読み: 隠れ状態から線形に読み出せる量（まっすぐなものさし）で「ある値より上」と切ると、その集まりは凸を保つ。
  同じ量でも、曲げたものさし（「両端」= 下の 4 分の 1 と上の 4 分の 1）で切ると、凸が崩れる。
  前の実験（geo_cross_genus_midpoint、#353 で支持）では、上位をまたぐ性質の集まりは散らばった。
  ここでは、その理由が「ものさしの曲がり」にあるかを、同じ量の上で、切り方だけを変えて問う。

手順:
  モデル・語の通し方・層は geo_cross_genus_midpoint と同じ（Qwen/Qwen2.5-1.5B-Instruct、「w、w のトークン位置の平均、
  判定は層 8、層 14・20 は記録のみ）。
  量のついた語の表（この実験のために手で作った。値はおおよそで、桁が合っていればよい。体系からは取らない）:
    体重（kg）、長さ（m）、値段（円）、緯度（度）、数（数詞の値）、時間（秒）の 6 つ。
    緯度のほかは常用対数を取る。
  量ごとに、その量の語だけを語彙とする（量をまたいで最も近い語を探さない）。中心化してから余弦で測る。
  読み出し R2: 隠れ状態から値への、リッジ回帰の一つ抜き交差検証の決定係数。
    カーネル K = X Xᵀ（X は中心化した隠れ状態）、正則化 α = K の対角の平均。y は中心化した値。
    一つ抜きの残差 = (y − ŷ)ᵢ / (1 − Hᵢᵢ)、H = K (K + αI)⁻¹。R2 = 1 − Σ残差² / Σy²。
  切り方（同じ大きさ: 値の順に並べた n 語の半分 = n//2 語。n は偶数にそろえた）:
    lin  値の大きい側の n//2 語（まっすぐなものさしで「上」）
    bent 値の小さい側の n//4 語と大きい側の n//2 − n//4 語（曲げたものさしで「両端」）
  中点の判定は geo_cross_genus_midpoint と同じ（成員二つの中点から最も近い語を、二つを除いた語彙から選び、成員なら 1）。
  行（geo_axis_readout_midpoint.json）: "axis <名前>": {n, words, values, r2_L8, lin_L8, bent_L8, ...}, "summary 要約": {...}
    summary: n_readable（r2_L8 ≥ 0.5 の量の数）、gap_readable（読める量での lin − bent の平均）、
             all_lin_above（読める量のすべてで lin > bent なら 1）、gap_unreadable（読めない量での平均。量がなければ記録しない）、
             verdict_support、precondition
判定（事前に決める。層 8 だけで）:
  前提: n_readable ≥ 3。満たさなければ、読める量が足りないので、未検証のまま残す。
  前提を満たすとき: gap_readable ≥ 0.15 かつ all_lin_above = 1 なら支持。そうでなければ反証。
  読めない量での差は記録するが、判定には使わない。

開示（結果を見る前に分かっていること）:
  - lin と bent の成員の数は同じ。ただし bent は二つの島からなるので、島の間の組（片方が下、片方が上）が多い。
    この組の中点が成員に落ちにくいことは、まさに「曲げたものさしでは凸が崩れる」の中身なので、偏りとしては扱わない。
  - 語彙が量ごとに小さい（12〜20 語）ため、率のばらつきは大きい。
  - 語を文脈なしで通すので、多義の語（例: 本、月）は意味が定まらない。
使い方:
  python exp/experiments/geo_axis_readout_midpoint.py
"""
import itertools
import json
import math
import os
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_axis_readout_midpoint.json"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LAYERS = [8, 14, 20]
JUDGE = 8

AXES = {
    "体重": ("log", {"ネズミ": 0.02, "スズメ": 0.025, "ハムスター": 0.1, "リス": 0.4, "ウサギ": 2, "ネコ": 4,
                     "キツネ": 6, "イヌ": 15, "オオカミ": 40, "ヒツジ": 60, "シカ": 100, "ブタ": 150,
                     "ライオン": 190, "ウマ": 500, "ウシ": 700, "キリン": 1200, "カバ": 1800, "サイ": 2300,
                     "ゾウ": 5000, "クジラ": 50000}),
    "長さ": ("log", {"アリ": 0.004, "米粒": 0.005, "硬貨": 0.022, "消しゴム": 0.05, "鉛筆": 0.18, "本": 0.25,
                     "傘": 0.9, "机": 1.2, "人": 1.7, "自動車": 4.5, "バス": 11, "電車": 20, "飛行機": 60,
                     "ビル": 150, "東京タワー": 333, "富士山": 3776, "東京": 50000, "日本": 3000000,
                     "地球": 12742000, "太陽": 1390000000}),
    "値段": ("log", {"消しゴム": 100, "鉛筆": 100, "ノート": 200, "牛乳": 250, "弁当": 600, "傘": 1000,
                     "本": 1500, "靴": 8000, "時計": 20000, "自転車": 30000, "指輪": 100000, "冷蔵庫": 150000,
                     "パソコン": 150000, "自動車": 3000000, "家": 40000000, "ビル": 5000000000}),
    "緯度": ("lin", {"旭川": 43.8, "札幌": 43.1, "函館": 41.8, "青森": 40.8, "盛岡": 39.7, "仙台": 38.3,
                     "新潟": 37.9, "福島": 37.8, "宇都宮": 36.6, "金沢": 36.6, "東京": 35.7, "名古屋": 35.2,
                     "京都": 35.0, "大阪": 34.7, "広島": 34.4, "高松": 34.3, "福岡": 33.6, "熊本": 32.8,
                     "鹿児島": 31.6, "那覇": 26.2}),
    "数": ("log", {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
                   "二十": 20, "五十": 50, "百": 100, "千": 1000, "一万": 10000, "百万": 1000000}),
    "時間": ("log", {"秒": 1, "分": 60, "時間": 3600, "日": 86400, "週": 604800, "月": 2592000,
                     "季節": 7776000, "年": 31536000, "十年": 315360000, "世紀": 3153600000,
                     "千年": 31536000000, "一億年": 3153600000000000}),
}


def vectors(words):
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    p = len(tok("「", add_special_tokens=False)["input_ids"])
    out = {L: {} for L in LAYERS}
    with torch.no_grad():
        for w in words:
            ids = tok("「" + w, add_special_tokens=False, return_tensors="pt")["input_ids"]
            q = ids.shape[1]
            assert q > p, w
            hs = model(ids, output_hidden_states=True).hidden_states
            for L in LAYERS:
                out[L][w] = hs[L][0, p:q].mean(0).double()
    return out


def loo_r2(X, y):
    K = X @ X.T
    n = K.shape[0]
    alpha = K.diagonal().mean()
    H = K @ torch.linalg.inv(K + alpha * torch.eye(n, dtype=K.dtype))
    res = (y - H @ y) / (1 - H.diagonal())
    return float(1 - (res ** 2).sum() / (y ** 2).sum())


def rate(members, vocab, X):
    idx = {w: i for i, w in enumerate(vocab)}
    hits = []
    for a, b in itertools.combinations(members, 2):
        m = (X[idx[a]] + X[idx[b]]) / 2
        sims = torch.nn.functional.cosine_similarity(X, m.unsqueeze(0), dim=1)
        sims[idx[a]] = -2
        sims[idx[b]] = -2
        hits.append(1.0 if vocab[int(sims.argmax())] in members else 0.0)
    return sum(hits) / len(hits)


def main():
    allwords = sorted({w for _, (_, d) in AXES.items() for w in d})
    vec = vectors(allwords)
    rows = {}
    for name, (scale, d) in AXES.items():
        words = sorted(d, key=lambda w: d[w])
        assert len(words) % 2 == 0, name
        n = len(words)
        vals = torch.tensor([math.log10(d[w]) if scale == "log" else float(d[w]) for w in words], dtype=torch.float64)
        y = vals - vals.mean()
        lin = words[n - n // 2:]
        bent = words[: n // 4] + words[n - (n // 2 - n // 4):]
        assert len(lin) == len(bent) == n // 2
        row = {"n": n, "words": words, "values": [d[w] for w in words], "lin": lin, "bent": bent}
        for L in LAYERS:
            X = torch.stack([vec[L][w] for w in words])
            X = X - X.mean(0, keepdim=True)
            row[f"r2_L{L}"] = loo_r2(X, y)
            row[f"lin_L{L}"] = rate(lin, words, X)
            row[f"bent_L{L}"] = rate(bent, words, X)
        rows[f"axis {name}"] = row

    def mean(xs):
        return sum(xs) / len(xs)

    readable = [r for r in rows.values() if r[f"r2_L{JUDGE}"] >= 0.5]
    unreadable = [r for r in rows.values() if r[f"r2_L{JUDGE}"] < 0.5]
    s = {"n_readable": len(readable)}
    gaps = [r[f"lin_L{JUDGE}"] - r[f"bent_L{JUDGE}"] for r in readable]
    s["gap_readable"] = mean(gaps) if gaps else 0.0
    s["all_lin_above"] = 1 if gaps and all(g > 0 for g in gaps) else 0
    if unreadable:
        s["gap_unreadable"] = mean([r[f"lin_L{JUDGE}"] - r[f"bent_L{JUDGE}"] for r in unreadable])
    s["precondition"] = 1 if len(readable) >= 3 else 0
    s["verdict_support"] = 1 if s["precondition"] and s["gap_readable"] >= 0.15 and s["all_lin_above"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("words", "values", "lin", "bent")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
