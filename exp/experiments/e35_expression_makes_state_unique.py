"""E35: h_expression_makes_state_unique を確かめる: 文脈に概念式を与えると、語を隠した状態の読み出しが一意になるか。

仮説（exp.yaml）: v_refer(h, v_depend(hidden_state, syntax.concept_expression))。
  出どころ: E34（#642）の反証。語を隠した状態は、モデル自身の読み出しで平均 2.87 語に広がり、一意は 0.407 だった。
  対の片方（h_state_points_region）は、一意な表示は状態ではなく式から来ると読む。こちらは、式を文脈に与えれば状態が一意になると読む。

操作（モデル Qwen/Qwen2.5-1.5B-Instruct、重みは固定、学習しない）:
  状態を作る文は E34 の S_new と S_old（data/sense_pairs_ja.json の 24 語 × 3 文ずつ、計 144）。語は＿＿で隠す。候補は 24 語。
  条件 none: E34 の結果ファイル（results/e34_state_unique_display.json）の S_new・S_old の行をそのまま使う（走らせ直さない）。
  条件 expr: 設問の前に、候補 24 語の概念式の一覧を置く。一覧は render_expr.Renderer().line で、subj.yaml の式を日本語にした行
    （例「営業日 ＝ 日 ∧ ¬曜日である(日曜, これ)」）。並びは data の語の順で、どの状態でも同じ。
    設問「次の語の概念式を使うこと。\\n<一覧>\\n\\n次の文の＿＿に入る語を一つ答えてください。\\n文：<文>」。
  読み出しは E34 と同じ: 応答の頭に「「」を置き、候補 w ごとに log P(w」 | 文脈) を足し、候補の上で正規化して q とする。
    計算を速くするため、文脈を一度だけ通してキャッシュし、候補の続きをまとめて通す。
    走らせる初めに、データにない固定の設問で、キャッシュありとなしの q の差が 1e-3 未満であることを確かめる（越えれば止まる）。
  状態ごと: hit、n_eff = exp(H(q))、unique = hit かつ n_eff < 2（E34 と同じ）。
集計（s）: 条件（none, expr）× 組（S_new, S_old, S）ごとに n, share_hit, share_unique, mean_n_eff。S は S_new と S_old を合わせたもの。
行（e35_expression_makes_state_unique.json）: expr の状態ごとの行と s。
  途中の結果は e35_expression_makes_state_unique.partial.json に書き、再開のときは済んだ状態を飛ばす。

判定（事前に決める。S の share_unique で）:
  モデルが読めないか、expr の状態が 144 に満たなければ外れ（状態を変えない）。
  支持: share_unique(expr) >= 0.8。
  反証: share_unique(expr) - share_unique(none) <= 0.05。
  mixed: それ以外。
開示:
  - 一覧には正しい語も含め 24 語すべてが名前つきで載る。式は語を隠さない。問うのは、式の一覧があると状態が一つの語に絞れるか。
  - D（定義文）は使わない。55 語のうち subj.yaml に式があるのは 25 語だけで、候補の一覧が作れないため。
  - 閾値 0.8 と 0.05 は走らせる前に決めた。
使い方:
  python e35_expression_makes_state_unique.py
"""
import contextlib
import copy
import io
import json
import math
import time

import torch

from e1_context_injection import ROOT, Runner
import e34_state_unique_display as e34

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
OUT = ROOT / "results" / "e35_expression_makes_state_unique.json"
PART = ROOT / "results" / "e35_expression_makes_state_unique.partial.json"
E34 = ROOT / "results" / "e34_state_unique_display.json"
HEAD = "次の語の概念式を使うこと。\n{}\n\n"
CHECK = ("次の文の＿＿に入る語を一つ答えてください。\n文：朝は＿＿を飲んでから出かける。", ["水", "牛乳", "お茶", "コーヒー"])


