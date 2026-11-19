"""E28: 前に並ぶ定義による追従の低下は、注意機構で前の定義へ届く経路を通るか（#18）。

E7（Qwen3-4B）では、全55定義のうち関係する定義を末尾に置く（gl55-last）と、先頭に置く（gl55-first）より
再定義・衝突の正答率が下がった（0.71 → 0.54）。一方、無関係な文章を前に置いても下がらなかった（fill2000-def）。
ここでは、gl55-last で前に並ぶ無関係な54定義へ届く注意を塞ぎ、下がった分が戻るかを見る。

設問は E7 と同じ G2c（24 問 × 2 順序）。プロンプトの組み立ては E7 の gl55-first・gl55-last と同じ
（others は Random(項目の id) で並べ替えた無関係な定義）。

範囲:
  others の範囲 = 無関係な定義を改行でつないだ文字列に重なるトークン。
  rel の範囲    = 関係する定義を改行でつないだ文字列に重なるトークン。
注意の遮断は E26 と同じ: 全層で、指定した位置（行）から others の範囲（列）への注意を -inf で塞ぐ。
他の位置への注意と因果の形はそのまま。

条件:
  first             gl55-first（遮断なし）
  last              gl55-last（遮断なし）
  last_block_all    last で、others の範囲より後のすべての位置から others へ遮断
  last_block_def    last で、rel の範囲の位置からだけ others へ遮断（定義の読み込みへの混入）
  last_block_query  last で、rel の範囲より後の位置（設問と答えの位置）からだけ others へ遮断
  first_block       first で、others の範囲より後のすべての位置から others へ遮断（対照: 後に並ぶ定義を塞ぐ）

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy（2順序とも正答）、logit_margin。

判定（gap = first − last の accuracy）:
  前提: gap ≥ 0.10。満たさなければ inconclusive（低下が再現しない）。
  causes        last_block_all − last ≥ 0.5 × gap、かつ first_block − first < 0.5 × gap
  not_cause     last_block_all − last < 0.5 × gap
  inconclusive  それ以外（後に並ぶ定義を塞いでも同じだけ上がる）
  経路の分け（last_block_def・last_block_query）は記録し、次の読みを前もって置くが、判定には使わない:
    def_route    block_def − last ≥ 0.5 × gap、かつ block_query − last < 0.5 × gap
    query_route  block_query − last ≥ 0.5 × gap、かつ block_def − last < 0.5 × gap
    both / neither それ以外（両方が満たす / 両方が満たさない）

注意の重みの観察（b_attention_observe_and_block の「観察」）は、4B で全層の注意を保持するとメモリが足りないため、
ここでは行わない。

使い方:
  python e28_preceding_attention.py --model Qwen/Qwen3-4B --dtype bfloat16
"""
import argparse
import json
import random
import time

import torch

from e1_context_injection import ROOT, Runner, question_text

HEADER = "以下は当プロジェクトの用語集である。回答はこの用語集の定義に従うこと。\n"
CONDS = ["first", "last", "last_block_all", "last_block_def", "last_block_query", "first_block"]


class AttnBlocker:
    def __init__(self, model):
        self.mask = None
        for lay in model.model.layers:
            lay.self_attn.register_forward_pre_hook(self._pre, with_kwargs=True)

    def _pre(self, module, args, kwargs):
        if self.mask is not None:
            kwargs["attention_mask"] = self.mask
        return args, kwargs


def span(enc, text, sub):
    i = text.find(sub)
    assert i >= 0 and text.find(sub, i + 1) < 0, sub[:20]
    j = i + len(sub)
    return [k for k, (s, e) in enumerate(enc.offset_mapping) if s < j and i < e]


def mask_of(n, cols, rows, dtype):
    m = torch.full((n, n), float("-inf")).triu(1)
    for c in cols:
        m[rows, c] = float("-inf")
    return m.to(dtype)[None, None]


