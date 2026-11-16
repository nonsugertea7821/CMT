"""E10: 定義を、日本語の文ではなく概念式（exp/src/subj.yaml に書いたままの行）で与えたとき、モデルは定義に従うか。

条件:
  none  定義なし
  near  日本語の定義文を、設問の直前に置く（E1 の near と同じ）
  expr_masked  expr から、語そのもの以外の種類の表示名（ja）を外したもの
  expr_masked_i  expr_masked に、限定が参照する個体の行（日曜、本州など）を足したもの
  expr_opaque  expr_masked_i から、core 以外の識別子（subj の種類・動詞・個体の名前）を無意味な記号に置き換えたもの
  expr  概念式を、設問の直前に置く。語の種類と、それがたどる subj の種類・動詞・個体・事実の行をそのまま並べる

測り方は E1 と同じ（二択の次トークンのロジット差、選択肢の順序を入れ替えた2回の平均）。

使い方:
  python e10_expression_given.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from e1_context_injection import Runner  # noqa: E402
import render_expr  # noqa: E402

HEAD = "次の概念式に従うこと。\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--conds", nargs="+", default=["none", "near", "expr", "expr_masked"])
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    R = render_expr.Renderer()
    expr = {w: R.text(w) for it in items for w in it["defs"]}
    masked = {w: R.text(w, mask=True) for it in items for w in it["defs"]}
    masked_i = {w: R.text(w, mask=True, inds=True) for it in items for w in it["defs"]}
    opaque = {w: R.text(w, mask=True, opaque=True, inds=True) for it in items for w in it["defs"]}
    r = Runner(args.model, args.dtype)

    conds = {
        "none": lambda it, body: body,
        "near": lambda it, body: "次の定義に従うこと。\n" + "\n".join(defs[d] for d in it["defs"]) + "\n\n" + body,
        "expr": lambda it, body: HEAD + "\n".join(expr[d] for d in it["defs"]) + "\n\n" + body,
        "expr_masked": lambda it, body: HEAD + "\n".join(masked[d] for d in it["defs"]) + "\n\n" + body,
        # core 以外の識別子を無意味な記号に置き換えたもの（表示名は語そのものと個体だけ）
        # expr_masked に、限定が参照する個体の行を足したもの（expr_opaque と比べる基準）
        "expr_masked_i": lambda it, body: HEAD + "\n".join(masked_i[d] for d in it["defs"]) + "\n\n" + body,
        "expr_opaque": lambda it, body: HEAD + "\n".join(opaque[d] for d in it["defs"]) + "\n\n" + body,
    }
    conds = {k: v for k, v in conds.items() if k in args.conds}
    results = {"args": vars(args), "expr": expr, "masked": masked, "masked_i": masked_i, "opaque": opaque, "items": {}, "summary": {}}
    for name, user in conds.items():
        t0 = time.time()
        for it in items:
            results["items"].setdefault(it["id"], {"group": it["group"]})[name] = r.margin(it, lambda it: None, user)
        print(f"[{name}] {time.time() - t0:.0f}s", flush=True)
    for name in conds:
        row = {}
        for g in args.groups + ["ALL"]:
            rs = [v[name] for v in results["items"].values() if g == "ALL" or v["group"] == g]
            row[g] = {"n": len(rs), "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                      "acc_both": sum(x["both"] for x in rs) / len(rs),
                      "mean_margin": sum(x["margin"] for x in rs) / len(rs)}
        results["summary"][name] = row
    out = ROOT / "results" / f"e10_{args.model.split('/')[-1]}{args.tag}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for g in args.groups + ["ALL"]:
        print(g, {n: round(results["summary"][n][g]["acc"], 2) for n in conds})


if __name__ == "__main__":
    main()
