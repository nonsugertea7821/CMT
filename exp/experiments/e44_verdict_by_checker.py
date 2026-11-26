"""E44: 依存の判定は、型検査器の出力に頼れるか（h_verdict_by_checker #727）。

系列:
  E43（#721。Qwen3-4B、比べの形、seed 1）で、h_model_reads_by_word を支持した:
    extends 0.75、decoy 0.125、control 0.417。
  依存する行（P: {mod: M}、M: {of: [v_depend, from], with: A}）より、A の文字列を val に置いただけの行を選んだ。
  読む側が依存を解けないなら、検査器が解いた依存を渡せば、判定はそれに頼って正しくなる、を仮説にした（#726）。
  ここでは、E43 と同じ項目・同じ定義の集まり・同じ設問に、検査器の出力を一行添える。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。

設問: E43 と同じ（「{A} の定義を変えたとします。意味が変わるのはどちらですか。」、P と Q を番号の選択肢に、順を入れ替えた 2 回）。
  定義の集まりの後、選択肢の前に、次の一行を置く。
  edges:   「検査器が解いた依存: X → Y; ...」（定義に直接書かれた依存。extends と mod の with。entity は除く）
  closure: 「検査器が解いた依存（たどった先まで）: X → {Y, Z}; ...」（直接の依存を推移的に閉じたもの）
  行は名前の順（辞書順）に並べる（どの行が問いの答えかを並びで漏らさない）。
  条件:
    decoy_closure  E43 の decoy に closure を添える
    decoy_edges    E43 の decoy に edges を添える
    control_edges  E43 の control に edges を添える
  d = logit(P の番号) − logit(Q の番号)。行の記録は {"margin", "both"}。acc = margin > 0 の割合（24 項目）。

判定（事前登録。24 項目）:
  h_verdict_by_checker（判定は検査器の出力に頼れる）:
    支持: decoy_closure の acc が 0.75 以上（E43 の decoy 0.125 から上がる）。
    反証: decoy_closure の acc が 0.5 以下（答えを含む出力を渡しても、字面を選ぶ）。
    その間: 判定しない。
  decoy_edges・control_edges は参考（直接の依存だけを渡したとき、2 段をたどれるか。h_model_misses_mod の参考）。

開示:
  - E41〜E43 の結果を見てから、この手順を書いた。
  - closure の行は、問い（A を変えて意味が変わるもの）の答えを、ほぼそのまま含む。
    支持はその易しい条件で頼れることだけを言い、検査器なしで読めることは言わない。
  - 検査器の出力は、ここでは手で計算した（cscl の型検査器そのものは呼ばない）。

使い方:
  python e44_verdict_by_checker.py --model Qwen/Qwen3-4B
  出力: results/e44_<model>.json（途中保存: results/e44_<model>.partial.json）
"""
import argparse
import json
import random

import torch

from e1_context_injection import ROOT, Runner

N_ITEMS = 24
CONDS = ("decoy_closure", "decoy_edges", "control_edges")
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


def deps(it, cond):
    a, b, p, q, m = it["A"], it["B"], it["P"], it["Q"], it["M"]
    if cond == "extends":
        return {p: [a], q: [b]}
    return {m: [a], p: [m], q: [b]}


def closure(d):
    out = {}
    for k in d:
        seen, st = [], list(d[k])
        while st:
            x = st.pop(0)
            if x not in seen:
                seen.append(x)
                st += d.get(x, [])
        out[k] = sorted(seen)
    return out


def checker_line(it, cond, kind):
    d = deps(it, cond)
    if kind == "edges":
        return "検査器が解いた依存: " + "; ".join(f"{k} → {y}" for k in sorted(d) for y in sorted(d[k]))
    c = closure(d)
    return "検査器が解いた依存（たどった先まで）: " + "; ".join(f"{k} → {{{', '.join(c[k])}}}" for k in sorted(c))


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
    base, kind = cond.split("_")
    o = [it["P"], it["Q"]] if p_opt_first else [it["Q"], it["P"]]
    body = f"{HEAD.format(A=it['A'])}\n{snippet(it, base)}\n{checker_line(it, base, kind)}\n1. {o[0]}\n2. {o[1]}"
    l1, l2 = r.logits_12(r.render(None, body))
    return (l1 - l2) if p_opt_first else (l2 - l1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e44_{short}.partial.json"
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
                                   "snippet": snippet(it, cond.split("_")[0]) + "\n" + checker_line(it, *cond.split("_"))}
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
    acc = s["decoy_closure"]["acc"]
    v = "supported" if acc >= 0.75 else ("refuted" if acc <= 0.5 else "not_judged")
    out["judgment"] = {"verdict_by_checker": v}
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e44_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
