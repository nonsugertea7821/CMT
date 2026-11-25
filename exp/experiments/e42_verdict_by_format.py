"""E42: 依存の判定は設問の形に頼るか（h_verdict_by_question_format #724）。

系列:
  E40（#718, Qwen2.5-1.5B）と E41（#721, Qwen3-4B）は、どちらも
  「{A} の定義を変えたとき、{T} の意味は変わるか」を T ごとに二択（変わる / 変わらない）で問うた。
  どちらも前提（extends の acc ≥ 0.75）が崩れた。E41 では P・Q のどちらにも「変わる」が 0.96 以上で、
  依存する側としない側を分けていなかった（extends の acc 0.417）。
  これを、モデルが extends を読めない（h_model_misses_extends）とも、
  T ごとに問う形が「変わる」へ偏らせている（h_verdict_by_question_format）とも読める。2 つを対で登録した（#722）。
  ここでは、同じモデル・同じ項目・同じ定義の集まりで、問う形だけを比べに変える。

モデル: Qwen/Qwen3-4B（bf16。E41 と同じ）。学習はしない。前向き計算だけ。

設問（比べ）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わるのはどちらですか。番号で答えてください。」
  定義の集まり（E41 と同じ snippet。項目も E41 と同じ生成: seed 0）
  1. {P か Q}
  2. {もう一方}
  選択肢の順を入れ替えた 2 回で、d = logit(P の番号) − logit(Q の番号)。
  行の記録は {"margin": d の平均, "both": 両方の順で d > 0}。acc = margin > 0 の割合（24 項目）。
  条件は E41 と同じ 4 つ（extends・inline・named・decoy）。

判定（事前登録。24 項目。比べる相手は E41 の extends の acc 0.4166667）:
  h_verdict_by_question_format（判定は設問の形に頼る）:
    支持: 比べの extends の acc が 0.75 以上（E41 の 0.417 より 0.25 以上高い）。
    反証: 比べの extends の acc が 0.583 以下（形を変えても上がらない。差が 0.17 以下）。
    その間（0.625・0.667・0.708）: 判定しない。
  h_model_misses_extends（モデルは extends を読まない）:
    反証: 比べの extends の acc が 0.75 以上（形を変えれば読める）。
    支持: 比べの extends の acc が 0.583 以下（E41 と合わせ、2 つの形のどちらでも読めない）。
    その間: 判定しない。
  inline・named・decoy は参考（decoy は h_model_reads_by_word を比べの形で見る参考。ここでは判定しない）。

開示:
  - E40・E41 の結果を見てから、この手順を書いた。
  - Qwen3-4B に比べの形の設問を見せたことはない。
  - 2 つの仮説の判定は同じ量（比べの extends の acc）から出るので、独立ではない。

使い方:
  python e42_verdict_by_format.py --model Qwen/Qwen3-4B
  出力: results/e42_<model>.json（途中保存: results/e42_<model>.partial.json）
"""
import argparse
import json
import random

import torch

from e1_context_injection import ROOT, Runner

N_ITEMS = 24
CONDS = ("extends", "inline", "named", "decoy")
SYL = ["ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so", "ta", "te", "to", "na", "ni", "nu", "ne",
       "no", "ha", "hi", "fu", "he", "ho", "ma", "mi", "mu", "me", "mo", "ra", "ri", "ru", "re", "ro"]
HEAD = "次の定義の集まりで、{A} の定義を変えたとします。意味が変わるのはどちらですか。番号で答えてください。"
E41_EXTENDS_ACC = 0.4166667


def make_items(seed=0):
    rng = random.Random(seed)
    used = set()

    def name():
        while True:
            w = "".join(rng.choice(SYL) for _ in range(3))
            if w not in used:
                used.add(w)
                return w

    items = []
    for i in range(N_ITEMS):
        a, b, p, q, m, n = (name() for _ in range(6))
        items.append({"id": i, "A": a, "B": b, "P": p, "Q": q, "M": m, "N": n,
                      "p_first": rng.random() < 0.5, "a_first": rng.random() < 0.5})
    return items


def snippet(it, cond):
    a, b, p, q, m, n = it["A"], it["B"], it["P"], it["Q"], it["M"], it["N"]
    base = [f"{a}: {{extends: entity}}", f"{b}: {{extends: entity}}"]
    mids = []
    if cond == "extends":
        tp, tq = f"{p}: {{extends: {a}}}", f"{q}: {{extends: {b}}}"
    elif cond == "inline":
        tp = f"{p}: {{extends: entity, mod: {{of: [v_depend, from], with: {a}}}}}"
        tq = f"{q}: {{extends: entity, mod: {{of: [v_depend, from], with: {b}}}}}"
    elif cond == "named":
        mids = [f"{m}: {{of: [v_depend, from], with: {a}}}", f"{n}: {{of: [v_depend, from], with: {b}}}"]
        tp, tq = f"{p}: {{extends: entity, mod: {m}}}", f"{q}: {{extends: entity, mod: {n}}}"
    elif cond == "decoy":
        mids = [f"{m}: {{of: [v_depend, from], with: {a}}}"]
        tp, tq = f"{p}: {{extends: entity, mod: {m}}}", f"{q}: {{extends: {b}, val: {{text: '{a}'}}}}"
    else:
        raise ValueError(cond)
    if not it["a_first"]:
        base.reverse()
        mids.reverse()
    tail = [tp, tq] if it["p_first"] else [tq, tp]
    return "\n".join(base + mids + tail)


@torch.no_grad()
def diff(r, it, cond, p_opt_first):
    o = [it["P"], it["Q"]] if p_opt_first else [it["Q"], it["P"]]
    body = f"{HEAD.format(A=it['A'])}\n{snippet(it, cond)}\n1. {o[0]}\n2. {o[1]}"
    l1, l2 = r.logits_12(r.render(None, body))
    return (l1 - l2) if p_opt_first else (l2 - l1)


def verdict(acc, hi, lo):
    return hi if acc >= 0.75 else (lo if acc <= 0.5834 else "not_judged")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e42_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        if cond in out["summary"]:
            continue
        rows = {}
        for it in items:
            ds = [diff(r, it, cond, f) for f in (True, False)]
            rows[str(it["id"])] = {"pair": {"margin": sum(ds) / 2, "both": all(d > 0 for d in ds)},
                                   "snippet": snippet(it, cond)}
        out["items"][cond] = rows
        vs = list(rows.values())
        out["summary"][cond] = {
            "acc": sum(v["pair"]["margin"] > 0 for v in vs) / len(vs),
            "both_acc": sum(v["pair"]["both"] for v in vs) / len(vs),
            "mean_margin": sum(v["pair"]["margin"] for v in vs) / len(vs),
        }
        print(cond, json.dumps(out["summary"][cond]), flush=True)
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    acc = out["summary"]["extends"]["acc"]
    out["judgment"] = {
        "e41_extends_acc": E41_EXTENDS_ACC,
        "verdict_by_question_format": verdict(acc, "supported", "refuted"),
        "model_misses_extends": verdict(acc, "refuted", "supported"),
    }
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e42_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
