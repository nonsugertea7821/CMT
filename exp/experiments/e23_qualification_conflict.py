"""E23: 限定の差分ベクトルは、元の意味と食い違う再定義への追従を上げるか（#92）。

組は手で作った data/modifiers_conflict_ja.json（大口/小口、至急/通常、正式/仮。体系からは取らない）。
修飾の語の元の意味と逆の定義を与える（例: 大口＝数量が十個未満）。設問は定義どおりに答えると、
元の意味から選ぶ答えと逆になる（衝突）。

下位の概念 = 修飾 + 上位（例: 大口注文）。E22 と同じく、上位の語には当プロジェクトの定義がないので、
上位の概念ベクトルは 0 とし、限定の差分 = 下位の概念ベクトル。

学習（E22 と同じ関数・層8・30 step・lr 0.1）:
  修飾 M と学習用の上位 G ごとに、下位の語「M+G」のトークン位置に足すベクトル v[M,G] を学習する。
  教師は、その G の上の学習用の設問（各 G 4 問 × 2 順序）。組の 2 本を同時に学習する。
  限定の差分 q[M] = 学習用の 2 つの G での v[M,G] の平均。

評価（学習していない上位 G'、各組 8 問、計 24 問）:
  none   何もなし
  text   修飾の定義文を設問の直前に置く
  qual   q[M] を、下位の語「M+G'」のトークン位置に足す
  学習用の設問では own（v[M,G] を自分の G の下位の語に足す）も測る。
  （E22 の mod は、この組の修飾のベクトルを学習していないので測らない）

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）。

判定（学習していない上位の 24 問を合わせて）:
  前提1: 学習用の 24 問で own の accuracy ≥ 0.75。満たさなければ inconclusive（学習が収まっていない）。
  前提2: 学習していない上位で none の accuracy ≤ 0.5。満たさなければ inconclusive（衝突になっていない）。
  raise     qual の accuracy − none の accuracy ≥ 0.20、かつ qual の order_robust_accuracy > none
  no_raise  それ以外
  text との比較は記録するが、判定には使わない。

使い方:
  python e23_qualification_conflict.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector
from e22_qualification_unseen import evaluate, parent_of, summarize, train_compounds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    args = ap.parse_args()
    pairs = json.loads((ROOT / "data" / "modifiers_conflict_ja.json").read_text(encoding="utf-8"))["pairs"]
    r = Runner(args.model)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)

    items, train_log, qual_norms = [], {}, {}
    for pair in pairs:
        mods = pair["modifiers"]
        own = {}
        for g in pair["train_parents"]:
            t0 = time.time()
            exs = [ex for ex in pair["train"] if parent_of(ex, pair["train_parents"]) == g]
            labels = [m + g for m in mods]
            vecs, first, last = train_compounds(r, inj, exs, labels, args.steps, args.lr)
            own[g] = vecs
            train_log[f"{'/'.join(mods)}:{g}"] = {"n_items": len(exs), "loss_first": first, "loss_last": last,
                                                 "norms": {k: v.norm().item() for k, v in vecs.items()}}
            print(f"[train] {labels}: loss {first:.2f} -> {last:.2f}  {time.time() - t0:.0f}s", flush=True)
        q = {m: torch.stack([own[g][m + g] for g in pair["train_parents"]]).mean(0) for m in mods}
        qual_norms.update({m: v.norm().item() for m, v in q.items()})
        prefix = "次の定義に従うこと。\n" + "\n".join(pair["defs"].values()) + "\n\n"
        for split in ("train", "test"):
            parents = pair[f"{split}_parents"]
            for ex in pair[split]:
                g = parent_of(ex, parents)
                row = {"pair": "/".join(mods), "split": split, "parent": g, "q": ex["q"],
                       "none": evaluate(r, inj, ex, "", None),
                       "text": evaluate(r, inj, ex, prefix, None),
                       "qual": evaluate(r, inj, ex, "", {m + g: q[m] for m in mods})}
                if split == "train":
                    row["own"] = evaluate(r, inj, ex, "", own[g])
                items.append(row)
                print(split, g, {k: round(v["margin"], 2) for k, v in row.items() if isinstance(v, dict)}, flush=True)

    tr = [x for x in items if x["split"] == "train"]
    te = [x for x in items if x["split"] == "test"]
    summary = {"train": summarize(tr, ["none", "text", "qual", "own"]),
               "test": summarize(te, ["none", "text", "qual"])}
    for pr in sorted({x["pair"] for x in items}):
        summary[f"test:{pr}"] = summarize([x for x in te if x["pair"] == pr], ["none", "text", "qual"])
    s = summary["test"]
    if summary["train"]["own"]["acc"] < 0.75 or s["none"]["acc"] > 0.5:
        verdict = "inconclusive"
    elif s["qual"]["acc"] - s["none"]["acc"] >= 0.20 and s["qual"]["acc_both"] > s["none"]["acc_both"]:
        verdict = "raise"
    else:
        verdict = "no_raise"
    out = ROOT / "results" / f"e23_{args.model.split('/')[-1]}_L{args.layer}.json"
    out.write_text(json.dumps({"args": vars(args), "train": train_log, "qual_norms": qual_norms,
                               "items": items, "summary": summary, "verdict": verdict},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    for k, row in summary.items():
        print(k, {c: (round(v["acc"], 3), round(v["acc_both"], 3)) for c, v in row.items()})
    print("verdict:", verdict)


if __name__ == "__main__":
    main()
