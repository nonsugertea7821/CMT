"""E62: 適用例は、概念をまたぐロジット差の散らばりを縮めるか（h_examples_compress_margin）。

仮説（exp.yaml）: {v_rely, from: margin_spread, to: application_example}。
系列:
  E60（#856）: G2c の 24 概念で、例の数を 0 → 8 にすると、例なしで外れていた概念の margin は上がり、
  当たっていた概念の margin は下がった（1.5B: 外れ 10 のうち 9 が上がり、当たり 14 のうち 11 が下がった。
  4B: 外れ 6 のうち 4 が上がり、当たり 18 のうち 11 が下がった）。h_examples_raise_apply は反証。
  読み（未検証）: 例は apply を上げるのではなく、概念をまたぐ margin の散らばりを縮める。
  対の読み: 例なしの値の、概念ごとの癖による平均への戻り（同じ散らばりのまま、高いものが下がり低いものが上がる）。
ここでは、読みを作った G2c ではなく、G2k の 24 概念で測る（通常の読みが定義と一致し、例なしでほぼ当たる）。

題材: concepts_ja.json の G2k の 24 概念。学習はしない。前向き計算だけ。
設問と margin: E60 と同じ（「次の定義に従うこと。」＋定義文＋設問。選択肢の順を入れ替えた 2 回の
  正答と誤答の logit の差の平均）。
条件: E60 と同じ k0・k2・k8。例は G2k の、概念 i+1 〜 i+k（24 で割った余り）。例 1 つの形も E60 と同じ。

量（モデルと条件ごと）: acc、margin の平均、margin の散らばり sd（24 概念の母標準偏差）。
判定に使う量（モデルごと）:
  ratio = sd(k8) / sd(k0)。
  closer = |margin(k8) − mean(k8)| < |margin(k0) − mean(k0)| の概念の数（24 のうち。各条件の平均からの距離）。
    p = closer の符号検定の片側の p 値（距離が等しい概念は除く）。
  k2 は推移を見るためだけに測る（判定に使わない）。

判定（事前登録。モデルごと。Qwen2.5-1.5B-Instruct と Qwen3-4B の両方を測る）:
  支持: ratio ≤ 0.8 かつ p ≤ 0.05（散らばりが 2 割以上縮み、平均に寄った概念が有意に多い）。
  反証: ratio ≥ 1.0 かつ closer ≤ 12（散らばりが縮まず、平均に寄った概念も半分以下）。
    平均への戻りだけなら、散らばりは変わらない（ratio ≈ 1）。
  その他: 判定しない。
  二つのモデルで支持と反証に分かれたら mixed。片方が判定しないなら、もう片方の判定を採る。

開示（結果を見る前に分かっていること）:
  - E60 の結果を見てから、この手順を書いた。G2k はこの系列（E58〜E60）では測っていない。
    E10〜E19 で G2k を別の設問の形で測っている（結果は読んだことがある）。
  - 登録の PR（#857）では「G2k で例を置くと margin は下がるはず」と書いた。ここでは、仮説の語（散らばり）に
    合わせて、平均の下がりではなく散らばりで判定する。margin の平均の動きは記録するが、判定に使わない。
  - 例の選び方と書き方は 1 通り。k8 の例は k2 の例を含む。
  - 1.5B は float32、4B は bfloat16（E58〜E60 と同じ）。

使い方:
  python e62_examples_compress_margin.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e62_examples_compress_margin.py --model Qwen/Qwen3-4B --dtype bfloat16
  出力: results/e62_<model>.json（途中保存: results/e62_<model>.partial.json。概念ごと）
"""
import argparse
import json
import math

from e1_context_injection import ROOT, Runner
from e60_examples_raise_apply import KS, near_prefix, example_block, apply_margin, sign_p


def sd(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2k"]
    assert len(items) == 24
    short = args.model.split("/")[-1]
    out = ROOT / "results" / f"e62_{short}.json"
    part = ROOT / "results" / f"e62_{short}.partial.json"
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "model": args.model, "dtype": args.dtype, "rows": {}, "summary": {}, "resumed": 0}
    if part.exists():
        res["resumed"] += 1
    r = Runner(args.model, args.dtype)
    for i, it in enumerate(items):
        L = it["defs"][0]
        if L in res["rows"]:
            continue
        row = {}
        for k in KS:
            row[f"k{k}"] = apply_margin(r, example_block(items, i, defs, k) + near_prefix(defs, L), it)
        res["rows"][L] = row
        part.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(L, {c: round(v, 3) for c, v in row.items()}, flush=True)

    rows = list(res["rows"].values())
    n = len(rows)
    for k in KS:
        ms = [row[f"k{k}"] for row in rows]
        res["summary"][f"k{k}"] = {"acc": sum(m > 0 for m in ms) / n, "margin": sum(ms) / n, "sd": sd(ms)}
    m0 = res["summary"]["k0"]["margin"]
    m8 = res["summary"]["k8"]["margin"]
    near = [abs(row["k8"] - m8) < abs(row["k0"] - m0) for row in rows]
    far = [abs(row["k8"] - m8) > abs(row["k0"] - m0) for row in rows]
    closer, farther = sum(near), sum(far)
    p = sign_p(closer, farther)
    ratio = res["summary"]["k8"]["sd"] / res["summary"]["k0"]["sd"]
    v = ("supported" if ratio <= 0.8 and p <= 0.05 else
         "refuted" if ratio >= 1.0 and closer <= 12 else "not_judged")
    res["paired"] = {"ratio": ratio, "closer": closer, "farther": farther, "p": p}
    res["judgment"] = {"examples_compress_margin": v}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()
    print(res["summary"], res["paired"], res["judgment"])


if __name__ == "__main__":
    main()
