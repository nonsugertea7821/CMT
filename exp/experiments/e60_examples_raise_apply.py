"""E60: 適用例の数を増やすと、apply（定義の当てはめ）は上がるか（h_examples_raise_apply）。

仮説（exp.yaml）: {v_rely, from: usage_apply, to: application_example}。
目的との関係: d_metric の物差し（E58）で、使い方をまたぐ一貫 joint の律速は apply だった。
E59 では、ほかの 2 概念の適用例を前に置くと、4B で apply が 0.750 → 0.875 に上がったが、
joint の当たり外れ（24 概念の二値）では検定に届かなかった。1.5B では apply は動かなかった。
ここでは apply だけを、当たり外れではなく概念ごとの margin（連続値）で比べ、例の数を 0・2・8 と変えて測る。

題材: E58・E59 と同じ G2c の 24 概念（定義と食い違う通常の読みがある、当てはめの設問）。学習はしない。前向き計算だけ。
設問と margin: E59 の apply と同じ（「次の定義に従うこと。」＋定義文＋設問。選択肢の順を入れ替えた 2 回の
  正答と誤答の logit の差の平均。margin > 0 を当たりとする）。

条件（例の数 k。同じ実行の中で全部を測る）:
  k0  E59 の near と同じ（例なし）。
  k2  E59 の near_ex と同じ（概念 i の例は、概念 i+1, i+2。24 で割った余り）。
  k8  概念 i+1 〜 i+8 の例。例 1 つの形は E59 と同じ（定義＋設問＋「答え: 正答」）。
  例は対象の概念と違う概念のもので、対象の概念の答えは見せない。

量（モデルと条件ごと）: apply の正答率 acc、margin の平均。
対の比較（判定に使う）: 概念ごとの d = margin(k8) − margin(k0)。
  pos = d > 0 の概念の数（24 のうち）。p = 符号検定の片側の p 値（d = 0 は除く）。
  k2 は量の推移を見るためだけに測る（判定に使わない）。

判定（事前登録。モデルごと。1.5B と 4B の両方を測る）:
  支持: pos > neg かつ p ≤ 0.05（24 で d = 0 がないとき、pos ≥ 17）。
  反証: pos ≤ neg。
  その他: 判定しない。
  二つのモデルで支持と反証に分かれたら mixed。片方が判定しないなら、もう片方の判定を採る。

開示（結果を見る前に分かっていること）:
  - E59 の結果（4B の k2 で apply の当たりが 3 増えて 0 減った、1.5B は動かなかった）を見てから、この手順を書いた。
  - 例の選び方（後ろに続く概念）と書き方は 1 通りだけ。k8 の例は k2 の例を含む。
  - k0 と k2 は E59 の near と near_ex の apply と同じ測り方なので、同じ当たり外れが出るはず（違えば開示する）。
  - 1.5B は float32、4B は bfloat16（E58・E59 と同じ）。

使い方:
  python e60_examples_raise_apply.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e60_examples_raise_apply.py --model Qwen/Qwen3-4B --dtype bfloat16
  出力: results/e60_<model>.json
"""
import argparse
import json
import math

import torch

from e1_context_injection import ROOT, Runner, question_text

KS = (0, 2, 8)


def near_prefix(defs, label):
    return "次の定義に従うこと。\n" + defs[label] + "\n\n"


def example_block(items, i, defs, k):
    if k == 0:
        return ""
    parts = []
    for j in range(1, k + 1):
        ex = items[(i + j) % len(items)]
        body, _ = question_text(ex, False)
        parts.append(near_prefix(defs, ex["defs"][0]) + body + f"\n答え: {ex['correct']}")
    return "例:\n" + "\n\n".join(parts) + "\n\nでは、次の問いに答えてください。\n"


@torch.no_grad()
def apply_margin(r, pre, it):
    ms = []
    for swap in (False, True):
        body, c = question_text(it, swap)
        l1, l2 = r.logits_12(r.render(None, pre + body))
        ms.append((l1 - l2) if c == 1 else (l2 - l1))
    return sum(ms) / 2


def sign_p(pos, neg):
    n = pos + neg
    if n == 0:
        return 1.0
    return sum(math.comb(n, j) for j in range(pos, n + 1)) / 2 ** n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2c"]
    r = Runner(args.model, args.dtype)
    out = ROOT / "results" / f"e60_{args.model.split('/')[-1]}.json"

    res = {"model": args.model, "dtype": args.dtype, "rows": {}, "summary": {}}
    for i, it in enumerate(items):
        L = it["defs"][0]
        row = {}
        for k in KS:
            row[f"k{k}"] = apply_margin(r, example_block(items, i, defs, k) + near_prefix(defs, L), it)
        res["rows"][L] = row
        print(L, {c: round(v, 3) for c, v in row.items()}, flush=True)

    rows = list(res["rows"].values())
    n = len(rows)
    for k in KS:
        ms = [row[f"k{k}"] for row in rows]
        res["summary"][f"k{k}"] = {"acc": sum(m > 0 for m in ms) / n, "margin": sum(ms) / n}
    d = [row["k8"] - row["k0"] for row in rows]
    pos = sum(x > 0 for x in d)
    neg = sum(x < 0 for x in d)
    p = sign_p(pos, neg)
    v = "supported" if (pos > neg and p <= 0.05) else "refuted" if pos <= neg else "not_judged"
    res["paired"] = {"pos": pos, "neg": neg, "p": p}
    res["judgment"] = {"examples_raise_apply": v}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(res["summary"], res["paired"], res["judgment"])


if __name__ == "__main__":
    main()
