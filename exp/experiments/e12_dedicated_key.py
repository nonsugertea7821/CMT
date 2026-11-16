"""E12: 具象概念に、モデルの中の専用の入口（キー）を与える。

E3 は、語（表示名）のトークン位置にベクトルを足した。表示名はモデルの中で複数の意味の入口を兼ねるので、
足したベクトルは既存の混ざったキーの読み方をずらすだけになる。ここでは概念ごとに新しいトークンを1つ足し、
その入力埋め込みだけを学習する（本体の重みは固定）。語 → 概念の解決は、設問の文字列一致で外から行う
（用語サーバーの役）。

学習（E3 の defqa と同じ教師）:
  - 「<概念>とは何ですか」に対して定義文を答える。定義文の中の語はそのまま（出力に専用トークンは出さない）。
  - 適用例の二択。設問の中の語を専用トークンに置き換える。

評価（E3 と同じ二択、同じ指標）:
  none      語のまま。何も与えない
  tok       設問の中の語を、専用トークンに置き換える
  word+tok  語の直後に専用トークンを添える（語も見える）
  tok0      tok と同じ置き換えで、埋め込みは学習前の初期値（語のトークンの埋め込みの平均）。置き換えそのものの効果を測る

使い方:
  python e12_dedicated_key.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import Injector, train_vector


class EmbedInjector(Injector):
    """入力埋め込み（層に入る前）に、位置ごとのベクトルを加えるフック。"""

    def __init__(self, model):
        self.delta = None
        self.handle = model.model.embed_tokens.register_forward_hook(self._hook)


@torch.no_grad()
def eval_item(r, inj, item, toks, vectors, cond):
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(item, swap)
        used = {}
        for c in item["defs"]:
            if cond == "tok" or cond == "tok0":
                body = body.replace(c, toks[c])
            elif cond == "word+tok":
                body = body.replace(c, c + toks[c])
            if cond in ("tok", "word+tok"):
                used[toks[c]] = vectors[c]
        text = r.render(None, body)
        ids = r.tok(text, add_special_tokens=False).input_ids
        delta = torch.zeros(1, len(ids), r.model.config.hidden_size)
        for t, v in used.items():
            tid = r.tok.convert_tokens_to_ids(t)
            m = torch.tensor([i == tid for i in ids], dtype=torch.float32).view(1, -1, 1)
            delta = delta + m * v.view(1, 1, -1)
        inj.delta = delta if used else None
        last = r.model(torch.tensor([ids])).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.002)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--budget", type=int, default=256, help="一度に流すトークン数の上限（例数 × 幅）。メモリに合わせる")
    args = ap.parse_args()

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in args.groups]
    concepts = sorted({d for it in items for d in it["defs"]})
    if args.limit:
        concepts = concepts[: args.limit]
        items = [it for it in items if all(d in concepts for d in it["defs"])]
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]

    r = Runner(args.model)
    toks = {c: f"<概念{i:02d}>" for i, c in enumerate(concepts)}
    r.tok.add_tokens(list(toks.values()), special_tokens=True)
    emb_old = r.model.get_input_embeddings().weight.shape[0]
    r.model.resize_token_embeddings(len(r.tok))
    emb = r.model.get_input_embeddings().weight
    with torch.no_grad():   # 初期値: 語のトークンの埋め込みの平均
        for c, t in toks.items():
            ids = r.tok(c, add_special_tokens=False).input_ids
            emb[r.tok.convert_tokens_to_ids(t)] = emb[ids].mean(0)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = EmbedInjector(r.model)

    run_name = f"e12_{args.model.split('/')[-1]}{args.tag}"
    part = ROOT / "results" / f"{run_name}.partial.pt"
    vectors, train_log = torch.load(part) if part.exists() else ({}, {})
    for c in concepts:
        if c in vectors:
            continue
        t0 = time.time()
        q = [dict(ex, q=ex["q"].replace(c, toks[c])) for ex in qa.get(c, [])]
        v, losses = train_vector(r, inj, toks[c], defs[c], args.steps, args.lr, "defqa", q, args.budget)
        vectors[c] = v
        train_log[c] = {"loss_first": losses[0], "loss_last": losses[-1], "norm": v.norm().item(),
                        "init_norm": emb[r.tok.convert_tokens_to_ids(toks[c])].norm().item()}
        print(f"[train] {c}: loss {losses[0]:.2f} -> {losses[-1]:.2f}  |v|={v.norm():.2f}  {time.time() - t0:.0f}s", flush=True)
        torch.save((vectors, train_log), part)

    conds = ["none", "tok0", "tok", "word+tok"]
    res = {}
    for it in items:
        res[it["id"]] = {"group": it["group"]}
        for cond in conds:
            res[it["id"]][cond] = eval_item(r, inj, it, toks, vectors, cond)

    summary = {}
    for g in sorted({it["group"] for it in items}):
        summary[g] = {}
        for cond in conds:
            rs = [v[cond] for v in res.values() if v["group"] == g]
            summary[g][cond] = {"n": len(rs), "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                                "acc_both": sum(x["both"] for x in rs) / len(rs),
                                "mean_margin": sum(x["margin"] for x in rs) / len(rs)}
    (ROOT / "results" / f"{run_name}.json").write_text(json.dumps(
        {"args": vars(args), "tokens": toks, "vocab_before": emb_old, "train": train_log, "items": res, "summary": summary},
        ensure_ascii=False, indent=1), encoding="utf-8")
    torch.save(vectors, ROOT / "results" / f"{run_name}.pt")
    print(f"\nmodel={args.model} steps={args.steps} lr={args.lr}")
    for g, row in summary.items():
        print(f"\n{g} (n={row['none']['n']})")
        for cname, s in row.items():
            print(f"  {cname:9s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}  m={s['mean_margin']:+.2f}")


if __name__ == "__main__":
    main()
