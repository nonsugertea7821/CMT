"""E6: 概念ベクトルは、語の使い方をまたいで効くか（「定義する」側の測定）。

再定義とは、その語のあらゆる使い方が共有している推論を変えることだと考える。
1つの使い方（定義する / 適用する）で学習したベクトルが、別の使い方も変えるかを測る。
「適用する」側は e3_concept_vectors.py と e3b_transfer.py が測る。ここでは「定義する」側を測る。

測るもの（概念ごと）:
  define_choice  「語」の定義として、プロジェクトの定義と一般の定義のどちらを選ぶか（二択）。
                 選択肢は定義文そのものではなく言い換え（data/definition_choice_ja.json）。
  define_nll     「語の定義を答えよ」に対して、プロジェクトの定義文を出力するときの
                 1トークンあたりの負の対数尤度。小さいほど定義文を出しやすい。

使い方:
  python e6_cross_use.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8 \
      --vectors none results/e3_..._defonly.pt results/e3_..._qa.pt
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import TEMPLATES, Injector, label_mask

INSTR = "「{L}」の定義として正しいほうを選び、番号だけで答えてください。"


def delta(r, text, label, v):
    ids, mask = label_mask(r.tok, text, label)
    ids = torch.tensor([ids])
    if v is None:
        return ids, None
    return ids, torch.tensor(mask, dtype=torch.float32).view(1, -1, 1) * v.view(1, 1, -1)


@torch.no_grad()
def define_choice(r, inj, label, pair, v):
    ms = []
    for swap in (False, True):
        opts = [pair["project"], pair["ordinary"]]
        if swap:
            opts.reverse()
        body = f"{INSTR.format(L=label)}\n1. {opts[0]}\n2. {opts[1]}"
        ids, inj.delta = delta(r, r.render(None, body), label, v)
        last = r.model(ids).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l2 - l1) if swap else (l1 - l2))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


@torch.no_grad()
def define_nll(r, inj, label, definition, v):
    total = 0.0
    for t in TEMPLATES:
        prompt = r.render(None, t.format(L=label))
        n_prompt = len(r.tok(prompt, add_special_tokens=False).input_ids)
        ids, inj.delta = delta(r, prompt + definition, label, v)
        labels = ids.clone()
        labels[:, :n_prompt] = -100
        total += r.model(ids, labels=labels).loss.item()
        inj.delta = None
    return total / len(TEMPLATES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--vectors", nargs="+", required=True, help="ベクトルのファイル。none は何も加えない")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    defs = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))["defs"]
    choice = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    r = Runner(args.model)
    inj = Injector(r.model, args.layer)

    out = {}
    for path in args.vectors:
        vectors = None if path == "none" else torch.load(path)
        rows = {}
        for c, pair in choice.items():
            v = None if vectors is None else vectors[c]
            rows[c] = {
                "define_choice": define_choice(r, inj, c, pair, v),
                "define_nll": define_nll(r, inj, c, defs[c], v),
            }
        out[path] = rows
        n = len(rows)
        acc = sum(x["define_choice"]["margin"] > 0 for x in rows.values()) / n
        both = sum(x["define_choice"]["both"] for x in rows.values()) / n
        m = sum(x["define_choice"]["margin"] for x in rows.values()) / n
        nll = sum(x["define_nll"] for x in rows.values()) / n
        print(f"{path}\n  define_choice acc={acc:.2f} both={both:.2f} m={m:+.2f}   define_nll={nll:.2f}", flush=True)
    (ROOT / "results" / f"e6_cross_use{args.tag}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
