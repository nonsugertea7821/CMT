"""E20: 適用で学習した概念ベクトルは、「説明する」使い方に転移するか（h_apply_does_not_transfer_to_explain, #35）。

系列: E6 は、適用（qa）で学習したベクトルが、定義の言い換え（paraphrase）と暗唱（recite）に
転移しないことを観察した（h_apply_does_not_transfer_to_paraphrase, h_apply_does_not_transfer_to_recite は支持）。
使い方のうち「説明」（usage_explain = 適用に、理由を発話することが時間的な部分として加わる）だけが残っている。

ベクトル（E3 の記録をそのまま使う。学習しない）:
  none    何も加えない
  qa      results/e3_<model>_L8_qa.pt      （適用の例で学習。判定に使う）
  defqa   results/e3_<model>_L8_defqa.pt   （定義と適用の両方で学習。参考）
加える位置: 文中の概念の語のトークン位置（E3・E6 と同じ）。層 8。

設問: concepts_ja.json の G2c（再定義が元の意味と衝突する 24 問）。理由の選択肢は
definition_choice_ja.json の言い換え（project / ordinary）。選択肢の順を入れ替えた2回の平均の差（margin）。

測るもの（設問ごと）:
  apply           E3 と同じ二択（操作の確かめ。ベクトルが適用を変えているか）
  explain         答えを示したうえで、その判断の理由として正しいほうを選ばせる（判定に使う）:
                    次の問いの答えは「{correct}」です。そう判断する理由として正しいほうを選び、番号だけで答えてください。
                    {q}
                    1. 「{L}」は{project}を指すから
                    2. 「{L}」は{ordinary}を指すから
  explain_noans   答えを示さずに、同じ二つの理由から選ばせる（参考）

判定（事前登録。acc は margin > 0 の割合、24 問）:
  前提（操作の確かめ）: apply の acc が qa で none より 0.25 以上高い。
  前提（天井）: explain の acc が none で 0.75 未満。
  前提のどちらかが崩れたら、判定しない（仮説は未検証のまま、観察だけ書く）。
  転移する（反証）: explain の acc が qa で 0.75 以上、かつ none より 0.25 以上高い。
  転移しない（支持）: それ以外。
  defqa と explain_noans は判定に使わない。

使い方:
  python e20_explain_transfer.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e20_<model>_L8.json
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, build_delta, eval_item

EXPLAIN = "次の問いの答えは「{A}」です。そう判断する理由として正しいほうを選び、番号だけで答えてください。"
EXPLAIN_NOANS = "次の問いに答えるときの理由として正しいほうを選び、番号だけで答えてください。"


@torch.no_grad()
def choice(r, inj, head, item, label, pair, v):
    d_model = r.model.config.hidden_size
    ms = []
    for swap in (False, True):
        opts = [f"「{label}」は{pair['project']}を指すから", f"「{label}」は{pair['ordinary']}を指すから"]
        if swap:
            opts.reverse()
        body = f"{head}\n{item['q']}\n1. {opts[0]}\n2. {opts[1]}"
        text = r.render(None, body)
        if v is None:
            ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
            inj.delta = None
        else:
            ids, inj.delta = build_delta(r.tok, text, {label: v}, d_model)
        last = r.model(ids).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l2 - l1) if swap else (l1 - l2))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def summarize(rows, key):
    n = len(rows)
    return {
        "n": n,
        "acc": sum(x[key]["margin"] > 0 for x in rows.values()) / n,
        "acc_both": sum(x[key]["both"] for x in rows.values()) / n,
        "mean_margin": sum(x[key]["margin"] for x in rows.values()) / n,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    pairs = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    items = [x for x in data["items"] if x["group"] == "G2c"]
    r = Runner(args.model)
    inj = Injector(r.model, args.layer)
    conds = {
        "none": None,
        "qa": ROOT / "results" / f"e3_{short}_L{args.layer}_qa.pt",
        "defqa": ROOT / "results" / f"e3_{short}_L{args.layer}_defqa.pt",
    }
    out = {"args": vars(args), "items": {}, "summary": {}}
    for cname, path in conds.items():
        vectors = None if path is None else torch.load(path)
        rows = {}
        for it in items:
            label = it["defs"][0]
            v = None if vectors is None else vectors[label]
            rows[it["id"]] = {
                "apply": eval_item(r, inj, it, data["defs"], vectors or {}, False, vectors is not None),
                "explain": choice(r, inj, EXPLAIN.format(A=it["correct"]), it, label, pairs[label], v),
                "explain_noans": choice(r, inj, EXPLAIN_NOANS, it, label, pairs[label], v),
            }
        out["items"][cname] = rows
        out["summary"][cname] = {k: summarize(rows, k) for k in ("apply", "explain", "explain_noans")}
        print(cname, json.dumps(out["summary"][cname], ensure_ascii=False), flush=True)
    s = out["summary"]
    pre_apply = s["qa"]["apply"]["acc"] - s["none"]["apply"]["acc"] >= 0.25
    pre_ceiling = s["none"]["explain"]["acc"] < 0.75
    transfer = s["qa"]["explain"]["acc"] >= 0.75 and s["qa"]["explain"]["acc"] - s["none"]["explain"]["acc"] >= 0.25
    out["judgment"] = {
        "pre_apply": pre_apply,
        "pre_ceiling": pre_ceiling,
        "verdict": ("not_judged" if not (pre_apply and pre_ceiling) else ("transfer" if transfer else "no_transfer")),
    }
    print(json.dumps(out["judgment"]), flush=True)
    (ROOT / "results" / f"e20_{short}_L{args.layer}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
