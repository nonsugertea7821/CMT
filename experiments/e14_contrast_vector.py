"""E14: 再定義した意味と、モデルの既定の意味の差を、ベクトルにする（学習しない）。

再定義を「モデルが元から持つ意味の候補から一つを選ぶこと」と見ると、ベクトルに要るのは定義の全体ではなく、
既定の意味から目的の意味へずらす向きだけになる。docs/design.md 5.5 の案2（定義文を読ませたときの活性化の差）を、
同じ文を定義あり／なしで読ませた差として作る。

作り方（概念ごと、指定した層の出力で、語のトークン位置の平均）:
  v = mean_{適用例 q} [ h(定義 + q) − h(q) ]
  適用例は data/train_qa_ja.json（評価の設問とは別）。定義は日本語の定義文、または概念式（--def-source expr）。

評価（E3 と同じ二択、同じ指標）:
  none     何もなし
  vecα    語のトークン位置に α·v を足す（α = 1, 2, 4）
  near     定義文を設問の直前に置く
  near+vec1

使い方:
  python e14_contrast_vector.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import Injector, eval_item, label_mask

HEAD = "次の定義に従うこと。\n"


class Capture:
    def __init__(self, model, layer):
        self.h = None
        model.model.layers[layer].register_forward_hook(self._hook)

    def _hook(self, module, args, output):
        self.h = (output[0] if isinstance(output, tuple) else output)[0].detach()


@torch.no_grad()
def word_state(r, cap, body, label):
    """body を読ませたときの、最後に現れる語のトークン位置の、指定層の出力の平均。"""
    text = r.render(None, body)
    ids, mask = label_mask(r.tok, text, label)
    r.model(torch.tensor([ids]))
    pos = [i for i, m in enumerate(mask) if m]
    # 設問の中の語（最後の出現）。定義の中にも語は出るが、比べたいのは設問の中の語の読み方
    last = []
    for i in reversed(pos):
        if last and i != last[-1] - 1:
            break
        last.append(i)
    return cap.h[last].mean(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    ap.add_argument("--def-source", choices=["ja", "expr"], default="ja")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    if args.def_source == "expr":
        import sys
        sys.path.insert(0, str(ROOT.parent / "tools"))
        import render_expr
        R = render_expr.Renderer()
        defs = {c: R.text(c, mask=True) for it in items for c in it["defs"]}
    concepts = sorted({d for it in items for d in it["defs"]})
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]

    r = Runner(args.model)
    cap = Capture(r.model, args.layer)
    inj = Injector(r.model, args.layer)

    base, info = {}, {}
    for c in concepts:
        diffs = []
        for ex in qa[c]:
            body, _ = question_text(ex, False)
            diffs.append(word_state(r, cap, HEAD + defs[c] + "\n\n" + body, c) - word_state(r, cap, body, c))
        base[c] = torch.stack(diffs).mean(0)
        cos = torch.nn.functional.cosine_similarity(torch.stack(diffs), base[c].view(1, -1)).mean().item()
        info[c] = {"norm": base[c].norm().item(), "mean_cos_to_mean": cos}
        print(f"[vec] {c}: |v|={info[c]['norm']:.1f}  各例と平均の cos={cos:.2f}", flush=True)

    alphas = [1, 2, 4]
    conds = {"none": (False, None), "near": (True, None)}
    conds |= {f"vec{a}": (False, a) for a in alphas}
    conds["near+vec1"] = (True, 1)
    res = {}
    for it in items:
        res[it["id"]] = {"group": it["group"]}
        for name, (use_def, a) in conds.items():
            vs = {c: a * v for c, v in base.items()} if a else {}
            res[it["id"]][name] = eval_item(r, inj, it, defs, vs, use_def, a is not None)
    summary = {}
    for g in sorted({it["group"] for it in items}):
        summary[g] = {}
        for name in conds:
            rs = [v[name] for v in res.values() if v["group"] == g]
            summary[g][name] = {"n": len(rs), "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                                "acc_both": sum(x["both"] for x in rs) / len(rs),
                                "mean_margin": sum(x["margin"] for x in rs) / len(rs)}
    run = f"e14_{args.model.split('/')[-1]}_L{args.layer}{args.tag}"
    (ROOT / "results" / f"{run}.json").write_text(json.dumps(
        {"args": vars(args), "vectors": info, "items": res, "summary": summary}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    torch.save(base, ROOT / "results" / f"{run}.pt")
    for g, row in summary.items():
        print(f"\n{g} (n={row['none']['n']})")
        for name, s in row.items():
            print(f"  {name:11s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}  m={s['mean_margin']:+.2f}")


if __name__ == "__main__":
    main()
