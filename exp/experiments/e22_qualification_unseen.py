"""E22: 限定の差分ベクトル（下位の概念ベクトル − 上位の概念ベクトル）は、学習していない上位概念に移るか（#91）。

組は e4 と同じ手で作った data/modifiers_ja.json（甲種/乙種、青/赤、一類/二類。体系からは取らない）。
下位の概念 = 修飾 + 上位（例: 甲種注文）。上位の語（注文）には当プロジェクトの定義がなく、元の意味のまま
使うので、上位の概念ベクトルは 0 とする。したがって限定の差分 = 下位の概念ベクトル。

学習（e4 と同じ目的・層8・30 step・lr 0.1）:
  修飾 M と学習用の上位 G ごとに、下位の語「M+G」のトークン位置に足すベクトル v[M,G] を学習する。
  教師は、その G の上の学習用の設問（各 G 4 問 × 2 順序）。組の 2 本（甲種G・乙種G）を同時に学習する。
  限定の差分 q[M] = 学習用の 2 つの G での v[M,G] の平均。

評価（学習していない上位 G'、各組 8 問、計 24 問）:
  none   何もなし
  text   修飾の定義文を設問の直前に置く（e4 の text）
  mod    e4 で学習した修飾のベクトルを、修飾の語の位置に足す（記録済みの e4_modifier_vectors.pt を読むだけ）
  qual   q[M] を、下位の語「M+G'」のトークン位置に足す
  学習用の設問では、own（v[M,G] を自分の G の下位の語に足す）も測り、学習が収まったかを見る。

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）。

判定（学習していない上位の 24 問を合わせて）:
  前提: 学習用の 24 問で own の accuracy ≥ 0.75。満たさなければ inconclusive（学習が収まっていない）。
  transfer     qual の accuracy − none の accuracy ≥ 0.20、かつ qual の order_robust_accuracy > none
  no_transfer  それ以外
  mod との比較は記録するが、判定には使わない。

使い方:
  python e22_qualification_unseen.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import Injector
from e4_modifier_composition import delta_of, encode


def parent_of(ex, parents):
    hits = [g for g in parents if g in ex["correct"]]
    assert len(hits) == 1, ex
    return hits[0]


def train_compounds(r, inj, exs, labels, steps, lr):
    d = r.model.config.hidden_size
    vecs = {lab: torch.zeros(d, requires_grad=True) for lab in labels}
    opt = torch.optim.Adam(list(vecs.values()), lr=lr)
    batch = []
    for ex in exs:
        for swap in (False, True):
            body, correct_no = question_text(ex, swap)
            batch.append(encode(r, r.render(None, body), str(correct_no), labels))
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
    return {lab: v.detach() for lab, v in vecs.items()}, first, last


@torch.no_grad()
def evaluate(r, inj, ex, prefix, vecs):
    labels = list(vecs) if vecs else []
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(ex, swap)
        ids, _, masks = encode(r, r.render(None, prefix + body), "", labels)
        inj.delta = delta_of(masks, vecs) if vecs else None
        last = r.model(ids).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def summarize(rows, conds):
    return {c: {"n": len(rows), "acc": sum(x[c]["margin"] > 0 for x in rows) / len(rows),
                "acc_both": sum(x[c]["both"] for x in rows) / len(rows),
                "mean_margin": sum(x[c]["margin"] for x in rows) / len(rows)} for c in conds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    args = ap.parse_args()
    pairs = json.loads((ROOT / "data" / "modifiers_ja.json").read_text(encoding="utf-8"))["pairs"]
    mod_vecs = torch.load(ROOT / "results" / "e4_modifier_vectors.pt")
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
        mv = {m: mod_vecs[m] for m in mods}
        for split in ("train", "test"):
            parents = pair[f"{split}_parents"]
            for ex in pair[split]:
                g = parent_of(ex, parents)
                row = {"pair": "/".join(mods), "split": split, "parent": g, "q": ex["q"],
                       "none": evaluate(r, inj, ex, "", None),
                       "text": evaluate(r, inj, ex, prefix, None),
                       "mod": evaluate(r, inj, ex, "", mv),
                       "qual": evaluate(r, inj, ex, "", {m + g: q[m] for m in mods})}
                if split == "train":
                    row["own"] = evaluate(r, inj, ex, "", own[g])
                items.append(row)
                print(split, g, {k: round(v["margin"], 2) for k, v in row.items() if isinstance(v, dict)}, flush=True)

    tr = [x for x in items if x["split"] == "train"]
    te = [x for x in items if x["split"] == "test"]
    summary = {"train": summarize(tr, ["none", "text", "mod", "qual", "own"]),
               "test": summarize(te, ["none", "text", "mod", "qual"])}
    for pr in sorted({x["pair"] for x in items}):
        summary[f"test:{pr}"] = summarize([x for x in te if x["pair"] == pr], ["none", "text", "mod", "qual"])
    s = summary["test"]
    if summary["train"]["own"]["acc"] < 0.75:
        verdict = "inconclusive"
    elif s["qual"]["acc"] - s["none"]["acc"] >= 0.20 and s["qual"]["acc_both"] > s["none"]["acc_both"]:
        verdict = "transfer"
    else:
        verdict = "no_transfer"
    out = ROOT / "results" / f"e22_{args.model.split('/')[-1]}_L{args.layer}.json"
    out.write_text(json.dumps({"args": vars(args), "train": train_log, "qual_norms": qual_norms,
                               "items": items, "summary": summary, "verdict": verdict},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    for k, row in summary.items():
        print(k, {c: (round(v["acc"], 3), round(v["acc_both"], 3)) for c, v in row.items()})
    print("verdict:", verdict)


if __name__ == "__main__":
    main()
