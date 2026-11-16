"""E15: モデルから見たベクトル（隠れ状態のずれ）の幾何を測る。学習しない。

spec の state_shift（隠れ状態のずれ）の定義から出る含意を確かめる。
  1. 大きさの比 |v| / |h|: 足したずれが、モデルが普段作る状態の範囲に留まるか
     E3（層8、学習）、E14（層8、定義の有無の差）、E12（入力埋め込み、専用トークン）
  2. E3 の v と、定義文を直前に置いたときに実際に起きるずれ Δnear = h(定義+設問) − h(設問) との cos
     （評価の設問ごと。概念をまたいだ平均を引いた「中心化」cos も出す。共通の位置の影響を除くため）
  3. 入れ替え: 概念 A の設問に概念 B の E3 ベクトルを足したときの正答率（意味が基準点＝概念に依存するか）

使い方:
  python e15_vector_geometry.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import Injector, eval_item, label_mask

HEAD = "次の定義に従うこと。\n"
F = torch.nn.functional


@torch.no_grad()
def word_state(r, layer, body, label):
    """層 layer の出力で、最後に現れる語のトークン位置の平均。"""
    ids, mask = label_mask(r.tok, r.render(None, body), label)
    hs = r.model(torch.tensor([ids]), output_hidden_states=True).hidden_states[layer + 1][0]
    pos = [i for i, m in enumerate(mask) if m]
    last = []
    for i in reversed(pos):
        if last and i != last[-1] - 1:
            break
        last.append(i)
    return hs[last].mean(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    args = ap.parse_args()
    name = args.model.split("/")[-1]
    res_dir = ROOT / "results"

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    concepts = sorted({d for it in items for d in it["defs"]})

    e3 = torch.load(res_dir / f"e3_{name}_L{args.layer}_defqa.pt")
    e3x = torch.load(res_dir / f"e3_{name}_L{args.layer}_exprdefqa.pt")
    e14 = torch.load(res_dir / f"e14_{name}_L{args.layer}.pt")
    e12 = torch.load(res_dir / f"e12_{name}.pt")
    e3 = e3[0] if isinstance(e3, tuple) else e3
    e3x = e3x[0] if isinstance(e3x, tuple) else e3x

    r = Runner(args.model)
    emb = r.model.get_input_embeddings().weight

    # 1. 大きさ
    h_none, d_near = {}, {}
    for it in items:
        c = it["defs"][0]
        body, _ = question_text(it, False)
        h0 = word_state(r, args.layer, body, c)
        h1 = word_state(r, args.layer, HEAD + "\n".join(defs[d] for d in it["defs"]) + "\n\n" + body, c)
        h_none[it["id"]], d_near[it["id"]] = h0, h1 - h0
    hn = torch.stack(list(h_none.values())).norm(dim=-1).mean().item()
    en = torch.stack([emb[r.tok(c, add_special_tokens=False).input_ids].mean(0) for c in concepts]).norm(dim=-1).mean().item()

    def ratio(vs, base):
        ns = torch.stack([vs[c].float().view(-1) for c in concepts if c in vs]).norm(dim=-1)
        return {"mean_norm": ns.mean().item(), "base_norm": base, "ratio": ns.mean().item() / base}

    size = {"e3_defqa": ratio(e3, hn), "e3_exprdefqa": ratio(e3x, hn), "e14": ratio(e14, hn),
            "near_actual": {"mean_norm": torch.stack(list(d_near.values())).norm(dim=-1).mean().item(), "base_norm": hn},
            "e12_embed": ratio(e12, en)}
    size["near_actual"]["ratio"] = size["near_actual"]["mean_norm"] / hn
    print("[1] |v|/|h|")
    for k, v in size.items():
        print(f"  {k:13s} |v|={v['mean_norm']:.2f}  |h|={v['base_norm']:.2f}  比={v['ratio']:.3f}")

    # 2. E3 の v と Δnear の cos（そのまま／中心化）
    mean_near = torch.stack(list(d_near.values())).mean(0)
    mean_e3 = torch.stack([e3[c].float().view(-1) for c in concepts]).mean(0)
    cos = {}
    for g in args.groups:
        raw, cen, own_vs_other = [], [], []
        for it in items:
            if it["group"] != g:
                continue
            c = it["defs"][0]
            v, dn = e3[c].float().view(-1), d_near[it["id"]]
            raw.append(F.cosine_similarity(v, dn, dim=0).item())
            cen.append(F.cosine_similarity(v - mean_e3, dn - mean_near, dim=0).item())
            others = [F.cosine_similarity(e3[o].float().view(-1) - mean_e3, dn - mean_near, dim=0).item()
                      for o in concepts if o != c]
            own_vs_other.append(cen[-1] - sum(others) / len(others))
        cos[g] = {"raw": sum(raw) / len(raw), "centered": sum(cen) / len(cen),
                  "centered_own_minus_other": sum(own_vs_other) / len(own_vs_other)}
    # 概念間の E3 ベクトルどうしの cos（共通成分の大きさ）
    V = torch.stack([e3[c].float().view(-1) for c in concepts])
    Vn = F.normalize(V, dim=-1)
    off = (Vn @ Vn.T)[~torch.eye(len(concepts), dtype=torch.bool)].mean().item()
    print("[2] cos(v_E3, Δnear)")
    for g, s in cos.items():
        print(f"  {g}: そのまま {s['raw']:+.3f}  中心化 {s['centered']:+.3f}  自概念−他概念 {s['centered_own_minus_other']:+.3f}")
    print(f"  E3 ベクトルどうしの平均 cos（概念間）: {off:+.3f}")

    # 3. 入れ替え（1つずらす）
    inj = Injector(r.model, args.layer)
    shifted = {c: e3[concepts[(i + 1) % len(concepts)]] for i, c in enumerate(concepts)}
    swap = {}
    for g in args.groups:
        swap[g] = {}
        gi = [it for it in items if it["group"] == g]
        for cname, vs in (("own", e3), ("swapped", shifted)):
            rs = [eval_item(r, inj, it, defs, vs, False, True) for it in gi]
            swap[g][cname] = {"acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                              "acc_both": sum(x["both"] for x in rs) / len(rs),
                              "mean_margin": sum(x["margin"] for x in rs) / len(rs)}
    print("[3] 入れ替え")
    for g, row in swap.items():
        for k, s in row.items():
            print(f"  {g} {k:8s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}  m={s['mean_margin']:+.2f}")

    (res_dir / f"e15_{name}_L{args.layer}.json").write_text(json.dumps(
        {"args": vars(args), "size": size, "cos": cos, "e3_offdiag_cos": off, "summary": swap},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
