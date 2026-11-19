"""h_cross_genus_lowers_midpoint を確かめる: 上位概念をまたぐ性質で集めた語は、中点が成員に落ちにくいか。

仮説（exp.yaml）: v_lower(cross_genus_word, midpoint_membership)。
  読み: 上位概念（動物、果物など）で集めた語の隠れ状態は、ひとかたまり（凸）に近い。
  上位概念をまたいで性質（赤い、丸いなど）で集めた語は、かたまりが崩れる。

手順:
  モデル Qwen/Qwen2.5-1.5B-Instruct（ローカルのキャッシュ、float32、CPU）。チャットの雛形は使わない。
  語 w ごとに、文字列「w」を通し、層 L の隠れ状態を w のトークン位置で平均する（位置は、
  「 だけの符号化の長さから「w の符号化の長さまで）。判定に使う層は L=8（e4・e22 と同じ）。
  層 14、20 も記録するが、判定には使わない。
  語の集まり（この実験のために手で作った。体系からは取らない）:
    上位概念 G: 動物、果物、乗り物、楽器、家具（各 8 語）
    またぐ性質 C: 赤いもの、丸いもの、柔らかいもの、光るもの、長いもの（各 8 語。どれも 2 つ以上の上位概念にまたがる）
    埋め草 F: どちらにも入らない名詞 40 語
    語はすべての集まりを通して重ならない。
  語彙 = G・C・F の全語（120 語）。全語の平均を引いてから（中心化）、余弦で近さを測る。
  中点の判定: 集まり S の成員 a, b（28 組）ごとに、中点 (a+b)/2 から最も近い語を、a と b を除いた語彙から選ぶ。
    その語が S の成員なら 1、そうでなければ 0。S の率 = 28 組の平均。
  対照 R: 語彙からでたらめに選んだ 8 語の集まり 200 個（seed 0）の率の平均。
  行（geo_cross_genus_midpoint.json）: "set <名前>": {kind, words, rate_L8, rate_L14, rate_L20}, "summary 要約": {...}
    summary: G_rate（G の 5 集まりの率の平均、L8）、C_rate、R_rate、diff_GC（G_rate − C_rate）、
             perm_p（10 集まりを 5 と 5 に分ける 252 通りのうち、差が観察以上になる割合）、
             precondition（G_rate − R_rate ≥ 0.15 なら 1）、verdict_support（支持なら 1）、
             層 14・20 の G_rate・C_rate（記録のみ）
判定（事前に決める。L8 だけで）:
  前提: G_rate − R_rate ≥ 0.15。満たさなければ、中点の検査がかたまりを捉えていないので、
        支持にも反証にもせず、未検証のまま残す。
  前提を満たすとき: diff_GC ≥ 0.15 かつ perm_p ≤ 0.05 なら支持。そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - 語の表は手で作ったので、選び方に偏りがありうる。とくに C の語は、モデルの中で上位概念ごとに固まりやすい。
    それは「性質では一かたまりにならない」という仮説の中身そのものなので、偏りとしては扱わない。
  - 語を文脈なしで通すので、多義の語（例: 星、帯）は意味が定まらない。
使い方:
  python exp/experiments/geo_cross_genus_midpoint.py
"""
import itertools
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_cross_genus_midpoint.json"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LAYERS = [8, 14, 20]
JUDGE = 8

