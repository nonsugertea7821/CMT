"""h_genus_region_immune_display を確かめる: 中点が成員に落ちる度合いは、字面（表示語）の書き替えの影響を受けないか。

仮説（exp.yaml）: {v_immune, from: midpoint_membership, to: syntax.display}。
  読み（利用者の幾何の読み）: 状態 x ≈ g（類）+ s（字面）+ c（文脈）。類の区画 g が成り立つなら、
  字面 s を替えても、中点は同じ類の成員に落ちる。s が支配するなら、字面をまたぐ中点は区画を外れる。

系列:
  #364（geo_cross_genus_midpoint）: 同じモデル・同じ 120 語で、L8 の G_rate 0.779、R_rate 0.054（支持）。

手順:
  geo_cross_genus_midpoint の GENUS・CROSS・FILLER・vectors・rate を読み込む（その main は走らせない）。
  モデル・取り方・層・中心化は #364 と同じ。
  字面の書き替え（SWAP。手で作った）: 漢字を含む語はひらがなの読みに、カタカナの語はひらがなに、
    ひらがなだけの語はカタカナに替える。どの語も字面が変わる。
    例外: 紙はひらがなにすると髪（かみ）と同じになるので、カタカナ「カミ」にする。
  条件 3 つ（どれも L8 で判定、L14・L20 は記録のみ）:
    orig: 元の 120 語（#364 の再現。値の一致を記録する）。
    swap: 書き替えた 120 語だけの語彙で、#364 と同じ計算。
    mixed: 元と書き替えの 240 語を一つの語彙にする（全体で中心化）。集まり S の成員 a, b（a ≠ b、28 組）ごとに、
      a の元の字面と b の書き替えた字面の中点をとり、a・b の両方の字面を除いた語彙から最も近い語を選ぶ。
      その語の元の語が S の成員なら 1。S の率 = 28 組の平均。
      対照 R: 語彙の元の語からでたらめに選んだ 8 語の集まり 200 個（seed 0）で、同じ計算の率の平均。
  holds(cond) = G_rate − R_rate ≥ 0.15（#364 の前提と同じ基準）。
  drop = G_rate(orig) − G_rate(mixed)。
判定（事前に決める。L8 だけで）:
  支持: holds(swap) かつ holds(mixed) かつ drop ≤ 0.15。
  反証: holds(mixed) でない、または drop ≥ 0.3。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #364 の orig の値（G_rate 0.779、R_rate 0.054）を知っている。
  - ひらがなにすると、語は細かいトークンに分かれやすい。字面の変化には、トークンの数の変化が混じる。
  - ひらがなの読みは同音の語と重なりうる（例: きょうだい、はし）。重なりは意味を揺らすが、それも字面の効きに含める。
  - mixed では、語彙の半分が書き替えの字面なので、同じ書き方どうしが近いという字面のまとまりが、中点を引き寄せうる。
    それが仮説の否定の中身そのものなので、偏りとしては扱わない。
  - 書き替えは、表示語の同義の言い替えではなく、書き方の替えである。語の選び（同義語）までは測らない。
使い方:
  python exp/experiments/geo_genus_region_immune_display.py
  出力: exp/experiments/results/geo_genus_region_immune_display.json
"""
import importlib.util
import itertools
import json
import random
import subprocess
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_genus_region_immune_display.json"

