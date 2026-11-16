"""E18: E3 の概念ベクトルは、二択の設問以外の形式でも効くか。学習しない。

s が「意味」なら形式によらず効き、「二択の鍵」なら二択の外では効かないはず。
チャットの雛形も選択肢も使わず、地の文で測る（層8、語のトークン位置に足す）。

A. 平叙文: 設問「X は、語に当たるか。」から、肯定「X は、語に当たる。」と否定「…当たらない。」を作り、
   正しい方の対数尤度 − 誤った方（margin）。正答率 = margin > 0 の割合。
B. 用例: E17 の文の組（新しい意味の文 i と、ふつうの意味の文 i）。語の位置から後の対数尤度の差
   new − old を、何も足さないときと比べた増分 Δ。新しい意味へ寄せるなら Δ > 0。
条件: none、full（m + s）、specific（s）、common（m）、swapped（他の語の v）

使い方:
  python e18_format_transfer.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, build_delta, label_mask

NEG = [("当たる", "当たらない"), ("属する", "属さない")]


@torch.no_grad()
def logp_after(r, inj, text, word, vs):
    """text の対数尤度のうち、word が最初に現れるトークン以降の分。vs があれば語の位置に足す。"""
    d_model = r.model.config.hidden_size
    ids, delta = build_delta(r.tok, text, vs, d_model)
    inj.delta = delta if vs else None
    logits = r.model(ids).logits[0]
    inj.delta = None
    _, mask = label_mask(r.tok, text, word)
    start = mask.index(True)
    lp = torch.log_softmax(logits[:-1].float(), -1).gather(1, ids[0, 1:].view(-1, 1)).view(-1)
    return lp[max(start - 1, 0):].sum().item()


def statements(q):
    pos = q[:-2] + "。"
    for a, b in NEG:
        i = pos.rfind(a)
        if i >= 0:
            return pos, pos[:i] + b + pos[i + len(a):]
    raise ValueError(q)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    args = ap.parse_args()
    name = args.model.split("/")[-1]

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    pairs = json.loads((ROOT / "data" / "sense_pairs_ja.json").read_text(encoding="utf-8"))["pairs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    concepts = sorted({d for it in items for d in it["defs"]})
    vec = torch.load(ROOT / "results" / f"e3_{name}_L{args.layer}_defqa.pt")
    vec = vec[0] if isinstance(vec, tuple) else vec
    m = torch.stack([vec[c] for c in concepts]).mean(0)
    conds = {"none": None, "full": vec, "specific": {c: vec[c] - m for c in concepts},
             "common": {c: m for c in concepts},
             "swapped": {c: vec[concepts[(i + 1) % len(concepts)]] for i, c in enumerate(concepts)}}

    r = Runner(args.model)
    inj = Injector(r.model, args.layer)
    # A. 平叙文
    rows = {}
    for it in items:
        c = it["defs"][0]
        pos, neg = statements(it["q"])
        right, wrong = (pos, neg) if it["correct"] == "はい" else (neg, pos)
        rows[it["id"]] = {"group": it["group"]}
        for k, vs in conds.items():
            v = {c: vs[c]} if vs else {}
            mg = logp_after(r, inj, right, c, v) - logp_after(r, inj, wrong, c, v)
            rows[it["id"]][k] = {"margin": mg}
    sumA = {}
    for g in args.groups:
        sumA[g] = {}
        for k in conds:
            rs = [x[k]["margin"] for x in rows.values() if x["group"] == g]
            sumA[g][k] = {"n": len(rs), "acc": sum(x > 0 for x in rs) / len(rs), "mean_margin": sum(rs) / len(rs)}
    # B. 用例
    usage = {}
    for c in concepts:
        for i, (tn, to) in enumerate(zip(pairs[c]["new"], pairs[c]["old"])):
            row = {}
            for k, vs in conds.items():
                v = {c: vs[c]} if vs else {}
                row[k] = logp_after(r, inj, tn, c, v) - logp_after(r, inj, to, c, v)
            usage[f"{c}.{i}"] = {"concept": c} | {k: {"margin": row[k], "delta": row[k] - row["none"]} for k in conds}
    sumB = {k: {"mean_delta": sum(u[k]["delta"] for u in usage.values()) / len(usage),
                "frac_up": sum(u[k]["delta"] > 0 for u in usage.values()) / len(usage)} for k in conds}

    print("[A] 平叙文")
    for g, row in sumA.items():
        for k, x in row.items():
            print(f"  {g} {k:9s} acc={x['acc']:.2f}  m={x['mean_margin']:+.2f}")
    print("[B] 用例（新しい意味 − ふつうの意味 の増分）")
    for k, x in sumB.items():
        print(f"  {k:9s} Δ={x['mean_delta']:+.3f}  上がった割合={x['frac_up']:.2f}")
    (ROOT / "results" / f"e18_{name}_L{args.layer}.json").write_text(json.dumps(
        {"args": vars(args), "items": rows, "usage": usage, "summary": sumA, "usage_summary": sumB},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