@torch.no_grad()
def readout_cached(r, prompt, cands):
    ctx = r.render(None, prompt) + e34.OPEN
    c_ids = r.tok(ctx, add_special_tokens=False).input_ids
    conts = []
    for w in cands:
        full = r.tok(ctx + w + e34.CLOSE, add_special_tokens=False).input_ids
        assert full[:len(c_ids)] == c_ids, "文脈のトークンが一致しない"
        conts.append(full[len(c_ids):])
    out = r.model(input_ids=torch.tensor([c_ids]), use_cache=True)
    first = torch.log_softmax(out.logits[0, -1].float(), -1)
    cache = copy.deepcopy(out.past_key_values)
    cache.batch_repeat_interleave(len(cands))
    L = max(len(x) for x in conts)
    pad = r.tok.pad_token_id if r.tok.pad_token_id is not None else 0
    ids = torch.tensor([x + [pad] * (L - len(x)) for x in conts])
    att = torch.tensor([[1] * len(c_ids) + [1] * len(x) + [0] * (L - len(x)) for x in conts])
    lp = torch.log_softmax(r.model(input_ids=ids, attention_mask=att, past_key_values=cache, use_cache=True).logits.float(), -1)
    scores = []
    for b, x in enumerate(conts):
        s = first[x[0]].item() + sum(lp[b, t - 1, x[t]].item() for t in range(1, len(x)))
        scores.append(s)
    m = max(scores)
    z = [math.exp(v - m) for v in scores]
    tot = sum(z)
    return [v / tot for v in z]


def agg(rs):
    n = len(rs)
    if not n:
        return {"n": 0}
    return {"n": n, "share_hit": sum(x["hit"] for x in rs) / n, "share_unique": sum(x["unique"] for x in rs) / n,
            "mean_n_eff": sum(x["n_eff"] for x in rs) / n}


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        import render_expr
        R = render_expr.Renderer()
    pairs = json.loads((ROOT / "data" / "sense_pairs_ja.json").read_text(encoding="utf-8"))["pairs"]
    gloss = "\n".join(R.line(R.by_ja[w]) for w in pairs)
    r = Runner(MODEL)
    a = e34.readout(r, *CHECK)
    b = readout_cached(r, *CHECK)
    diff = max(abs(x - y) for x, y in zip(a, b))
    assert diff < 1e-3, f"キャッシュありとなしの q が食い違う: {diff}"
    print(f"cache check diff={diff:.2e}", flush=True)
    done = json.loads(PART.read_text(encoding="utf-8")) if PART.exists() else {}
    for st, key, prompt, cands in e34.states():
        if st == "D":
            continue
        k = f"{st}/{key}"
        if k in done:
            continue
        t = time.time()
        q = readout_cached(r, HEAD.format(gloss) + prompt, cands)
        w = key.split("#")[0]
        top = cands[max(range(len(q)), key=q.__getitem__)]
        n_eff = math.exp(-sum(x * math.log(x) for x in q if x > 0))
        hit = top == w
        done[k] = {"set": st, "word": key, "top": top, "q_max": max(q), "q_true": q[cands.index(w)],
                   "n_eff": n_eff, "hit": hit, "unique": hit and n_eff < 2}
        PART.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{k} top={top} q_max={max(q):.2f} n_eff={n_eff:.2f} {time.time() - t:.0f}s", flush=True)
    none = [v for v in json.loads(E34.read_text(encoding="utf-8"))["rows"].values() if v["set"] != "D"]
    expr = list(done.values())
    s = {}
    for c, rows in (("none", none), ("expr", expr)):
        for g in ("S_new", "S_old"):
            s[f"{c}_{g}"] = agg([x for x in rows if x["set"] == g])
        s[f"{c}_S"] = agg(rows)
    s["delta_S"] = {"share_unique": s["expr_S"]["share_unique"] - s["none_S"]["share_unique"],
                    "share_hit": s["expr_S"]["share_hit"] - s["none_S"]["share_hit"],
                    "mean_n_eff": s["expr_S"]["mean_n_eff"] - s["none_S"]["mean_n_eff"]}
    OUT.write_text(json.dumps({"cache_check_diff": diff, "gloss": gloss, "rows": done, "s": s}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    PART.unlink()
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
