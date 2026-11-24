"""E43: モデルは依存を、語の字面で読むか（比べの形で。h_model_reads_by_word #720）。

系列:
  E41（同じ枝。Qwen3-4B、T ごとの二択）は前提（extends の acc ≥ 0.75）が崩れ、判定しなかった。
  E42（#725。同じモデル・同じ項目で、比べ「意味が変わるのはどちらですか」の形）では、
  extends 0.708・decoy 0.167 だった（decoy は参考）。依存しない側でも A の文字列がある行を選んだ。
  E42 の項目で見てから仮説を判定すると、見てから線を引くことになる。
  ここでは、新しい項目（seed 1）で、E42 と同じ比べの形を使い、判定を事前に決める。
  また、decoy で選ばれた理由が「A の文字列」であることを分けるため、対照 control を足す。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。

設問（E42 と同じ形）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わるのはどちらですか。番号で答えてください。」
  定義の集まりの後に、1. と 2. で P と Q（順を入れ替えた 2 回）。
  d = logit(P の番号) − logit(Q の番号)。行の記録は {"margin": d の平均, "both": 両方の順で d > 0}。
  acc = margin > 0 の割合（24 項目）。
  条件:
    extends  P: {extends: A}   Q: {extends: B}
    decoy    M: {of: [v_depend, from], with: A}、P: {extends: entity, mod: M}、Q: {extends: B, val: {text: 'A'}}
    control  decoy と同じ。ただし Q の text は、どこにも出ない別の名前 C（A の文字列は M の行にだけある）

判定（事前登録。24 項目）:
  前提: extends の acc が 0.625 以上（比べの形で、名前の位置の依存をある程度読める）。崩れたら判定しない。
    （0.625 は E42 の 0.708 を見てから決めた。開示する。）
  h_model_reads_by_word:
    支持: decoy の acc が 0.25 以下、かつ control の acc − decoy の acc が 0.25 以上。
    反証: decoy の acc が 0.5 以上。
    それ以外: 判定しない。

開示:
  - E41・E42 の結果を見てから、この手順を書いた。
  - 項目の生成は E41・E42 と同じ関数で、seed だけ 1 に変えた（名前を 7 つ作る。7 つ目が C）。

使い方:
  python e43_reads_by_word_compare.py --model Qwen/Qwen3-4B
  出力: results/e43_<model>.json（途中保存: results/e43_<model>.partial.json）
"""
import argparse
import json
import random

import torch

from e1_context_injection import ROOT, Runner

N_ITEMS = 24
CONDS = ("extends", "decoy", "control")
SYL = ["ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so", "ta", "te", "to", "na", "ni", "nu", "ne",
       "no", "ha", "hi", "fu", "he", "ho", "ma", "mi", "mu", "me", "mo", "ra", "ri", "ru", "re", "ro"]
HEAD = "次の定義の集まりで、{A} の定義を変えたとします。意味が変わるのはどちらですか。番号で答えてください。"


def make_items(seed=1):
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
        a, b, p, q, m, n, c = (name() for _ in range(7))
        items.append({"id": i, "A": a, "B": b, "P": p, "Q": q, "M": m, "N": n, "C": c,
                      "p_first": rng.random() < 0.5, "a_first": rng.random() < 0.5})
    return items


def snippet(it, cond):
    a, b, p, q, m, n = it["A"], it["B"], it["P"], it["Q"], it["M"], it["N"]
    base = [f"{a}: {{extends: entity}}", f"{b}: {{extends: entity}}"]
    mids = []
    if cond == "extends":
        tp, tq = f"{p}: {{extends: {a}}}", f"{q}: {{extends: {b}}}"
    elif cond in ("decoy", "control"):
        t = a if cond == "decoy" else it["C"]
        mids = [f"{m}: {{of: [v_depend, from], with: {a}}}"]
        tp, tq = f"{p}: {{extends: entity, mod: {m}}}", f"{q}: {{extends: {b}, val: {{text: '{t}'}}}}"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e43_{short}.partial.json"
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
    s = out["summary"]
    pre = s["extends"]["acc"] >= 0.625
    dec, con = s["decoy"]["acc"], s["control"]["acc"]
    v = "not_judged"
    if pre and dec <= 0.25 and con - dec >= 0.25:
        v = "supported"
    elif pre and dec >= 0.5:
        v = "refuted"
    out["judgment"] = {"pre": pre, "model_reads_by_word": v}
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e43_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
