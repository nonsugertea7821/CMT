"""E5: 文章の側で再定義に従わせる手段（言い換え）を比べる。

対象は一般語の再定義（G2c 衝突する設問、G2k 衝突しない設問）。ベクトルは使わない。

条件:
  near           定義文を設問の直前に置く（E1 と同じ。基準）
  rename_semi    語を、元の語が見える新しい語に改名する（社員 → P社員）。定義文と設問の両方で置き換える
  rename_opaque  語を、元の語が見えない新しい語に改名する（社員 → 用語08）
  inline         改名せず、設問中の語の直後に定義を展開する（「社員」（定義…））。定義文は別に置かない
  near+inline    定義文を直前に置き、設問中でも展開する

使い方:
  python e5_paraphrase.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

from e1_context_injection import ROOT, Runner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in ("G2c", "G2k")]
    concepts = sorted({it["defs"][0] for it in items})
    r = Runner(args.model)

    def sub(text, old, new):
        # 「翌週」のように別の語の一部である箇所は置き換えない
        return text.replace(old, new).replace("翌" + new, "翌" + old)

    def body(c):
        return defs[c].split("：", 1)[1]

    def near(it, q):
        return "次の定義に従うこと。\n" + defs[it["defs"][0]] + "\n\n" + q

    def rename(new_of):
        def fn(it, q):
            c = it["defs"][0]
            return "次の定義に従うこと。\n" + sub(defs[c], c, new_of(c)) + "\n\n" + sub(q, c, new_of(c))

        return fn

    def inline(it, q):
        c = it["defs"][0]
        return sub(q, c, f"「{c}」（{body(c)}）")

    conds = {
        "near": near,
        "rename_semi": rename(lambda c: "P" + c),
        "rename_opaque": rename(lambda c: f"用語{concepts.index(c) + 1:02d}"),
        "inline": inline,
        "near+inline": lambda it, q: "次の定義に従うこと。\n" + defs[it["defs"][0]] + "\n\n" + inline(it, q),
    }
    res = {it["id"]: {"group": it["group"]} for it in items}
    for name, fn in conds.items():
        for it in items:
            # question_text は設問の本文に指示と選択肢を付ける。語の置き換えは本文全体に対して行う
            res[it["id"]][name] = r.margin(it, lambda _: None, lambda it_, b, fn=fn: fn(it_, b))
        print(f"[{name}] done", flush=True)

    print("表記: 正答率(順序を入れ替えても両方正答する率)")
    for name in conds:
        line = f"{name:14s}"
        for g in ("G2c", "G2k"):
            rs = [v[name] for v in res.values() if v["group"] == g]
            line += f"  {g}={sum(x['margin'] > 0 for x in rs) / len(rs):.2f}({sum(x['both'] for x in rs) / len(rs):.2f})"
        n = sum(
            res[f"G2c-{i:02d}"][name]["margin"] > 0 and res[f"G2k-{i:02d}"][name]["margin"] > 0
            for i in range(1, 25)
        )
        print(line + f"  両方正答の概念数={n}/24")
    (ROOT / "results" / f"e5_{args.model.split('/')[-1]}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
