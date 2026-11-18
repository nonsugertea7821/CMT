"""E21: E16 の共通成分 m を、ベクトルを学習していない概念の語に足しても、判定は安定するか（#56）。

m = E3（defqa, 層8）の 24 概念のベクトルの平均（E16 の common と同じもの）。
対象は、E3 でベクトルを学習していない概念の組 G1・G3・G4（concepts_ja.json、手で作った設問）。
m を、設問の中で各項目の defs の語が現れたトークン位置に足す（E16 と同じ足し方）。学習はしない。

条件:
  none    何もなし
  common  m
  rand    m と同じ大きさの乱数の向き（seed 0）。どんなずれでも同じことが起きるかの対照

指標（E16 と同じ）: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）。

判定（G1・G3・G4 を合わせた 51 項目、ALL）:
  transfer     common の order_robust_accuracy が none より 0.10 以上高く、かつ rand より 0.10 以上高い
  no_transfer  common − none < 0.10
  nonspecific  common − none ≥ 0.10 だが common − rand < 0.10（向きに依らないずれの効果）
  群ごと（G1, G3, G4）の値も記録するが、判定は ALL で行う。

使い方:
  python e21_common_unseen.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, eval_item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--run", default="defqa")
    ap.add_argument("--groups", nargs="+", default=["G1", "G3", "G4"])
    args = ap.parse_args()
    name = args.model.split("/")[-1]

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    vec = torch.load(ROOT / "results" / f"e3_{name}_L{args.layer}_{args.run}.pt")
    vec = vec[0] if isinstance(vec, tuple) else vec
    trained = sorted({d for it in data["items"] if it["group"] in ("G2c", "G2k") for d in it["defs"]})
    assert sorted(vec) == trained
    m = torch.stack([vec[c] for c in trained]).mean(0)
    g = torch.Generator().manual_seed(0)
    rnd = torch.randn(m.shape[0], generator=g)
    rnd = rnd / rnd.norm() * m.norm()

    items = [it for it in data["items"] if it["group"] in args.groups]
    assert not any(d in vec for it in items for d in it["defs"])
    labels = sorted({d for it in items for d in it["defs"]})
    conds = {"common": {c: m for c in labels}, "rand": {c: rnd for c in labels}}

    r = Runner(args.model)
    inj = Injector(r.model, args.layer)
    rows = {}
    for it in items:
        rows[it["id"]] = {"group": it["group"], "none": eval_item(r, inj, it, defs, {}, False, False)}
        for k, vs in conds.items():
            rows[it["id"]][k] = eval_item(r, inj, it, defs, vs, False, True)
        print(it["id"], {k: round(v["margin"], 2) for k, v in rows[it["id"]].items() if k != "group"}, flush=True)

    summary = {}
    for grp in [*args.groups, "ALL"]:
        summary[grp] = {}
        for k in ["none", *conds]:
            rs = [v[k] for v in rows.values() if grp == "ALL" or v["group"] == grp]
            summary[grp][k] = {"n": len(rs), "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                               "acc_both": sum(x["both"] for x in rs) / len(rs),
                               "mean_margin": sum(x["margin"] for x in rs) / len(rs)}
    a = summary["ALL"]
    d_none = a["common"]["acc_both"] - a["none"]["acc_both"]
    d_rand = a["common"]["acc_both"] - a["rand"]["acc_both"]
    verdict = "no_transfer" if d_none < 0.10 else ("transfer" if d_rand >= 0.10 else "nonspecific")
    out = ROOT / "results" / f"e21_{name}_L{args.layer}_{args.run}.json"
    out.write_text(json.dumps({"args": vars(args), "norm_m": m.norm().item(), "items": rows, "summary": summary,
                               "verdict": verdict, "d_none": d_none, "d_rand": d_rand},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    for grp, row in summary.items():
        print(grp, {k: (round(s["acc"], 3), round(s["acc_both"], 3)) for k, s in row.items()})
    print("verdict:", verdict, round(d_none, 3), round(d_rand, 3))


if __name__ == "__main__":
    main()
