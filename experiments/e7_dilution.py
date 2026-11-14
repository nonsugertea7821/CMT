"""E7: 定義が効かなくなる原因の切り分け（置き場所・距離・定義の数・用語集内の位置）。

E1 では「定義文を直前に置く」と「用語集に入れる」の間で、定義の数、設問からの距離、
置き場所（利用者の発話 / システムプロンプト）が同時に変わっていた。1つずつ動かす。

条件（定義はすべてシステムプロンプトに置く）:
  sys1          関係する定義だけ
  sys1-far500   関係する定義だけ ＋ 無関係な文章 約500トークン
  sys1-far2000  関係する定義だけ ＋ 無関係な文章 約2000トークン
  gl5 / gl15    関係する定義を含む 5 / 15 定義（他は無作為、順序も無作為）
  gl55-first    全55定義。関係する定義を先頭に置く
  gl55-last     全55定義。関係する定義を末尾（設問の直前）に置く

対象: G2c（再定義で衝突する設問）と、対照として G3・G4（新しい語）。

使い方:
  python e7_dilution.py --model Qwen/Qwen3-4B --dtype bfloat16
"""
import argparse
import json
import random

from e1_context_injection import ROOT, Runner, make_filler

HEADER = "以下は当プロジェクトの用語集である。回答はこの用語集の定義に従うこと。\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--groups", nargs="+", default=["G2c", "G3", "G4"])
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    r = Runner(args.model, args.dtype)
    fill = {n: make_filler(r.tok, n) for n in (500, 2000)}

    def glossary(it, k, where):
        rel = list(it["defs"])
        rng = random.Random(it["id"])
        others = [d for d in defs if d not in rel]
        rng.shuffle(others)
        others = others[: k - len(rel)]
        if where == "first":
            order = rel + others
        elif where == "last":
            order = others + rel
        else:
            order = rel + others
            rng.shuffle(order)
        return HEADER + "\n".join(defs[d] for d in order)

    def far(n):
        return lambda it: glossary(it, len(it["defs"]), "first") + "\n\n以下は参考の文章である。\n" + fill[n]

    conds = {
        "sys1": lambda it: glossary(it, len(it["defs"]), "first"),
        "sys1-far500": far(500),
        "sys1-far2000": far(2000),
        "gl5": lambda it: glossary(it, 5, "random"),
        "gl15": lambda it: glossary(it, 15, "random"),
        "gl55-first": lambda it: glossary(it, len(defs), "first"),
        "gl55-last": lambda it: glossary(it, len(defs), "last"),
    }
    out = ROOT / "results" / f"e7_{args.model.split('/')[-1]}.json"
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for name, sys_fn in conds.items():
        for it in items:
            row = res.setdefault(it["id"], {"group": it["group"]})
            if name in row:
                continue  # 中断からの再開
            row[name] = r.margin(it, sys_fn, lambda it_, body: body)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        line = f"{name:13s}"
        for g, label in (("G2c", "再定義・衝突"), ("G3G4", "新しい語")):
            rs = [v[name] for v in res.values() if v["group"] in g and name in v]
            if rs:
                line += f"  {label}={sum(x['margin'] > 0 for x in rs) / len(rs):.2f}({sum(x['both'] for x in rs) / len(rs):.2f}) n={len(rs)}"
        print(line, flush=True)


if __name__ == "__main__":
    main()
