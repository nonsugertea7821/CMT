"""E19: 中立な対照。E3 の概念ベクトルと同じ大きさのランダムなベクトルを足す。学習しない。

入れ替え（他の語の v）は中立でなく、逆向きに押す。そこで、同じ大きさのランダムな向きと比べる。
条件（層8、語のトークン位置。E3 と同じ二択、同じ指標）:
  none       何もなし
  own        v_c（E3）
  swapped    他の語の v（E15 と同じ、1つずらす）
  rand       ランダムな向き、大きさ |v_c|（5 回引いて平均）
  m+rand     m + ランダムな向き、大きさ |s_c|（5 回。固有成分だけをランダムにする）

使い方:
  python e19_neutral_control.py --model Qwen/Qwen2.5-1.5B-Instruct
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
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    ap.add_argument("--draws", type=int, default=5)
    args = ap.parse_args()
    name = args.model.split("/")[-1]

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    concepts = sorted({d for it in items for d in it["defs"]})
    vec = torch.load(ROOT / "results" / f"e3_{name}_L{args.layer}_defqa.pt")
    vec = vec[0] if isinstance(vec, tuple) else vec
    m = torch.stack([vec[c] for c in concepts]).mean(0)

    def rand(k, c, norm):
        g = torch.Generator().manual_seed(k * 1000 + concepts.index(c))
        x = torch.randn(vec[c].shape, generator=g)
        return (x / x.norm() * norm).to(vec[c].dtype)

    conds = {"own": vec, "swapped": {c: vec[concepts[(i + 1) % len(concepts)]] for i, c in enumerate(concepts)}}
    for k in range(args.draws):
        conds[f"rand{k}"] = {c: rand(k, c, vec[c].norm()) for c in concepts}
        conds[f"m+rand{k}"] = {c: m + rand(100 + k, c, (vec[c] - m).norm()) for c in concepts}

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
        for base in ("rand", "m+rand"):
            ks = [f"{base}{k}" for k in range(args.draws)]
            summary[g][base] = {s: sum(summary[g][k][s] for k in ks) / len(ks) for s in ("acc", "acc_both", "mean_margin")}
            summary[g][base]["acc_range"] = [min(summary[g][k]["acc"] for k in ks), max(summary[g][k]["acc"] for k in ks)]
    for g, row in summary.items():
        print(g)
        for k in ["none", "own", "swapped", "rand", "m+rand"]:
            x = row[k]
            print(f"  {k:8s} acc={x['acc']:.2f}  both={x['acc_both']:.2f}  m={x['mean_margin']:+.2f}  {x.get('acc_range', '')}")
    (ROOT / "results" / f"e19_{name}_L{args.layer}.json").write_text(json.dumps(
        {"args": vars(args), "items": rows, "summary": summary}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
