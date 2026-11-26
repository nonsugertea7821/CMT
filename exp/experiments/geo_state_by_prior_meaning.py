"""h_state_by_prior_meaning を確かめる: 隠れ状態は、学習で得た元の意味に引きずられるか。

仮説（exp.yaml）: {v_depend, from: hidden_state, to: prior_meaning}。
  登録（#774）の読み（利用者の示唆）: 表示語の字面に状態が沿うのは、モデルが学習した内容に引きずられているから。

系列:
  #771（geo_state_by_genus_display）: 類の語を前に置いても、表示語の位置の状態はほとんど類に寄らない
    （層 8 で G_orig 0.082、G_derived 0.108、up 0.025）。h_state_by_genus_display は反証。

手順:
  #771 と同じモデル・同じ動詞・同じ類・同じ取り方（geo_state_by_genus_display の collect・vectors・norm・sep を読み込む）。
  子の表示語を、元の意味を持たない作り語に替えた条件を足す。
    作り語: カタカナ 3 字（「ア」〜「ン」から「ー」「ッ」「ヲ」「ン」を除いた字）を、seed 0 で動詞ごとに引く。重複はしない。
    親（類）の表示語は替えない。
  条件 4 つ: real_orig（表示語だけ）、real_derived（親の表示語のうち、表示語）、
            nonce_orig（作り語だけ）、nonce_derived（親の表示語のうち、作り語）。
  real の 2 つは #771 と同じ計算で、#771 の値と一致するはず（一致を記録する）。
  up_real = G(real_derived) − G(real_orig)、up_nonce = G(nonce_derived) − G(nonce_orig)。
  帰無: nonce_derived の行列で親のラベルを並べ替えたもの 2000 回（seed 0）。p = G_perm ≥ G(nonce_derived) の割合。
判定（事前に決める。L8 だけで）:
  gap = up_nonce − up_real。
  支持: gap ≥ 0.05 かつ p ≤ 0.05。
  反証: gap < 0.02。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #771 の値（層 8 の up_real 0.025）を知っている。
  - 作り語は親を問わず無作為なので、nonce_orig の G は 0 の近くになる見込みが高い。
    そのため up_nonce は、類の前置きがどれだけ状態を寄せるかを、元の意味なしで測ることになる。
  - 作り語でも、カタカナの字の並びに学習された意味（外来語の断片）が入りうる。元の意味を完全には消せない。
  - 作り語の字数は 3 字に固定。実在の表示語は長さがまちまち。
使い方:
  python exp/experiments/geo_state_by_prior_meaning.py
  出力: exp/experiments/results/geo_state_by_prior_meaning.json
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geo_state_by_genus_display import LAYERS, JUDGE, N_NULL, ROOT, collect, vectors, norm, sep

OUT = ROOT / "exp/experiments/results/geo_state_by_prior_meaning.json"
KANA = [chr(c) for c in range(ord("ア"), ord("ン") + 1) if chr(c) not in "ァィゥェォッャュョヮヰヱヲンヴ"]


def nonce_words(n):
    rng = random.Random(0)
    out = []
    while len(out) < n:
        w = "".join(rng.choice(KANA) for _ in range(3))
        if w not in out:
            out.append(w)
    return out


def main():
    verbs = collect()
    kids = {}
    for k, v in verbs.items():
        if v["parent"] in verbs:
            kids.setdefault(v["parent"], []).append(k)
    names = [k for par, ks in sorted(kids.items()) if len(ks) >= 2 for k in ks]
    lab = [verbs[k]["parent"] for k in names]
    nonce = dict(zip(names, nonce_words(len(names))))
    pre = {k: verbs[verbs[k]["parent"]]["display"] + "のうち、" for k in names}
    V = {
        "real_orig": vectors([("", verbs[k]["display"]) for k in names]),
        "real_derived": vectors([(pre[k], verbs[k]["display"]) for k in names]),
        "nonce_orig": vectors([("", nonce[k]) for k in names]),
        "nonce_derived": vectors([(pre[k], nonce[k]) for k in names]),
    }
    res = {"verbs": {k: dict(verbs[k], nonce=nonce[k]) for k in names}, "n": len(names), "layers": {}}
    for L in LAYERS:
        G = {c: sep(norm(V[c][L]), lab) for c in V}
        Xn = norm(V["nonce_derived"][L])
        rng = random.Random(0)
        null = []
        for _ in range(N_NULL):
            perm = lab[:]
            rng.shuffle(perm)
            null.append(sep(Xn, perm))
        up_r = G["real_derived"] - G["real_orig"]
        up_n = G["nonce_derived"] - G["nonce_orig"]
        res["layers"][str(L)] = dict(G, up_real=up_r, up_nonce=up_n, gap=up_n - up_r,
                                     null_mean=sum(null) / N_NULL, p=sum(x >= G["nonce_derived"] for x in null) / N_NULL)
    j = res["layers"][str(JUDGE)]
    v = "supported" if j["gap"] >= 0.05 and j["p"] <= 0.05 else "refuted" if j["gap"] < 0.02 else "not_judged"
    res["judgment"] = {"gap": j["gap"], "p": j["p"], "state_by_prior_meaning": v}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["layers"], indent=1))
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
