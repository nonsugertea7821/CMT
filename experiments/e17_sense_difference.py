"""E17: E3 の固有成分 s_c は、語の意味の候補どうしの差と一致するか。学習しない。

意味の差のベクトル d_c = 平均 h(新しい意味で使った文) − 平均 h(ふつうの意味で使った文)
（層8、語のトークン位置。文は data/sense_pairs_ja.json、語ごとに3文ずつ。定義文は含まない）
中心化 d~_c = d_c − （概念をまたいだ d の平均）。s_c も中心化されている（s_c = v_c − m）。

1. 向き: cos(s_c, d~_c)、自概念 − 他概念の平均、24 語の中で自分の d~ が何番目に近いか。
   語の順を入れ替えた並べ替え検定（10000 回）で、自概念の平均 cos の p 値。
2. 介入（E3 と同じ二択、同じ指標）:
   none、full（m + s_c）、m+d（m + d~_c、大きさを |s_c| にそろえる）、d（d~_c だけ、同じ大きさ）、
   m+d_swap（m + 他の語の d~、同じ大きさ。対照）

使い方:
  python e17_sense_difference.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json
import random

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, eval_item
from e15_vector_geometry import word_state

F = torch.nn.functional


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    args = ap.parse_args()
    name = args.model.split("/")[-1]

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    pairs = json.loads((ROOT / "data" / "sense_pairs_ja.json").read_text(encoding="utf-8"))["pairs"]
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    concepts = sorted({d for it in items for d in it["defs"]})
    vec = torch.load(ROOT / "results" / f"e3_{name}_L{args.layer}_defqa.pt")
    vec = vec[0] if isinstance(vec, tuple) else vec
    V = {c: vec[c].float().view(-1) for c in concepts}
    m = torch.stack(list(V.values())).mean(0)
    s = {c: V[c] - m for c in concepts}

    r = Runner(args.model)
    d = {}
    for c in concepts:
        hn = torch.stack([word_state(r, args.layer, t, c).float() for t in pairs[c]["new"]]).mean(0)
        ho = torch.stack([word_state(r, args.layer, t, c).float() for t in pairs[c]["old"]]).mean(0)
        d[c] = hn - ho
    dm = torch.stack(list(d.values())).mean(0)
    dc = {c: d[c] - dm for c in concepts}

    # 1. 向き
    S = F.normalize(torch.stack([s[c] for c in concepts]), dim=-1)
    D = F.normalize(torch.stack([dc[c] for c in concepts]), dim=-1)
    C = S @ D.T                       # [s の語, d の語]
    own = C.diag()
    other = (C.sum(1) - own) / (len(concepts) - 1)
    rank = [(C[i] > C[i, i]).sum().item() + 1 for i in range(len(concepts))]
    rng, obs, ge = random.Random(0), own.mean().item(), 0
    for _ in range(10000):
        p = list(range(len(concepts)))
        rng.shuffle(p)
        ge += C[list(range(len(concepts))), p].mean().item() >= obs
    raw = [F.cosine_similarity(s[c], d[c], dim=0).item() for c in concepts]
    full = [F.cosine_similarity(V[c], d[c], dim=0).item() for c in concepts]
    geo = {"cos_s_dcentered_own": obs, "cos_s_dcentered_other": other.mean().item(),
           "own_minus_other": (own - other).mean().item(), "perm_p": (ge + 1) / 10001,
           "rank_mean": sum(rank) / len(rank), "rank1_count": sum(x == 1 for x in rank),
           "cos_s_draw": sum(raw) / len(raw), "cos_v_draw": sum(full) / len(full),
           "cos_m_dmean": F.cosine_similarity(m, dm, dim=0).item(),
           "norm_s": sum(s[c].norm().item() for c in concepts) / len(concepts),
           "norm_dcentered": sum(dc[c].norm().item() for c in concepts) / len(concepts),
           "norm_d": sum(d[c].norm().item() for c in concepts) / len(concepts)}
    per = {c: {"cos_own": own[i].item(), "cos_other": other[i].item(), "rank": rank[i]} for i, c in enumerate(concepts)}
    print("[1] 向き")
    for k, v in geo.items():
        print(f"  {k:24s} {v:+.4f}")

    # 2. 介入
    scale = lambda x, c: x / x.norm() * s[c].norm()
    sw = {c: concepts[(i + 1) % len(concepts)] for i, c in enumerate(concepts)}
    shape = vec[concepts[0]].shape
    mk = lambda f: {c: f(c).view(shape).to(vec[c].dtype) for c in concepts}
    conds = {"full": mk(lambda c: V[c]),
             "m+d": mk(lambda c: m + scale(dc[c], c)),
             "d": mk(lambda c: scale(dc[c], c)),
             "m+d_swap": mk(lambda c: m + scale(dc[sw[c]], c))}
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
    print("[2] 介入")
    for g, row in summary.items():
        for k, x in row.items():
            print(f"  {g} {k:9s} acc={x['acc']:.2f}  both={x['acc_both']:.2f}  m={x['mean_margin']:+.2f}")
    (ROOT / "results" / f"e17_{name}_L{args.layer}.json").write_text(json.dumps(
        {"args": vars(args), "geometry": geo, "concepts": per, "items": rows, "summary": summary},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
