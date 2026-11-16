"""E8: 概念ベクトルを、連続する複数の層に薄く分けて加える。

仮説: 語の意味への依存は単一の層にあるのではなく、多くの層に薄く分布している。
1つの層を大きなベクトルで押すのではなく、複数の層を小さなベクトルで押す方が、
語の使い方が共有する推論に届くのではないか。

仕組み:
  - 概念ごとに、指定した各層に1本ずつベクトルを持つ（形は [層の数, 次元]）。
  - 語が現れた位置で、各層の出力にその層のベクトルを加える。
  - 学習の損失に、ベクトルの大きさへの罰則（--decay × 二乗和）を加える。
  - 教師は、定義文の暗唱と適用例の両方（e3 の defqa と同じ）。

測るもの:
  apply          適用する（G2c 衝突する設問 / G2k 衝突しない設問）。none と vec
  define_choice  定義の言い換えの二択（教えていない使い方）
  define_nll     定義文の出しやすさ
  norms          学習後の、層ごとのベクトルの大きさ（全概念の平均）

使い方:
  python e8_multilayer.py --model Qwen/Qwen2.5-1.5B-Instruct --layers 2-13 --decay 0.001
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import TEMPLATES, label_mask
from e6_cross_use import INSTR


class MultiInjector:
    """複数の層の出力に、層ごとの delta を加える。"""

    def __init__(self, model, layers):
        self.layers = layers
        self.deltas = None  # {層: [batch, seq, d]}
        for L in layers:
            model.model.layers[L].register_forward_hook(self._make(L))

    def _make(self, L):
        def hook(module, args, output):
            if self.deltas is None:
                return None
            h = output[0] if isinstance(output, tuple) else output
            d = self.deltas[L]
            if h.shape[1] != d.shape[1]:
                return None
            return (h + d,) + tuple(output[1:]) if isinstance(output, tuple) else h + d

        return hook

    def set(self, mask, v):
        """mask: [batch, seq, 1]、v: [層の数, 次元]"""
        self.deltas = None if v is None else {L: mask * v[i].view(1, 1, -1) for i, L in enumerate(self.layers)}


def pad_batch(r, rows):
    n, width = len(rows), max(len(ids) for ids, _, _ in rows)
    pad = r.tok.pad_token_id if r.tok.pad_token_id is not None else r.tok.eos_token_id
    ids_b = torch.full((n, width), pad)
    att_b = torch.zeros((n, width), dtype=torch.long)
    lab_b = torch.full((n, width), -100)
    msk_b = torch.zeros((n, width, 1))
    for i, (ids, n_prompt, mask) in enumerate(rows):
        k = len(ids)
        ids_b[i, :k] = torch.tensor(ids)
        att_b[i, :k] = 1
        lab_b[i, n_prompt:k] = torch.tensor(ids[n_prompt:])
        msk_b[i, :k, 0] = torch.tensor(mask, dtype=torch.float32)
    return ids_b, att_b, lab_b, msk_b


def encode(r, prompt, cont, label):
    full = prompt + cont
    n_prompt = len(r.tok(prompt, add_special_tokens=False).input_ids)
    ids, mask = label_mask(r.tok, full, label)
    return ids, n_prompt, mask


def train(r, inj, label, definition, qa, steps, lr, decay, chunk=4):
    d = r.model.config.hidden_size
    v = torch.zeros(len(inj.layers), d, requires_grad=True)
    opt = torch.optim.Adam([v], lr=lr)
    rows = [encode(r, r.render(None, t.format(L=label)), definition + r.tok.eos_token, label) for t in TEMPLATES]
    for ex in qa:
        for swap in (False, True):
            body, correct_no = question_text(ex, swap)
            rows.append(encode(r, r.render(None, body), str(correct_no), label))
    ids_b, att_b, lab_b, msk_b = pad_batch(r, rows)
    n = len(rows)
    first = last = None
    for _ in range(steps):
        opt.zero_grad()
        total = 0.0
        for i in range(0, n, chunk):
            sl = slice(i, i + chunk)
            inj.set(msk_b[sl], v)
            logits = r.model(ids_b[sl], attention_mask=att_b[sl]).logits
            per_tok = torch.nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, logits.shape[-1]), lab_b[sl, 1:].reshape(-1), reduction="none"
            ).view(logits.shape[0], -1)
            valid = (lab_b[sl, 1:] != -100).float()
            loss = ((per_tok * valid).sum(1) / valid.sum(1)).sum() / n
            loss.backward()
            total += loss.item()
        (decay * v.pow(2).sum()).backward()
        opt.step()
        first = total if first is None else first
        last = total
    inj.set(None, None)
    return v.detach(), first, last


@torch.no_grad()
def two_choice(r, inj, body_of, label, v):
    """body_of(swap) -> (設問の本文, 正答の番号)。2順序の平均 margin を返す。"""
    ms = []
    for swap in (False, True):
        body, correct_no = body_of(swap)
        text = r.render(None, body)
        ids, mask = label_mask(r.tok, text, label)
        inj.set(torch.tensor(mask, dtype=torch.float32).view(1, -1, 1), v)
        last = r.model(torch.tensor([ids])).logits[0, -1]
        inj.set(None, None)
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


@torch.no_grad()
def define_nll(r, inj, label, definition, v):
    total = 0.0
    for t in TEMPLATES:
        ids, n_prompt, mask = encode(r, r.render(None, t.format(L=label)), definition, label)
        ids = torch.tensor([ids])
        labels = ids.clone()
        labels[:, :n_prompt] = -100
        inj.set(torch.tensor(mask, dtype=torch.float32).view(1, -1, 1), v)
        total += r.model(ids, labels=labels).loss.item()
        inj.set(None, None)
    return total / len(TEMPLATES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layers", required=True, help="例: 2-13")
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.03)
    ap.add_argument("--decay", type=float, default=0.001)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    lo, hi = map(int, args.layers.split("-"))
    layers = list(range(lo, hi + 1))

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]
    choice = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in ("G2c", "G2k")]
    concepts = sorted({it["defs"][0] for it in items})
    if args.limit:
        concepts = concepts[: args.limit]
        items = [it for it in items if it["defs"][0] in concepts]

    r = Runner(args.model)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = MultiInjector(r.model, layers)

    run = f"e8_L{args.layers}_d{args.decay}{args.tag}"
    part = ROOT / "results" / f"{run}.partial.pt"
    vectors, log = torch.load(part) if part.exists() else ({}, {})
    for c in concepts:
        if c in vectors:
            continue
        t0 = time.time()
        v, first, last = train(r, inj, c, defs[c], qa[c], args.steps, args.lr, args.decay)
        vectors[c] = v
        log[c] = {"loss_first": first, "loss_last": last, "norms": v.norm(dim=1).tolist()}
        print(f"[train] {c}: loss {first:.2f} -> {last:.2f}  |v|層平均={v.norm(dim=1).mean():.2f}  {time.time() - t0:.0f}s", flush=True)
        torch.save((vectors, log), part)

    res = {}
    for it in items:
        c = it["defs"][0]
        res[it["id"]] = {
            "group": it["group"],
            "none": two_choice(r, inj, lambda s, it=it: question_text(it, s), c, None),
            "vec": two_choice(r, inj, lambda s, it=it: question_text(it, s), c, vectors[c]),
        }
    dc = {}
    for c in concepts:
        pair = choice[c]

        def body_of(swap, c=c, pair=pair):
            opts = [pair["project"], pair["ordinary"]]
            if swap:
                opts.reverse()
            return f"{INSTR.format(L=c)}\n1. {opts[0]}\n2. {opts[1]}", (2 if swap else 1)

        dc[c] = {
            "none": two_choice(r, inj, body_of, c, None),
            "vec": two_choice(r, inj, body_of, c, vectors[c]),
            "nll": define_nll(r, inj, c, defs[c], vectors[c]),
        }

    norms = torch.tensor([log[c]["norms"] for c in concepts]).mean(0).tolist()
    (ROOT / "results" / f"{run}.json").write_text(
        json.dumps({"args": vars(args), "layers": layers, "train": log, "apply": res, "define": dc, "norms": norms},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    torch.save(vectors, ROOT / "results" / f"{run}.pt")
    part.unlink(missing_ok=True)

    print(f"\nlayers={args.layers} decay={args.decay} lr={args.lr} steps={args.steps}")
    print("表記: 正答率(順序を入れ替えても両方正答する率)")
    for g in ("G2c", "G2k"):
        rs = [v for v in res.values() if v["group"] == g]
        print(f"適用 {g}: " + "  ".join(
            f"{k}={sum(x[k]['margin'] > 0 for x in rs) / len(rs):.2f}({sum(x[k]['both'] for x in rs) / len(rs):.2f})"
            for k in ("none", "vec")))
    n = len(dc)
    print("定義の言い換え: " + "  ".join(
        f"{k}={sum(x[k]['margin'] > 0 for x in dc.values()) / n:.2f}({sum(x[k]['both'] for x in dc.values()) / n:.2f})"
        for k in ("none", "vec")) + f"   定義文の出しやすさ={sum(x['nll'] for x in dc.values()) / n:.2f}")
    print("層ごとの大きさ: " + "  ".join(f"L{L}={x:.2f}" for L, x in zip(layers, norms)))


if __name__ == "__main__":
    main()
