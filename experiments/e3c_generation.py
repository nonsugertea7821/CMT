"""E3c: 概念ベクトルが、文章を生成させたときの答えにも効くかを測る。

二択ではなく、選択肢を示さずに自由に答えさせる。出力の中で最初に現れる
肯定・否定の表現で判定する。

条件:
  none  何もなし
  text  定義文と適用例4問を文脈に置く
  vec   その設問の概念のベクトルだけ

制約: ベクトルは入力の語の位置にだけ加える。生成中の語には加えない。

使い方:
  python e3c_generation.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8 \
      --vectors results/e3_Qwen2.5-1.5B-Instruct_L8_qa.pt
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, build_delta

YES = ["はい", "当たります", "該当します", "属します", "含まれます"]
NO = ["いいえ", "当たりません", "該当しません", "属しません", "含まれません", "ではありません"]


def judge(text):
    pos = [(text.find(w), "はい") for w in YES if w in text] + [(text.find(w), "いいえ") for w in NO if w in text]
    return min(pos)[1] if pos else "不明"


@torch.no_grad()
def generate(r, inj, prompt, vectors):
    text = r.render(None, prompt)
    if vectors:
        ids, inj.delta = build_delta(r.tok, text, vectors, r.model.config.hidden_size)
    else:
        ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
        inj.delta = None
    out = r.model.generate(ids, max_new_tokens=40, do_sample=False)
    inj.delta = None
    return r.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)


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

    res = {}
    for it in [it for it in data["items"] if it["group"] in ("G2c", "G2k")]:
        c = it["defs"][0]
        q = it["q"][:-2] + "ますか。" if it["q"].endswith("当たるか。") else it["q"][:-3] + "しますか。"
        ask = q + "「はい」か「いいえ」で答え、理由を一文で述べてください。"
        ex = "\n".join(f"問：{e['q']}\n答：{e['correct']}" for e in qa[c])
        prefix = f"次の定義に従うこと。\n{defs[c]}\n\n次の例に従うこと。\n{ex}\n\n"
        row = {"group": it["group"], "correct": it["correct"], "q": ask}
        for cond, (pre, vs) in {"none": ("", None), "text": (prefix, None), "vec": ("", {c: vectors[c]})}.items():
            out = generate(r, inj, pre + ask, vs)
            row[cond] = {"out": out, "judged": judge(out)}
        res[it["id"]] = row
        print(it["id"], it["correct"], {k: row[k]["judged"] for k in ("none", "text", "vec")}, flush=True)

    (ROOT / "results" / "e3c_generation.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for g in ("G2c", "G2k"):
        rs = [v for v in res.values() if v["group"] == g]
        line = f"{g} (n={len(rs)})"
        for cond in ("none", "text", "vec"):
            acc = sum(x[cond]["judged"] == x["correct"] for x in rs) / len(rs)
            unk = sum(x[cond]["judged"] == "不明" for x in rs)
            line += f"  {cond}={acc:.2f}(不明{unk})"
        print(line)


if __name__ == "__main__":
    main()
