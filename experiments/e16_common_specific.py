"""E16: E3 の概念ベクトルを、概念間の共通成分と概念ごとの固有成分に分けて、片方ずつ足す。学習しない。

v_c = m + s_c   （m = 概念をまたいだ平均、s_c = v_c − m）
条件（層8、語のトークン位置に足す。E3 と同じ二択、同じ指標）:
  none      何もなし
  full      v_c（E3 と同じ）
  common    m だけ（どの概念にも同じもの）
  specific  s_c だけ

予想: common は元の意味を抑える（G2c↑、G2k↓）。specific が G2k を守る。

使い方:
  python e16_common_specific.py --model Qwen/Qwen2.5-1.5B-Instruct
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
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    args = ap.parse_args()
    name = args.model.split("/")[-1]

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    concepts = sorted({d for it in items for d in it["defs"]})
    vec = torch.load(ROOT / "results" / f"e3_{name}_L{args.layer}_{args.run}.pt")
    vec = vec[0] if isinstance(vec, tuple) else vec
    m = torch.stack([vec[c] for c in concepts]).mean(0)
    conds = {"full": vec, "common": {c: m for c in concepts}, "specific": {c: vec[c] - m for c in concepts}}
    norms = {k: sum(v[c].float().norm().item() for c in concepts) / len(concepts) for k, v in conds.items()}
    print("平均の大きさ:", {k: round(v, 2) for k, v in norms.items()})

    r = Runner(args.model)
    inj = Injector(r.model, args.layer)
    rows = {}
    for it in items:
        rows[it["id"]] = {"group": it["group"], "none": eval_item(r, inj, it, defs, {}, False, False)}
        for k, vs in conds.items():
            rows[it["id"]][k] = eval_item(r, inj, it, defs, vs, False, True)
    summary = {}
    for g in args.groups:
        summary[g] = {}
        for k in ["none", *conds]:
            rs = [v[k] for v in rows.values() if v["group"] == g]
            summary[g][k] = {"n": len(rs), "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                             "acc_both": sum(x["both"] for x in rs) / len(rs),
                             "mean_margin": sum(x["margin"] for x in rs) / len(rs)}
    (ROOT / "results" / f"e16_{name}_L{args.layer}_{args.run}.json").write_text(json.dumps(
        {"args": vars(args), "norms": norms, "items": rows, "summary": summary}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    for g, row in summary.items():
        print(f"\n{g} (n={row['none']['n']})")
        for k, s in row.items():
            print(f"  {k:9s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}  m={s['mean_margin']:+.2f}")


if __name__ == "__main__":
    main()
