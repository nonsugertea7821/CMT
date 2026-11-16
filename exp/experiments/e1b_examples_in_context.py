"""E1b: E3（適用例で学習したベクトル）と公平に比べるための、文章側の対照。

E3 の qa 版は概念あたり4問の適用例を教師に使う。同じ4問を、ベクトルにせず
文章として文脈に置いた場合の正答率を測る。

条件:
  examples       適用例4問と答えを、設問の前に置く
  def+examples   定義文と適用例4問を、設問の前に置く

使い方:
  python e1b_examples_in_context.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

from e1_context_injection import ROOT, Runner, question_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in ("G2c", "G2k")]
    r = Runner(args.model)

    def examples(it):
        return "次の例に従うこと。\n" + "\n".join(
            f"問：{ex['q']}\n答：{ex['correct']}" for ex in qa[it["defs"][0]]
        )

    conds = {
        "examples": lambda it, body: examples(it) + "\n\n" + body,
        "def+examples": lambda it, body: "次の定義に従うこと。\n"
        + defs[it["defs"][0]]
        + "\n\n"
        + examples(it)
        + "\n\n"
        + body,
    }
    res = {it["id"]: {"group": it["group"]} for it in items}
    for name, fn in conds.items():
        for it in items:
            res[it["id"]][name] = r.margin(it, lambda _: None, fn)
    summary = {}
    for g in ("G2c", "G2k"):
        summary[g] = {}
        for name in conds:
            rs = [v[name] for v in res.values() if v["group"] == g]
            summary[g][name] = {
                "n": len(rs),
                "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                "acc_both": sum(x["both"] for x in rs) / len(rs),
                "mean_margin": sum(x["margin"] for x in rs) / len(rs),
            }
            s = summary[g][name]
            print(f"{g} {name:13s} acc={s['acc']:.2f} both={s['acc_both']:.2f} m={s['mean_margin']:+.2f}")
    for name in conds:
        n = sum(
            res[f"G2c-{i:02d}"][name]["margin"] > 0 and res[f"G2k-{i:02d}"][name]["margin"] > 0
            for i in range(1, 25)
        )
        print(f"{name}: 衝突・非衝突とも正答の概念数 {n}/24")
    out = ROOT / "results" / f"e1b_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps({"items": res, "summary": summary}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
