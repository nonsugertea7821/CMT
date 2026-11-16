"""E13: 下層の具象概念の判定をモデルにさせず、体系で決める。

モデルには、語の概念式（exp/src/subj.yaml）の1行「上位 ∧ 限定」を、モデルが元から持つ水準の問いに分けて聞く。
  上位   「対象は〈上位の表示名〉に当たるか」
  限定   「〈限定を自然言語にした文〉は成り立つか」（否定 ¬ は聞かずに、体系の側で反転する）
帰属は 上位 ∧ 限定（否定なら ¬限定）で、記号的に決める。モデルは語そのもの（再定義された語）を見ない。

条件:
  none      定義なしで即答（E1 の none と同じ）
  near      日本語の定義文を設問の直前に置いて即答（E1 の near と同じ）
  symbolic  上の分け方で事実だけ答えさせ、帰属は体系で決める
  symbolic_mod  上位の問いを使わず、限定の答えだけで帰属を決める（上位がモデルにとって抽象すぎる場合の比較）

設問は「〈対象〉は、〈語〉に当たるか。」の形のものだけ使う（週の2問は形が違うので外す）。
測り方: 事実の問いは、はい／いいえの二択の次トークンのロジット差を、選択肢の順序を入れ替えた2回で平均する。

使い方:
  python e13_fact_then_symbolic.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json
import re
import sys

import torch

from e1_context_injection import ROOT, Runner, question_text

sys.path.insert(0, str(ROOT))
import render_expr  # noqa: E402

PAT = re.compile(r"^(.+)は、(.+)に当たるか。$")
WORDS = {"lt": "未満", "le": "以下", "ge": "以上", "gt": "より大きい"}


def amount_text(v):
    if isinstance(v, dict):
        (op, a), = v.items()
        return f"{a}{WORDS[op]}"
    return f"{v}"


def condition(R, nid):
    """語の種類の1行から、(上位の表示名, 限定の文, 否定か) を作る。"""
    T, S = R.T, R.S
    n = T.N[nid]
    genus = render_expr._ja(T, n["extends"], S)
    m = n["mod"][0] if isinstance(n["mod"], list) else n["mod"]
    verb = render_expr._ja(T, m["of"][0], S)
    pos = m["of"][1]
    other = render_expr._ja(T, m["with"], S) if "with" in m else "何か"
    at = m.get("at") or {}
    if "amount" in at and pos == "to" and m["of"][0].split(".")[-1] in ("v_depend", "v_measure"):
        # 量の性質: 依存する(年齢（歳）（<25）, これ) → 対象の年齢（歳）は25未満である
        text = f"対象の{other}は{amount_text(at['amount'])}である"
    else:
        if "amount" in at:
            other += f"（{amount_text(at['amount'])}）"
        if "count" in at:
            (op, a), = at["count"].items() if isinstance(at["count"], dict) else (("eq", at["count"]),)
            other += f"（{a}個{WORDS.get(op, '')}）"
        base = m["of"][0].split(".")[-1]
        if base == "v_depend" and pos == "to":
            text = f"対象は{other}を持つ"
        elif base == "v_measure" and pos == "from":
            text = f"対象は{other}を表す"
        elif pos == "from":
            text = f"対象が{other}に対して「{verb}」という関係が成り立つ"
        else:
            text = f"{other}が対象に対して「{verb}」という関係が成り立つ"
    return genus, text, bool(m.get("neg"))


@torch.no_grad()
def yes_margin(r, body):
    """はい − いいえ のロジット差（順序を入れ替えた2回の平均）と、2回とも同じ向きか。"""
    ms = []
    for swap in (False, True):
        text, correct_no = question_text({"type": "yesno", "q": body, "correct": "はい", "wrong": "いいえ"}, swap)
        ids = r.tok(r.render(None, text), return_tensors="pt", add_special_tokens=False).input_ids
        last = r.model(ids).logits[0, -1]
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return sum(ms) / 2, (ms[0] > 0) == (ms[1] > 0)


@torch.no_grad()
def direct(r, item, defs, use_def):
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(item, swap)
        if use_def:
            body = "次の定義に従うこと。\n" + "\n".join(defs[d] for d in item["defs"]) + "\n\n" + body
        ids = r.tok(r.render(None, body), return_tensors="pt", add_special_tokens=False).input_ids
        last = r.model(ids).logits[0, -1]
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    args = ap.parse_args()

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups and PAT.match(it["q"])]
    R = render_expr.Renderer()
    r = Runner(args.model)

    res = {}
    for it in items:
        subj, word = PAT.match(it["q"]).groups()
        assert it["defs"][0] in word, it["id"]
        word = it["defs"][0]
        genus, cond, neg = condition(R, R.by_ja[word])
        q_genus = f"対象: {subj}\n対象は「{genus}」に当たるか。"
        q_mod = f"対象: {subj}\n次のことは成り立つか。\n{cond}"
        mg, sg = yes_margin(r, q_genus)
        mm, sm = yes_margin(r, q_mod)
        member = (mg > 0) and ((mm > 0) != neg)
        ok = member == (it["correct"] == "はい")
        ok_mod = ((mm > 0) != neg) == (it["correct"] == "はい")
        res[it["id"]] = {
            "group": it["group"],
            "none": direct(r, it, defs, False),
            "near": direct(r, it, defs, True),
            # 帰属は記号で決めるのでロジット差はない。正誤を ±1 で、順序に頑健かを both で記録する
            "symbolic": {"margin": 1.0 if ok else -1.0, "both": ok and sg and sm},
            "symbolic_mod": {"margin": 1.0 if ok_mod else -1.0, "both": ok_mod and sm},
            "facts": {"genus": {"q": q_genus, "yes_margin": mg}, "mod": {"q": q_mod, "yes_margin": mm, "neg": neg},
                      "member": member},
        }
        print(f"{it['id']} {word}: 上位 {mg:+.2f} 限定 {mm:+.2f}{' (¬)' if neg else ''} → {'属する' if member else '属さない'} "
              f"{'正' if ok else '誤'}", flush=True)

    summary = {}
    for g in sorted({v["group"] for v in res.values()}):
        summary[g] = {}
        for c in ("none", "near", "symbolic", "symbolic_mod"):
            rs = [v[c] for v in res.values() if v["group"] == g]
            summary[g][c] = {"n": len(rs), "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                             "acc_both": sum(x["both"] for x in rs) / len(rs)}
    out = ROOT / "results" / f"e13_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps({"args": vars(args), "items": res, "summary": summary}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    for g, row in summary.items():
        print(f"\n{g} (n={row['none']['n']})")
        for c, s in row.items():
            print(f"  {c:9s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}")


if __name__ == "__main__":
    main()