SWAP = {
    "犬": "いぬ", "猫": "ねこ", "馬": "うま", "牛": "うし", "象": "ぞう", "ライオン": "らいおん", "兎": "うさぎ", "熊": "くま",
    "りんご": "リンゴ", "みかん": "ミカン", "ぶどう": "ブドウ", "バナナ": "ばなな", "桃": "もも", "梨": "なし", "メロン": "めろん", "スイカ": "すいか",
    "自転車": "じてんしゃ", "バス": "ばす", "電車": "でんしゃ", "飛行機": "ひこうき", "船": "ふね", "トラック": "とらっく", "タクシー": "たくしー", "バイク": "ばいく",
    "ピアノ": "ぴあの", "ギター": "ぎたー", "バイオリン": "ばいおりん", "太鼓": "たいこ", "フルート": "ふるーと", "トランペット": "とらんぺっと", "ハープ": "はーぷ", "木琴": "もっきん",
    "椅子": "いす", "机": "つくえ", "ベッド": "べっど", "棚": "たな", "ソファ": "そふぁ", "タンス": "たんす", "テーブル": "てーぶる", "鏡台": "きょうだい",
    "いちご": "イチゴ", "トマト": "とまと", "ポスト": "ぽすと", "消防車": "しょうぼうしゃ", "血": "ち", "夕焼け": "ゆうやけ", "紅葉": "もみじ", "金魚": "きんぎょ",
    "ボール": "ぼーる", "月": "つき", "硬貨": "こうか", "皿": "さら", "ドーナツ": "どーなつ", "地球": "ちきゅう", "ボタン": "ぼたん", "タイヤ": "たいや",
    "綿": "わた", "枕": "まくら", "毛布": "もうふ", "豆腐": "とうふ", "スポンジ": "すぽんじ", "マシュマロ": "ましゅまろ", "羽毛": "うもう", "粘土": "ねんど",
    "太陽": "たいよう", "電球": "でんきゅう", "星": "ほし", "蛍": "ほたる", "稲妻": "いなずま", "宝石": "ほうせき", "花火": "はなび", "懐中電灯": "かいちゅうでんとう",
    "川": "かわ", "蛇": "へび", "線路": "せんろ", "うどん": "ウドン", "髪": "かみ", "ロープ": "ろーぷ", "帯": "おび", "ホース": "ほーす",
    "学校": "がっこう", "病院": "びょういん", "先生": "せんせい", "医者": "いしゃ", "時間": "じかん", "音楽": "おんがく", "数学": "すうがく", "歴史": "れきし", "雨": "あめ", "風": "かぜ",
    "山": "やま", "海": "うみ", "町": "まち", "駅": "えき", "本": "ほん", "新聞": "しんぶん", "手紙": "てがみ", "電話": "でんわ", "時計": "とけい", "鉛筆": "えんぴつ",
    "靴": "くつ", "帽子": "ぼうし", "服": "ふく", "傘": "かさ", "鍵": "かぎ", "窓": "まど", "扉": "とびら", "道": "みち", "橋": "はし", "公園": "こうえん",
    "米": "こめ", "パン": "ぱん", "水": "みず", "火": "ひ", "石": "いし", "木": "き", "草": "くさ", "花": "はな", "紙": "カミ", "箱": "はこ",
}


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def mixed_rate(members, vocab, X, form):
    hits = []
    for a, b in itertools.combinations(members, 2):
        m = (X[form[("o", a)]] + X[form[("s", b)]]) / 2
        sims = torch.nn.functional.cosine_similarity(X, m.unsqueeze(0), dim=1)
        for w in (a, b):
            for k in ("o", "s"):
                sims[form[(k, w)]] = -2
        hits.append(1.0 if vocab[int(sims.argmax())][1] in members else 0.0)
    return sum(hits) / len(hits)


def main():
    g = module("geo_cross_genus_midpoint")
    sets = {**{k: ("G", v) for k, v in g.GENUS.items()}, **{k: ("C", v) for k, v in g.CROSS.items()}}
    base = [w for _, ws in sets.values() for w in ws] + g.FILLER
    assert len(base) == len(set(base)) == 120 and set(SWAP) == set(base)
    swapped = [SWAP[w] for w in base]
    assert len(set(swapped)) == 120 and not set(swapped) & set(base) and all(SWAP[w] != w for w in base)
    vec = g.vectors(base + swapped)
    mixed_vocab = [("o", w) for w in base] + [("s", w) for w in base]
    form = {k: i for i, k in enumerate(mixed_vocab)}
    rng = random.Random(0)
    rsets = [rng.sample(base, 8) for _ in range(200)]
    layers = {}
    for L in g.LAYERS:
        Xo = torch.stack([vec[L][w] for w in base])
        Xs = torch.stack([vec[L][SWAP[w]] for w in base])
        Xm = torch.cat([Xo, Xs])
        Xo = Xo - Xo.mean(0, keepdim=True)
        Xs = Xs - Xs.mean(0, keepdim=True)
        Xm = Xm - Xm.mean(0, keepdim=True)
        idx = {w: i for i, w in enumerate(base)}
        conds = {
            "orig": (lambda ws: g.rate(ws, base, Xo, idx)),
            "swap": (lambda ws: g.rate(ws, base, Xs, idx)),
            "mixed": (lambda ws: mixed_rate(ws, mixed_vocab, Xm, form)),
        }
        row = {}
        for c, f in conds.items():
            per = {k: f(ws) for k, (_, ws) in sets.items()}
            G = mean([per[k] for k in g.GENUS])
            C = mean([per[k] for k in g.CROSS])
            R = mean([f(ws) for ws in rsets]) if L == g.JUDGE else None
            row[c] = {"per_set": per, "G_rate": G, "C_rate": C, "diff_GC": G - C}
            if R is not None:
                row[c].update(R_rate=R, holds=1 if G - R >= 0.15 else 0)
        row["drop"] = row["orig"]["G_rate"] - row["mixed"]["G_rate"]
        layers[str(L)] = row
        print(L, json.dumps({c: {k: v for k, v in r.items() if k != "per_set"} if isinstance(r, dict) else r
                             for c, r in row.items()}, ensure_ascii=False), flush=True)
    j = layers[str(g.JUDGE)]
    if j["swap"]["holds"] and j["mixed"]["holds"] and j["drop"] <= 0.15:
        v = "supported"
    elif not j["mixed"]["holds"] or j["drop"] >= 0.3:
        v = "refuted"
    else:
        v = "not_judged"
    judgment = {"holds_swap": j["swap"]["holds"], "holds_mixed": j["mixed"]["holds"], "drop": j["drop"],
                "genus_region_immune_display": v}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": g.MODEL, "swap": SWAP, "layers": layers, "judgment": judgment},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(judgment, ensure_ascii=False))


if __name__ == "__main__":
    main()
