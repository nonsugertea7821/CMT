"""E41: モデルは依存を、語の字面で読むか（h_model_reads_by_word #720）。

系列:
  E40（#718）は、Qwen2.5-1.5B で、依存を名前の位置で読むか（h_model_reads_by_name）を測った。
  前提（extends の acc ≥ 0.75）が崩れ（0.667）、判定しなかった。
  inline で「変わる」が増えたのが、行に A の文字列があることへの反応に見えた。
  そこで、字面で読む（h_model_reads_by_word）を対として登録した（54664b1）。
  E40 の設問は、どの条件でも A の文字列が依存する側にあり、2 つの読みを区別できなかった。
  ここでは、A の文字列を、依存しない側だけに置く条件（decoy）を足して分ける。

モデル: Qwen/Qwen3-4B（bf16。E40 より大きい。手元にある一番大きいモデル）。学習はしない。前向き計算だけ。

設問: E40 と同じ形。意味のない名前の小さな定義の集まりを見せ、
  「{A} の定義を変えたとき、{T} の意味は変わるか」を二択（変わる / 変わらない）で問う。
  T は、A に依存する P と、A に依存しない Q。
  条件（名前は項目ごとに同じ。書き方だけ違う）:
    extends  P: {extends: A}                  Q: {extends: B}
    inline   P: {extends: entity, mod: {of: [v_depend, from], with: A}}   Q: 同じ形で B
    named    M: {of: [v_depend, from], with: A}、P: {extends: entity, mod: M}   Q: 同じ形で N（B）
    decoy    M: {of: [v_depend, from], with: A}、P: {extends: entity, mod: M}
             Q: {extends: B, val: {text: 'A'}}
             （A の文字列は Q の行だけにある。P の行にはない。依存するのは P）
  行の順は項目ごとに混ぜる（seed 0）。

測る量:
  選択肢の順ごとに d = score(P) − score(Q)（score は「変わる」−「変わらない」の logit の差）。
  行の記録は {"margin": d の平均, "both": 両方の順で d > 0}。acc = margin > 0 の割合（24 項目）。

判定（事前登録。24 項目）:
  前提: extends の acc が 0.75 以上。崩れたら判定しない。
  h_model_reads_by_word:
    支持（字面で読む）: decoy の acc が 0.25 以下（A の文字列がある、依存しない側を選ぶ）。
    反証: それ以外。
  extends・inline・named は参考（h_model_reads_by_name は #718 で扱うので、ここでは判定しない）。

開示:
  - E40 の結果（上）を見てから、この手順を書いた。
  - Qwen3-4B にこの種の設問を見せたことはない。

使い方:
  python e41_reads_by_word.py --model Qwen/Qwen3-4B
  出力: results/e41_<model>.json（途中保存: results/e41_<model>.partial.json）
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
HEAD = "次の定義の集まりで、{A} の定義を変えたとします。{T} の意味は変わりますか。番号で答えてください。"
OPTS = ("変わる", "変わらない")


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
def score(r, it, cond, target, swap):
    opts = list(OPTS)
    if swap:
        opts.reverse()
    body = f"{HEAD.format(A=it['A'], T=target)}\n{snippet(it, cond)}\n1. {opts[0]}\n2. {opts[1]}"
    l1, l2 = r.logits_12(r.render(None, body))
    return (l2 - l1) if swap else (l1 - l2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e41_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        if cond in out["summary"]:
            continue
        rows = {}
        for it in items:
            ds, sp, sq = [], [], []
            for swap in (False, True):
                a, b = score(r, it, cond, it["P"], swap), score(r, it, cond, it["Q"], swap)
                sp.append(a)
                sq.append(b)
                ds.append(a - b)
            rows[str(it["id"])] = {"pair": {"margin": sum(ds) / 2, "both": all(d > 0 for d in ds)},
                                   "p_score": sum(sp) / 2, "q_score": sum(sq) / 2, "snippet": snippet(it, cond)}
        out["items"][cond] = rows
        vs = list(rows.values())
        out["summary"][cond] = {
            "acc": sum(v["pair"]["margin"] > 0 for v in vs) / len(vs),
            "mean_margin": sum(v["pair"]["margin"] for v in vs) / len(vs),
            "p_yes": sum(v["p_score"] > 0 for v in vs) / len(vs),
            "q_yes": sum(v["q_score"] > 0 for v in vs) / len(vs),
        }
        print(cond, json.dumps(out["summary"][cond]), flush=True)
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    s = out["summary"]
    pre = s["extends"]["acc"] >= 0.75
    out["judgment"] = {"pre": pre, "verdict": "not_judged" if not pre else (
        "by_word" if s["decoy"]["acc"] <= 0.25 else "not_by_word")}
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e41_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
