"""E3: 概念の定義を、中間層に加えるベクトルへコンパイルする（接続層 C1）。

仕組み:
  - 本体の重みは固定する。
  - 概念ごとに1本のベクトルを持つ。入力の中でその概念の語が現れたトークン位置で、
    指定した層の出力（残差）にベクトルを加える。語 → 概念の束縛は文字列一致で行う。
  - 学習（コンパイル）: 「語の定義を答えよ」という問いに対して、モデルが定義文を
    出力するようにベクトルだけを最適化する。教師は定義文だけで、設問は使わない。

評価（E1 と同じ二択、同じ指標）:
  none      定義もベクトルもなし
  vec       ベクトルだけ（定義文は文脈に置かない）
  near      定義文を設問の直前に置く（E1 の near）
  near+vec  両方

使い方:
  python e3_concept_vectors.py --model Qwen/Qwen2.5-1.5B-Instruct --layer 8 --groups G2c G2k
"""
import argparse
import json
import time
from pathlib import Path

import torch

from e1_context_injection import ROOT, Runner, question_text

TEMPLATES = [
    "「{L}」とは何ですか。当プロジェクトでの定義を答えてください。",
    "当プロジェクトの用語「{L}」の定義を教えてください。",
    "{L}の意味を、当プロジェクトの定義で説明してください。",
]


class Injector:
    """指定した層の出力に、位置ごとのベクトルを加えるフック。"""

    def __init__(self, model, layer: int):
        self.delta = None  # [batch, seq, d] または None
        self.handle = model.model.layers[layer].register_forward_hook(self._hook)

    def _hook(self, module, args, output):
        if self.delta is None:
            return None
        if isinstance(output, tuple):
            return (output[0] + self.delta,) + tuple(output[1:])
        return output + self.delta


def label_mask(tok, text: str, label: str):
    """text をトークン化し、label に重なるトークン位置のマスクを返す。"""
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    spans, start = [], 0
    while (i := text.find(label, start)) >= 0:
        spans.append((i, i + len(label)))
        start = i + len(label)
    mask = [any(s < e and a < b for a, b in spans) for s, e in enc.offset_mapping]
    return enc.input_ids, mask


def build_delta(tok, text: str, vectors: dict, d_model: int):
    """text に現れる各概念の語の位置に、その概念のベクトルを置いた delta を作る。"""
    ids = tok(text, add_special_tokens=False).input_ids
    delta = torch.zeros(1, len(ids), d_model)
    for label, v in vectors.items():
        _, mask = label_mask(tok, text, label)
        m = torch.tensor(mask, dtype=torch.float32).view(1, -1, 1)
        delta = delta + m * v.view(1, 1, -1)
    return torch.tensor([ids]), delta


def train_vector(r, inj, label, definition, steps, lr, objective="def", qa=None):
    """objective: def = 定義文の暗唱 / qa = 適用例の二択 / defqa = 両方"""
    d_model = r.model.config.hidden_size
    v = torch.zeros(d_model, requires_grad=True)
    opt = torch.optim.Adam([v], lr=lr)
    pairs = []  # (プロンプト, 続き)
    if "def" in objective:
        for t in TEMPLATES:
            pairs.append((r.render(None, t.format(L=label)), definition + r.tok.eos_token))
    if "qa" in objective:
        for ex in qa:
            for swap in (False, True):
                body, correct_no = question_text(ex, swap)
                pairs.append((r.render(None, body), str(correct_no)))
    batch = []
    for prompt, cont in pairs:
        full = prompt + cont
        n_prompt = len(r.tok(prompt, add_special_tokens=False).input_ids)
        ids, mask = label_mask(r.tok, full, label)
        ids = torch.tensor([ids])
        labels = ids.clone()
        labels[:, :n_prompt] = -100
        m = torch.tensor(mask, dtype=torch.float32).view(1, -1, 1)
        batch.append((ids, labels, m))
    losses = []
    for _ in range(steps):
        opt.zero_grad()
        total = 0.0
        for ids, labels, m in batch:
            inj.delta = m * v.view(1, 1, -1)
            loss = r.model(ids, labels=labels).loss / len(batch)
            loss.backward()
            total += loss.item()
        opt.step()
        losses.append(total)
    inj.delta = None
    return v.detach(), losses


@torch.no_grad()
def eval_item(r: Runner, inj: Injector, item, defs, vectors, use_def: bool, use_vec: bool):
    d_model = r.model.config.hidden_size
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(item, swap)
        if use_def:
            body = "次の定義に従うこと。\n" + "\n".join(defs[d] for d in item["defs"]) + "\n\n" + body
        text = r.render(None, body)
        if use_vec:
            vs = {d: vectors[d] for d in item["defs"] if d in vectors}
            ids, inj.delta = build_delta(r.tok, text, vs, d_model)
        else:
            ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
            inj.delta = None
        last = r.model(ids).logits[0, -1]
        inj.delta = None
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--groups", nargs="+", default=["G2c", "G2k"])
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--limit", type=int, default=0, help="概念数の上限（試行用）")
    ap.add_argument("--objective", choices=["def", "qa", "defqa"], default="def")
    ap.add_argument("--tag", default="")
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
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)

    vectors, train_log = {}, {}
    for c in concepts:
        t0 = time.time()
        v, losses = train_vector(r, inj, c, defs[c], args.steps, args.lr, args.objective, qa.get(c))
        vectors[c] = v
        train_log[c] = {"loss_first": losses[0], "loss_last": losses[-1], "norm": v.norm().item()}
        print(
            f"[train] {c}: loss {losses[0]:.2f} -> {losses[-1]:.2f}  |v|={v.norm():.1f}  {time.time() - t0:.0f}s",
            flush=True,
        )

    conds = {"none": (False, False), "vec": (False, True), "near": (True, False), "near+vec": (True, True)}
    res = {}
    for it in items:
        res[it["id"]] = {"group": it["group"]}
        for name, (use_def, use_vec) in conds.items():
            res[it["id"]][name] = eval_item(r, inj, it, defs, vectors, use_def, use_vec)

    summary = {}
    for g in sorted({it["group"] for it in items}):
        summary[g] = {}
        for name in conds:
            rs = [v[name] for v in res.values() if v["group"] == g]
            summary[g][name] = {
                "n": len(rs),
                "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                "acc_both": sum(x["both"] for x in rs) / len(rs),
                "mean_margin": sum(x["margin"] for x in rs) / len(rs),
            }

    name = f"e3_{args.model.split('/')[-1]}_L{args.layer}{args.tag}"
    out = ROOT / "results" / f"{name}.json"
    out.write_text(
        json.dumps(
            {"args": vars(args), "train": train_log, "items": res, "summary": summary},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    torch.save(vectors, ROOT / "results" / f"{name}.pt")

    print(f"\nmodel={args.model} layer={args.layer} steps={args.steps} lr={args.lr}")
    for g, row in summary.items():
        print(f"\n{g} (n={row['none']['n']})")
        for cname, s in row.items():
            print(f"  {cname:9s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}  m={s['mean_margin']:+.2f}")


if __name__ == "__main__":
    main()
