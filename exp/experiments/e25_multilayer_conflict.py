"""E25: 複数の層に分けたベクトルは、元の意味と食い違う再定義への追従を上げるか。

E24 と同じ組（data/modifiers_conflict_ja.json）・同じ位置（修飾の語のトークン位置）・同じ教師
（組の学習用の 8 問 × 2 順序）・同じ step と lr。変えるのは層だけ: E24 は層8の1本、
E25 は層 2〜13（E8 と同じ範囲）に1本ずつ、修飾ごとに [12, 次元] のベクトルを学習する。
大きさへの罰則は E24 と同じく置かない。

E23・E24 では、損失が ln 2 ≈ 0.69 付近で止まり、元の意味を打ち消すが逆にはしなかった。
層の数だけを変えて、この止まりが層の数によるかを見る。

条件（学習用と学習していない上位の両方で測る）:
  none   何もなし
  text   修飾の定義文を設問の直前に置く
  multi  修飾の語の位置に、層ごとのベクトルを足す

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）。

判定（学習していない上位の 24 問を合わせて）:
  前提1: 学習用の 24 問で multi の accuracy ≥ 0.75。満たさなければ inconclusive（学習が収まっていない）。
  前提2: 学習していない上位で none の accuracy ≤ 0.5。満たさなければ inconclusive。
  raise     multi の accuracy − none の accuracy ≥ 0.20、かつ multi の order_robust_accuracy > none
  no_raise  それ以外
  E24 の mod との比較は記録するが、判定には使わない。

使い方:
  python e25_multilayer_conflict.py --model Qwen/Qwen2.5-1.5B-Instruct --layers 2-13
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner, question_text
from e4_modifier_composition import encode
from e8_multilayer import MultiInjector
from e22_qualification_unseen import parent_of, summarize


def set_deltas(inj, masks, vecs):
    inj.deltas = {L: sum(masks[lab] * vecs[lab][i].view(1, 1, -1) for lab in vecs)
                  for i, L in enumerate(inj.layers)}


def train_pair(r, inj, pair, steps, lr):
    d = r.model.config.hidden_size
    vecs = {m: torch.zeros(len(inj.layers), d, requires_grad=True) for m in pair["modifiers"]}
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
            set_deltas(inj, masks, vecs)
            loss = r.model(ids, labels=tgt).loss / len(batch)
            loss.backward()
            total += loss.item()
        opt.step()
        first = total if first is None else first
        last = total
    inj.deltas = None
    return {m: v.detach() for m, v in vecs.items()}, first, last


@torch.no_grad()
def evaluate(r, inj, ex, prefix, vecs):
    labels = list(vecs) if vecs else []
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(ex, swap)
        ids, _, masks = encode(r, r.render(None, prefix + body), "", labels)
        if vecs:
            set_deltas(inj, masks, vecs)
        last = r.model(ids).logits[0, -1]
        inj.deltas = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layers", required=True)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    args = ap.parse_args()
    lo, hi = map(int, args.layers.split("-"))
    pairs = json.loads((ROOT / "data" / "modifiers_conflict_ja.json").read_text(encoding="utf-8"))["pairs"]
    r = Runner(args.model)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = MultiInjector(r.model, list(range(lo, hi + 1)))

    items, train_log = [], {}
    for pair in pairs:
        mods = pair["modifiers"]
        t0 = time.time()
        vecs, first, last = train_pair(r, inj, pair, args.steps, args.lr)
        train_log["/".join(mods)] = {"n_items": len(pair["train"]), "loss_first": first, "loss_last": last,
                                     "norms": {k: v.norm(dim=1).tolist() for k, v in vecs.items()}}
        print(f"[train] {mods}: loss {first:.2f} -> {last:.2f}  {time.time() - t0:.0f}s", flush=True)
        prefix = "次の定義に従うこと。\n" + "\n".join(pair["defs"].values()) + "\n\n"
        for split in ("train", "test"):
            parents = pair[f"{split}_parents"]
            for ex in pair[split]:
                g = parent_of(ex, parents)
                row = {"pair": "/".join(mods), "split": split, "parent": g, "q": ex["q"],
                       "none": evaluate(r, inj, ex, "", None),
                       "text": evaluate(r, inj, ex, prefix, None),
                       "multi": evaluate(r, inj, ex, "", vecs)}
                items.append(row)
                print(split, g, {k: round(v["margin"], 2) for k, v in row.items() if isinstance(v, dict)}, flush=True)

    conds = ["none", "text", "multi"]
    tr = [x for x in items if x["split"] == "train"]
    te = [x for x in items if x["split"] == "test"]
    summary = {"train": summarize(tr, conds), "test": summarize(te, conds)}
    for pr in sorted({x["pair"] for x in items}):
        summary[f"test:{pr}"] = summarize([x for x in te if x["pair"] == pr], conds)
    s = summary["test"]
    if summary["train"]["multi"]["acc"] < 0.75 or s["none"]["acc"] > 0.5:
        verdict = "inconclusive"
    elif s["multi"]["acc"] - s["none"]["acc"] >= 0.20 and s["multi"]["acc_both"] > s["none"]["acc_both"]:
        verdict = "raise"
    else:
        verdict = "no_raise"
    out = ROOT / "results" / f"e25_{args.model.split('/')[-1]}_L{args.layers}.json"
    out.write_text(json.dumps({"args": vars(args), "train": train_log, "items": items,
                               "summary": summary, "verdict": verdict},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    for k, row in summary.items():
        print(k, {c: (round(v["acc"], 3), round(v["acc_both"], 3)) for c, v in row.items()})
    print("verdict:", verdict)


if __name__ == "__main__":
    main()