GENUS = {
    "動物": ["犬", "猫", "馬", "牛", "象", "ライオン", "兎", "熊"],
    "果物": ["りんご", "みかん", "ぶどう", "バナナ", "桃", "梨", "メロン", "スイカ"],
    "乗り物": ["自転車", "バス", "電車", "飛行機", "船", "トラック", "タクシー", "バイク"],
    "楽器": ["ピアノ", "ギター", "バイオリン", "太鼓", "フルート", "トランペット", "ハープ", "木琴"],
    "家具": ["椅子", "机", "ベッド", "棚", "ソファ", "タンス", "テーブル", "鏡台"],
}
CROSS = {
    "赤いもの": ["いちご", "トマト", "ポスト", "消防車", "血", "夕焼け", "紅葉", "金魚"],
    "丸いもの": ["ボール", "月", "硬貨", "皿", "ドーナツ", "地球", "ボタン", "タイヤ"],
    "柔らかいもの": ["綿", "枕", "毛布", "豆腐", "スポンジ", "マシュマロ", "羽毛", "粘土"],
    "光るもの": ["太陽", "電球", "星", "蛍", "稲妻", "宝石", "花火", "懐中電灯"],
    "長いもの": ["川", "蛇", "線路", "うどん", "髪", "ロープ", "帯", "ホース"],
}
FILLER = ["学校", "病院", "先生", "医者", "時間", "音楽", "数学", "歴史", "雨", "風",
          "山", "海", "町", "駅", "本", "新聞", "手紙", "電話", "時計", "鉛筆",
          "靴", "帽子", "服", "傘", "鍵", "窓", "扉", "道", "橋", "公園",
          "米", "パン", "水", "火", "石", "木", "草", "花", "紙", "箱"]


def vectors(words):
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
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
                out[L][w] = hs[L][0, p:q].mean(0)
    return out


def rate(members, vocab, X, idx):
    hits = []
    for a, b in itertools.combinations(members, 2):
        m = (X[idx[a]] + X[idx[b]]) / 2
        sims = torch.nn.functional.cosine_similarity(X, m.unsqueeze(0), dim=1)
        sims[idx[a]] = -2
        sims[idx[b]] = -2
        hits.append(1.0 if vocab[int(sims.argmax())] in members else 0.0)
    return sum(hits) / len(hits)


def main():
    sets = {**{k: ("G", v) for k, v in GENUS.items()}, **{k: ("C", v) for k, v in CROSS.items()}}
    vocab = [w for _, ws in sets.values() for w in ws] + FILLER
    assert len(vocab) == len(set(vocab)) == 120
    idx = {w: i for i, w in enumerate(vocab)}
    vec = vectors(vocab)
    mats = {}
    for L in LAYERS:
        X = torch.stack([vec[L][w] for w in vocab])
        mats[L] = X - X.mean(0, keepdim=True)
    rows = {}
    rates = {L: {} for L in LAYERS}
    for name, (kind, ws) in sets.items():
        r = {L: rate(ws, vocab, mats[L], idx) for L in LAYERS}
        for L in LAYERS:
            rates[L][name] = r[L]
        rows[f"set {name}"] = {"kind": kind, "words": ws, **{f"rate_L{L}": r[L] for L in LAYERS}}
    rng = random.Random(0)
    R = [rate(rng.sample(vocab, 8), vocab, mats[JUDGE], idx) for _ in range(200)]

    def mean(xs):
        return sum(xs) / len(xs)

    def g_c(L):
        return mean([rates[L][k] for k in GENUS]), mean([rates[L][k] for k in CROSS])

    G, C = g_c(JUDGE)
    names = list(sets)
    obs = G - C
    splits = list(itertools.combinations(names, 5))
    ge = sum(1 for s in splits
             if mean([rates[JUDGE][k] for k in s]) - mean([rates[JUDGE][k] for k in names if k not in s]) >= obs - 1e-12)
    perm_p = ge / len(splits)
    Rr = mean(R)
    pre = 1 if G - Rr >= 0.15 else 0
    support = 1 if pre and obs >= 0.15 and perm_p <= 0.05 else 0
    s = {"G_rate": G, "C_rate": C, "R_rate": Rr, "diff_GC": obs, "perm_p": perm_p,
         "precondition": pre, "verdict_support": support}
    for L in LAYERS:
        if L != JUDGE:
            g, c = g_c(L)
            s[f"G_rate_L{L}"] = g
            s[f"C_rate_L{L}"] = c
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        print(k, json.dumps(v, ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