@torch.no_grad()
def margin_of(r, blk, ids, correct_no, mask):
    blk.mask = mask
    last = r.model(torch.tensor([ids])).logits[0, -1].float()
    blk.mask = None
    l1, l2 = last[r.id1].item(), last[r.id2].item()
    return (l1 - l2) if correct_no == 1 else (l2 - l1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2c"]
    if args.limit:
        items = items[: args.limit]
    r = Runner(args.model, args.dtype)
    blk = AttnBlocker(r.model)
    dt = getattr(torch, args.dtype)

    rows, spans = [], []
    for it in items:
        rel = list(it["defs"])
        others = [d for d in defs if d not in rel]
        random.Random(it["id"]).shuffle(others)
        rel_t = "\n".join(defs[d] for d in rel)
        oth_t = "\n".join(defs[d] for d in others)
        ms = {c: [] for c in CONDS}
        t0 = time.time()
        for swap in (False, True):
            body, correct_no = question_text(it, swap)
            for where in ("first", "last"):
                sys_t = HEADER + (rel_t + "\n" + oth_t if where == "first" else oth_t + "\n" + rel_t)
                full = r.render(sys_t, body)
                enc = r.tok(full, add_special_tokens=False, return_offsets_mapping=True)
                ids, n = enc.input_ids, len(enc.input_ids)
                opos, rpos = span(enc, full, oth_t), span(enc, full, rel_t)
                o_end, r_end = max(opos) + 1, max(rpos) + 1
                if swap is False:
                    spans.append({"id": it["id"], "where": where, "n": n, "n_others": len(opos), "n_rel": len(rpos)})
                ms[where].append(margin_of(r, blk, ids, correct_no, None))
                if where == "first":
                    ms["first_block"].append(margin_of(r, blk, ids, correct_no, mask_of(n, opos, slice(o_end, n), dt)))
                else:
                    assert o_end <= min(rpos)
                    ms["last_block_all"].append(margin_of(r, blk, ids, correct_no, mask_of(n, opos, slice(o_end, n), dt)))
                    ms["last_block_def"].append(margin_of(r, blk, ids, correct_no, mask_of(n, opos, rpos, dt)))
                    ms["last_block_query"].append(margin_of(r, blk, ids, correct_no, mask_of(n, opos, slice(r_end, n), dt)))
        row = {"id": it["id"]}
        row.update({c: {"margin": sum(v) / 2, "both": all(x > 0 for x in v)} for c, v in ms.items()})
        rows.append(row)
        print(it["id"], f"{time.time() - t0:.0f}s", {c: round(row[c]["margin"], 2) for c in CONDS}, flush=True)

    s = {c: {"n": len(rows), "acc": sum(x[c]["margin"] > 0 for x in rows) / len(rows),
             "acc_both": sum(x[c]["both"] for x in rows) / len(rows),
             "mean_margin": sum(x[c]["margin"] for x in rows) / len(rows)} for c in CONDS}
    gap = s["first"]["acc"] - s["last"]["acc"]
    up = {c: s[c]["acc"] - s["last"]["acc"] for c in ("last_block_all", "last_block_def", "last_block_query")}
    first_up = s["first_block"]["acc"] - s["first"]["acc"]
    if gap < 0.10:
        verdict = "inconclusive"
    elif up["last_block_all"] < 0.5 * gap:
        verdict = "not_cause"
    elif first_up < 0.5 * gap:
        verdict = "causes"
    else:
        verdict = "inconclusive"
    d_ok, q_ok = up["last_block_def"] >= 0.5 * gap, up["last_block_query"] >= 0.5 * gap
    route = {(True, False): "def_route", (False, True): "query_route", (True, True): "both"}.get((d_ok, q_ok), "neither")
    tag = "_limit" + str(args.limit) if args.limit else ""
    out = ROOT / "results" / f"e28_{args.model.split('/')[-1]}{tag}.json"
    out.write_text(json.dumps({"args": vars(args), "spans": spans, "items": rows, "summary": {"all": s},
                               "gap": gap, "verdict": verdict, "route": route}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    for c, v in s.items():
        print(f"{c:17s} acc={v['acc']:.3f} both={v['acc_both']:.3f} margin={v['mean_margin']:.3f}")
    print("gap:", gap, "verdict:", verdict, "route:", route)


if __name__ == "__main__":
    main()
