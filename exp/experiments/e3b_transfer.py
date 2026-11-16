"""E3b: 学習済みの概念ベクトルの転移と干渉を測る。

入力: e3_concept_vectors.py が保存したベクトル（results/*.pt）。

測るもの:
  1. 形式の転移: 学習時と違う設問形式でも効くか。
       orig   学習時と同じ形式（〜に当たるか → はい/いいえ）
       fill   空欄補充（〜に＿＿。 → 当たる/当たらない）
       truth  正誤判定（「〜に当たる。」 → 正しい/誤り）
  2. 干渉: 24概念のベクトルを同時に入れても効くか（vec_all）。
  3. 局所性: 無関係な設問（G1）の答えが、全ベクトルを入れても変わらないか。

条件:
  none     何もなし
  text     定義文と適用例4問を文脈に置く
  vec      その設問の概念のベクトルだけ
  vec_all  全概念のベクトル

使い方:
  python e3b_transfer.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8 \
      --vectors results/e3_Qwen2.5-1.5B-Instruct_L8_qa.pt
"""
import argparse
import json

import torch

import e1_context_injection as e1
from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import Injector, build_delta

e1.INSTRUCTION["truth"] = "次の文が正しいか誤りかを選び、番号だけで答えてください。"


def reformat(item, fmt):
    q, yes = item["q"], item["correct"] == "はい"
    verb = "属する" if q.endswith("属するか。") else "当たる"
    neg = {"属する": "属さない", "当たる": "当たらない"}[verb]
    assert q.endswith(verb + "か。"), q
    stem = q[: -len(verb + "か。")]
    if fmt == "orig":
        return item
    if fmt == "fill":
        c, w = (verb, neg) if yes else (neg, verb)
        return {**item, "type": "fill", "q": stem + "＿＿。", "correct": c, "wrong": w}
    if fmt == "truth":
        c, w = ("正しい", "誤り") if yes else ("誤り", "正しい")
        return {**item, "type": "truth", "q": "「" + stem + verb + "。」", "correct": c, "wrong": w}


@torch.no_grad()
def run(r, inj, item, prefix, vectors):
    d_model = r.model.config.hidden_size
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(item, swap)
        text = r.render(None, prefix + body)
        if vectors:
            ids, inj.delta = build_delta(r.tok, text, vectors, d_model)
        else:
            ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
            inj.delta = None
        last = r.model(ids).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--vectors", required=True)
    args = ap.parse_args()

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]
    defs = data["defs"]
    vectors = torch.load(args.vectors)
    r = Runner(args.model)
    inj = Injector(r.model, args.layer)

    def text_prefix(it):
        c = it["defs"][0]
        ex = "\n".join(f"問：{e['q']}\n答：{e['correct']}" for e in qa[c])
        return f"次の定義に従うこと。\n{defs[c]}\n\n次の例に従うこと。\n{ex}\n\n"

    res = {}
    g2 = [it for it in data["items"] if it["group"] in ("G2c", "G2k")]
    for fmt in ("orig", "fill", "truth"):
        for it0 in g2:
            it = reformat(it0, fmt)
            c = it["defs"][0]
            res[f"{fmt}/{it['id']}"] = {
                "fmt": fmt,
                "group": it["group"],
                "none": run(r, inj, it, "", None),
                "text": run(r, inj, it, text_prefix(it), None),
                "vec": run(r, inj, it, "", {c: vectors[c]}),
                "vec_all": run(r, inj, it, "", vectors),
            }
        print(f"[{fmt}] done", flush=True)
    for it in [it for it in data["items"] if it["group"] == "G1"]:
        res[f"orig/{it['id']}"] = {
            "fmt": "orig",
            "group": "G1",
            "none": run(r, inj, it, "", None),
            "vec_all": run(r, inj, it, "", vectors),
        }

    out = ROOT / "results" / "e3b_transfer.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    for fmt in ("orig", "fill", "truth"):
        for g in ("G2c", "G2k"):
            rs = [v for v in res.values() if v["fmt"] == fmt and v["group"] == g]
            line = f"{fmt:5s} {g}"
            for cond in ("none", "text", "vec", "vec_all"):
                acc = sum(x[cond]["margin"] > 0 for x in rs) / len(rs)
                both = sum(x[cond]["both"] for x in rs) / len(rs)
                line += f"  {cond}={acc:.2f}({both:.2f})"
            print(line)
    g1 = [v for v in res.values() if v["group"] == "G1"]
    for cond in ("none", "vec_all"):
        acc = sum(x[cond]["margin"] > 0 for x in g1) / len(g1)
        m = sum(x[cond]["margin"] for x in g1) / len(g1)
        print(f"G1 {cond}: acc={acc:.2f} m={m:+.2f}")
    print("表記: 正答率(順序を入れ替えても両方正答する率)")


if __name__ == "__main__":
    main()
