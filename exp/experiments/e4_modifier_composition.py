"""E4: 修飾（類種差の種差）のベクトルは、学習していない上位概念に付けても通用するか。

概念 = 上位概念 + 修飾。修飾を表す語（甲種/乙種 など）ごとに1本のベクトルを持ち、
その語が現れた位置で中間層に加える。上位概念の語には何も加えない。

学習: 修飾の組ごとに、2つの上位概念の上の適用例8問で、組の2本を同時に学習する。
評価: 学習に使っていない別の2つの上位概念の上で、兄弟を区別できるかを測る。

条件:
  none  何もなし
  text  修飾の定義文を設問の直前に置く
  vec   修飾のベクトルだけ

使い方:
  python e4_modifier_composition.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import Injector, label_mask


def encode(r, prompt, cont, labels_):
    """(入力ID, 損失用ラベル, 修飾ごとの位置マスク) を返す。"""
    full = prompt + cont
    n_prompt = len(r.tok(prompt, add_special_tokens=False).input_ids)
    ids = torch.tensor([r.tok(full, add_special_tokens=False).input_ids])
    tgt = ids.clone()
    tgt[:, :n_prompt] = -100
    masks = {}
    for lab in labels_:
        _, m = label_mask(r.tok, full, lab)
        masks[lab] = torch.tensor(m, dtype=torch.float32).view(1, -1, 1)
    return ids, tgt, masks


def delta_of(masks, vecs):
    return sum(masks[lab] * vecs[lab].view(1, 1, -1) for lab in vecs)


def train_pair(r, inj, pair, steps, lr):
    d = r.model.config.hidden_size
    vecs = {m: torch.zeros(d, requires_grad=True) for m in pair["modifiers"]}
    opt = torch.optim.Adam(list(vecs.values()), lr=lr)
    batch = []
    for ex in pair["train"]:
        for swap in (False, True):
            body, correct_no = question_text(ex, swap)
            batch.append(encode(r, r.render(None, body), str(correct_no), pair["modifiers"]))
    first = last = None
    for _ in range(steps):
        opt.zero_grad()
        total = 0.0
        for ids, tgt, masks in batch:
            inj.delta = delta_of(masks, vecs)
            loss = r.model(ids, labels=tgt).loss / len(batch)
            loss.backward()
            total += loss.item()
        opt.step()
        first = total if first is None else first
        last = total
    inj.delta = None
    return {m: v.detach() for m, v in vecs.items()}, first, last


@torch.no_grad()
def evaluate(r, inj, ex, prefix, vecs, mods):
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(ex, swap)
        ids, _, masks = encode(r, r.render(None, prefix + body), "", mods)
        inj.delta = delta_of(masks, vecs) if vecs else None
        last = r.model(ids).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    args = ap.parse_args()
    pairs = json.loads((ROOT / "data" / "modifiers_ja.json").read_text(encoding="utf-8"))["pairs"]
    r = Runner(args.model)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)

    res, all_vecs = [], {}
    for pair in pairs:
        mods = pair["modifiers"]
        t0 = time.time()
        vecs, first, last = train_pair(r, inj, pair, args.steps, args.lr)
        all_vecs.update(vecs)
        print(f"[train] {mods}: loss {first:.2f} -> {last:.2f}  {time.time() - t0:.0f}s", flush=True)
        prefix = "次の定義に従うこと。\n" + "\n".join(pair["defs"].values()) + "\n\n"
        for split in ("train", "test"):
            for ex in pair[split]:
                res.append(
                    {
                        "pair": "/".join(mods),
                        "split": split,
                        "q": ex["q"],
                        "none": evaluate(r, inj, ex, "", None, mods),
                        "text": evaluate(r, inj, ex, prefix, None, mods),
                        "vec": evaluate(r, inj, ex, "", vecs, mods),
                    }
                )
    (ROOT / "results" / "e4_modifier_composition.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    torch.save(all_vecs, ROOT / "results" / "e4_modifier_vectors.pt")

    print("\n表記: 正答率(順序を入れ替えても両方正答する率)")
    keys = ["全体"] + sorted({x["pair"] for x in res})
    for split, title in (("train", "学習した上位概念"), ("test", "学習していない上位概念")):
        print(f"\n{title}")
        for k in keys:
            rs = [x for x in res if x["split"] == split and (k == "全体" or x["pair"] == k)]
            line = f"  {k:8s} n={len(rs):2d}"
            for cond in ("none", "text", "vec"):
                acc = sum(x[cond]["margin"] > 0 for x in rs) / len(rs)
                both = sum(x[cond]["both"] for x in rs) / len(rs)
                line += f"  {cond}={acc:.2f}({both:.2f})"
            print(line)


if __name__ == "__main__":
    main()
