"""E26: 定義文の効き目は、注意機構で定義の語へ届く経路を通るか（#57）。

組は e4・E22 と同じ手で作った data/modifiers_ja.json（甲種/乙種、青/赤、一類/二類。体系からは取らない）。
設問は、組ごとの学習用と学習していない上位の全問（計 48 問 × 2 順序）。学習はしない。

text の入力は E22 と同じ: 「次の定義に従うこと。」＋修飾の定義文＋空行＋設問。
定義の範囲 = 定義文（各行を改行でつないだ文字列）に重なるトークン。

注意の遮断: 定義の範囲より後のすべての位置から、定義の範囲のトークンへの注意を -inf で塞ぐ。
層ごとに、注意の部品へ渡す attention_mask を差し替えて行う（他の位置への注意と因果の形はそのまま）。

条件:
  none          何もなし
  text          定義文を置く
  block_all     text で、全層（0〜27）の注意を遮断
  ctrl_all      text で、全層の注意を、定義の範囲の直前の同じ数のトークン（雛形・system 文・
                指示の行。先頭のトークンは塞がない）へ遮断する（定義でない文脈を同じ数だけ塞ぐ対照）
  block_early   text で、層 0〜9 だけ遮断
  block_mid     text で、層 10〜18 だけ遮断
  block_late    text で、層 19〜27 だけ遮断

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）、logit_margin。

判定（全 48 問で。gain = text の accuracy − none の accuracy）:
  前提: gain ≥ 0.20。満たさなければ inconclusive（定義文の効き目がない）。
  前提: 先頭のトークンを除いて、定義の範囲の前に同じ数のトークンがある（対照が同じ数を塞げる）。満たさなければ inconclusive。
  carries      text − block_all ≥ 0.5 × gain、かつ text − ctrl_all < 0.5 × gain
  not_carry    text − block_all < 0.5 × gain
  inconclusive それ以外（対照でも同じだけ落ちる）
  層の帯（early・mid・late）は記録するが、判定には使わない。

使い方:
  python e26_attention_text_route.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner, question_text

BANDS = {"early": range(0, 10), "mid": range(10, 19), "late": range(19, 28)}


class AttnBlocker:
    def __init__(self, model):
        self.mask, self.layers = None, set()
        for L, lay in enumerate(model.model.layers):
            lay.self_attn.register_forward_pre_hook(self._make(L), with_kwargs=True)

    def _make(self, L):
        def pre(module, args, kwargs):
            if self.mask is not None and L in self.layers:
                kwargs["attention_mask"] = self.mask
            return args, kwargs

        return pre


def span_tokens(r, text, sub):
    enc = r.tok(text, add_special_tokens=False, return_offsets_mapping=True)
    i = text.find(sub)
    assert i >= 0 and text.find(sub, i + 1) < 0, sub
    j = i + len(sub)
    pos = [k for k, (s, e) in enumerate(enc.offset_mapping) if s < j and i < e]
    return enc.input_ids, pos


def block_mask(n, keys, after):
    m = torch.full((n, n), float("-inf")).triu(1)
    for k in keys:
        m[after:, k] = float("-inf")
    return m[None, None]


@torch.no_grad()
def margin_of(r, blk, ids, correct_no, mask, layers):
    blk.mask, blk.layers = mask, set(layers)
    last = r.model(torch.tensor([ids])).logits[0, -1]
    blk.mask, blk.layers = None, set()
    l1, l2 = last[r.id1].item(), last[r.id2].item()
    return (l1 - l2) if correct_no == 1 else (l2 - l1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    pairs = json.loads((ROOT / "data" / "modifiers_ja.json").read_text(encoding="utf-8"))["pairs"]
    r = Runner(args.model)
    blk = AttnBlocker(r.model)
    n_layers = len(r.model.model.layers)

    conds = ["none", "text", "block_all", "ctrl_all"] + [f"block_{b}" for b in BANDS]
    items, spans = [], []
    for pair in pairs:
        defs = "\n".join(pair["defs"].values())
        prefix = "次の定義に従うこと。\n" + defs + "\n\n"
        for split in ("train", "test"):
            for ex in pair[split]:
                ms = {c: [] for c in conds}
                for swap in (False, True):
                    body, correct_no = question_text(ex, swap)
                    ids0, _ = span_tokens(r, r.render(None, body), body)
                    ms["none"].append(margin_of(r, blk, ids0, correct_no, None, []))
                    full = r.render(None, prefix + body)
                    ids, dpos = span_tokens(r, full, defs)
                    n, after = len(ids), max(dpos) + 1
                    ctrl = list(range(max(1, dpos[0] - len(dpos)), dpos[0]))
                    spans.append({"n_def": len(dpos), "n_ctrl": len(ctrl)})
                    ms["text"].append(margin_of(r, blk, ids, correct_no, None, []))
                    m_def = block_mask(n, dpos, after)
                    ms["block_all"].append(margin_of(r, blk, ids, correct_no, m_def, range(n_layers)))
                    ms["ctrl_all"].append(margin_of(r, blk, ids, correct_no, block_mask(n, ctrl, after), range(n_layers)))
                    for b, Ls in BANDS.items():
                        ms[f"block_{b}"].append(margin_of(r, blk, ids, correct_no, m_def, Ls))
                row = {"pair": "/".join(pair["modifiers"]), "split": split, "q": ex["q"]}
                row.update({c: {"margin": sum(v) / 2, "both": all(x > 0 for x in v)} for c, v in ms.items()})
                items.append(row)
                print(split, {c: round(row[c]["margin"], 2) for c in conds}, flush=True)

    def summ(rows):
        return {c: {"n": len(rows), "acc": sum(x[c]["margin"] > 0 for x in rows) / len(rows),
                    "acc_both": sum(x[c]["both"] for x in rows) / len(rows),
                    "mean_margin": sum(x[c]["margin"] for x in rows) / len(rows)} for c in conds}

    summary = {"all": summ(items)}
    for pr in sorted({x["pair"] for x in items}):
        summary[f"pair:{pr}"] = summ([x for x in items if x["pair"] == pr])
    s = summary["all"]
    gain = s["text"]["acc"] - s["none"]["acc"]
    ctrl_ok = all(sp["n_ctrl"] == sp["n_def"] for sp in spans)
    if gain < 0.20 or not ctrl_ok:
        verdict = "inconclusive"
    elif s["text"]["acc"] - s["block_all"]["acc"] < 0.5 * gain:
        verdict = "not_carry"
    elif s["text"]["acc"] - s["ctrl_all"]["acc"] < 0.5 * gain:
        verdict = "carries"
    else:
        verdict = "inconclusive"
    out = ROOT / "results" / f"e26_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps({"args": vars(args), "bands": {b: list(v) for b, v in BANDS.items()},
                               "spans": spans, "items": items, "summary": summary, "gain": gain,
                               "verdict": verdict}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, row in summary.items():
        print(k, {c: (round(v["acc"], 3), round(v["acc_both"], 3)) for c, v in row.items()})
    print("gain:", gain, "verdict:", verdict)


if __name__ == "__main__":
    main()
