"""E24: 修飾の位置に足すベクトルは、元の意味と食い違う再定義への追従を上げるか（E23 の含意）。

E23 では、下位の語「M+G」の位置に足す単一層のベクトルが、衝突の組で損失 ln 2 の近くに止まり、
答えを五分五分に押し戻すだけだった。元の意味が修飾の語 M に載っているなら、M の位置に足すほうが
押し切れるはず、という読みを確かめる。

組は E23 と同じ data/modifiers_conflict_ja.json（大口/小口、至急/通常、正式/仮。手で作ったもの）。

学習（e4 の train_pair をそのまま使う。層8・30 step・lr 0.1）:
  組ごとに、学習用の 2 つの上位の 8 問 × 2 順序で、修飾の語 M の位置に足すベクトル v[M] を、組の 2 本同時に学習する。

評価（E22 の evaluate。学習していない上位、各組 8 問、計 24 問）:
  none   何もなし
  text   修飾の定義文を設問の直前に置く
  mod    v[M] を修飾の語 M の位置に足す
  学習用の設問でも同じ 3 条件を測り、mod を学習が収まったかの確認に使う。

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）。

判定（E23 と同じ形。学習していない上位の 24 問を合わせて）:
  前提1: 学習用の 24 問で mod の accuracy ≥ 0.75。満たさなければ inconclusive。
  前提2: 学習していない上位で none の accuracy ≤ 0.5。満たさなければ inconclusive。
  raise     mod の accuracy − none の accuracy ≥ 0.20、かつ mod の order_robust_accuracy > none
  no_raise  それ以外

使い方:
  python e24_modifier_conflict.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8
"""
import argparse
import json
import time

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector
from e4_modifier_composition import train_pair
from e22_qualification_unseen import evaluate, parent_of, summarize


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

    items, train_log = [], {}
    for pair in pairs:
        mods = pair["modifiers"]
        t0 = time.time()
        vecs, first, last = train_pair(r, inj, pair, args.steps, args.lr)
        train_log["/".join(mods)] = {"n_items": len(pair["train"]), "loss_first": first, "loss_last": last,
                                     "norms": {k: v.norm().item() for k, v in vecs.items()}}
        print(f"[train] {mods}: loss {first:.2f} -> {last:.2f}  {time.time() - t0:.0f}s", flush=True)
        prefix = "次の定義に従うこと。\n" + "\n".join(pair["defs"].values()) + "\n\n"
        for split in ("train", "test"):
            parents = pair[f"{split}_parents"]
            for ex in pair[split]:
                g = parent_of(ex, parents)
                row = {"pair": "/".join(mods), "split": split, "parent": g, "q": ex["q"],
                       "none": evaluate(r, inj, ex, "", None),
                       "text": evaluate(r, inj, ex, prefix, None),
                       "mod": evaluate(r, inj, ex, "", vecs)}
                items.append(row)
                print(split, g, {k: round(v["margin"], 2) for k, v in row.items() if isinstance(v, dict)}, flush=True)

    conds = ["none", "text", "mod"]
    tr = [x for x in items if x["split"] == "train"]
    te = [x for x in items if x["split"] == "test"]
    summary = {"train": summarize(tr, conds), "test": summarize(te, conds)}
    for pr in sorted({x["pair"] for x in items}):
        summary[f"test:{pr}"] = summarize([x for x in te if x["pair"] == pr], conds)
    s = summary["test"]
    if summary["train"]["mod"]["acc"] < 0.75 or s["none"]["acc"] > 0.5:
        verdict = "inconclusive"
    elif s["mod"]["acc"] - s["none"]["acc"] >= 0.20 and s["mod"]["acc_both"] > s["none"]["acc_both"]:
        verdict = "raise"
    else:
        verdict = "no_raise"
    out = ROOT / "results" / f"e24_{args.model.split('/')[-1]}_L{args.layer}.json"
    out.write_text(json.dumps({"args": vars(args), "train": train_log, "items": items,
                               "summary": summary, "verdict": verdict},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    for k, row in summary.items():
        print(k, {c: (round(v["acc"], 3), round(v["acc_both"], 3)) for c, v in row.items()})
    print("verdict:", verdict)


if __name__ == "__main__":
    main()
