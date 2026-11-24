"""E48: 同じ項目で、番号で選ぶ形と名前で答える形を比べる（h_verdict_by_question_format #724）。

系列:
  E42（この枝）は、T ごとの二択（E41）から番号で選ぶ比べに形を変え、extends の acc が 0.417 → 0.708 だった（判定しない）。
  E43（seed 1、番号で選ぶ形）では decoy 0.125、E47（seed 2、名前で答える形）では decoy 0.875 だった。
  この差は、形の差とも、項目（seed）の差とも読める。
  ここでは、E47 と同じ項目（seed 2）・同じ並べ方で、番号で選ぶ形だけを測り、E47 の値と比べる。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。
項目: e43_reads_by_word_compare.make_items(seed=2)。条件は extends・decoy・control（E47 と同じ）。
  依存する側の定義を D、しない側を O と呼ぶ（E43 の P・Q）。

設問（E43 と同じ番号の形）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わるのはどちらですか。番号で答えてください。」
  定義の集まりの後に、1. と 2. で 2 つの名前。
  名前の割り当て 2 通り × 定義の並び 2 通り（D が先 / O が先）× 選択肢の順 2 通り = 8 回。
  d = logit(D の番号) − logit(O の番号)。
  定義の並びごとに、名前の割り当てと選択肢の順の 4 回の d を平均する: pair = [D が先の平均, O が先の平均]。
  E47 の pair は、名前の割り当て 2 回の平均（名前で答える形に選択肢の順はない）。
  acc = pair の平均 > 0 の割合。order_robust = pair の 2 つがどちらも > 0 の割合。

判定（事前登録。24 項目。比べる相手は E47 の名前の形: extends 0.9583333、decoy 0.875、control 0.9166667）:
  h_verdict_by_question_format（判定は設問の形に頼る）:
    支持: decoy の acc が 0.625 以下（E47 の 0.875 より 0.25 以上低い）。
    反証: extends の acc が 0.875 以上、かつ decoy の acc が 0.792 以上（どちらも E47 との差が 0.083 以下）。
    それ以外: 判定しない。
  参考（判定しない）: control の acc、各条件の order_robust。

開示:
  - E42・E43・E46・E47 の結果を見てから、この手順を書いた。E47 の値はこの判定の比べる相手として固定した。
  - 主に decoy で比べるのは、E43 と E47 の差が decoy で最も大きかったから（見てから選んだ）。
  - この枝の E42 は判定しないまま残っている。E48 は E42 の訂正ではなく、同じ仮説への 2 つ目の測り。
  - 結果ファイルが E42 のものより後に来るので、この PR は自動マージの条件（事前登録が結果より前）に合わない。手で見る。

使い方:
  python e48_format_same_items.py --model Qwen/Qwen3-4B
  出力: results/e48_<model>.json（途中保存: results/e48_<model>.partial.json）
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e43_reads_by_word_compare import CONDS, HEAD, make_items, snippet


@torch.no_grad()
def d_one(r, it, cond, swap_names, d_first, d_opt_first):
    it = dict(it, P=it["Q"], Q=it["P"]) if swap_names else dict(it)
    it["p_first"] = d_first
    o = [it["P"], it["Q"]] if d_opt_first else [it["Q"], it["P"]]
    body = f"{HEAD.format(A=it['A'])}\n{snippet(it, cond)}\n1. {o[0]}\n2. {o[1]}"
    l1, l2 = r.logits_12(r.render(None, body))
    return (l1 - l2) if d_opt_first else (l2 - l1)


def summ(rows):
    vs = [v["pair"] for v in rows.values()]
    n = len(vs)
    return {"acc": sum(sum(e) > 0 for e in vs) / n,
            "order_robust": sum(all(x > 0 for x in e) for e in vs) / n,
            "mean_margin": sum(sum(e) / 2 for e in vs) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e48_{short}.partial.json"
    items = make_items(seed=2)
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "raw": {}, "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        if cond in out["raw"]:
            continue
        out["raw"][cond] = {str(it["id"]): [d_one(r, it, cond, s, f, o)
                                            for f in (True, False) for s in (False, True) for o in (True, False)]
                            for it in items}
        print(cond, "done", flush=True)
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [sum(d[:4]) / 4, sum(d[4:]) / 4], "d8": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    s = out["summary"]
    v = "not_judged"
    if s["decoy"]["acc"] <= 0.6251:
        v = "supported"
    elif s["extends"]["acc"] >= 0.8749 and s["decoy"]["acc"] >= 0.7916:
        v = "refuted"
    out["judgment"] = {"verdict_by_question_format": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e48_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
