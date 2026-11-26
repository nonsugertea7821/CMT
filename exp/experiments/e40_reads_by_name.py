"""E40: モデルは依存を識別子の位置で読み、名前のない中身の中の依存を落とすか（h_model_reads_by_name #483）。

系列: #478 の事前登録で、手順を書いたモデル（Claude）が、関係の差を「名詞の名前を含む行」で振り分け、
名前のない中身（{of: ..., with: ...} の項）の行を漏らした。その見落としを含意として登録した（8f3de75）:
  h_model_reads_by_name = v_read(model, syntax.identifier)。
ここでは、小さいモデル（Qwen2.5-1.5B-Instruct）で、その読み方が観察できるかを測る。
（手順を書いたモデルそのものではない。体系の d_road_checker は「読む側」一般について言うので、
  別のモデルで同じ偏りが出るかを確かめる。）

設問（モデルは学習しない。前向き計算だけ）:
  意味のない名前の小さな定義の集まりを見せ、「{A} の定義を変えたら、{T} の意味は変わるか」を二択で問う。
  T は、A に依存する X と、A に依存しない Y（B に依存する）の2つ。
  依存の書き方を3通りに変える（名前は項目ごとに同じ。書き方だけが違う）:
    extends  X: {extends: A}                                     A は名前の位置（extends の値）
    inline   X: {extends: entity, mod: {of: [v_depend, from], with: A}}
                                                                A は名前のない中身の中
    named    M: {of: [v_depend, from], with: A}  と  X: {extends: entity, mod: M}
                                                                A は名前のある中身の中（参考。2段）
  Y は同じ書き方で B に依存する。行の順は項目ごとに混ぜる（どの条件でも同じ順の決め方）。

測る量:
  score(T) = 「変わる」と「変わらない」の logit の差を、選択肢の順を入れ替えた2回で平均したもの。
  正しい = score(X) > score(Y)。acc = 正しい項目の割合（24 項目）。
  答えの偏り（どちらにも「変わる」と言う）は、X と Y の比べで打ち消す。

判定（事前登録。24 項目）:
  前提: extends の acc が 0.75 以上（依存を名前の位置で読めること）。崩れたら判定しない。
  支持（名前で読み、名前のない中身を落とす）: extends の acc − inline の acc が 0.25 以上。
  反証: それ以外。
  named は判定に使わない（参考）。

開示: この手順を書く前に、Qwen2.5-1.5B にこの種の設問を見せたことはない。項目は下の生成で決まる（seed 0）。

使い方:
  python e40_reads_by_name.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e40_<model>.json（途中保存: results/e40_<model>.partial.json）
"""
import argparse
import json
import random

import torch

from e1_context_injection import ROOT, Runner

N_ITEMS = 24
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
        a, b, x, y, m, n = (name() for _ in range(6))
        xy_first = rng.random() < 0.5
        ab_first = rng.random() < 0.5
        items.append({"id": i, "A": a, "B": b, "X": x, "Y": y, "M": m, "N": n,
                      "x_first": xy_first, "a_first": ab_first})
    return items


def snippet(it, cond):
    a, b, x, y, m, n = it["A"], it["B"], it["X"], it["Y"], it["M"], it["N"]
    base = [f"{a}: {{extends: entity}}", f"{b}: {{extends: entity}}"]
    if not it["a_first"]:
        base.reverse()
    mids = []
    if cond == "extends":
        tx, ty = f"{x}: {{extends: {a}}}", f"{y}: {{extends: {b}}}"
    elif cond == "inline":
        tx = f"{x}: {{extends: entity, mod: {{of: [v_depend, from], with: {a}}}}}"
        ty = f"{y}: {{extends: entity, mod: {{of: [v_depend, from], with: {b}}}}}"
    elif cond == "named":
        mids = [f"{m}: {{of: [v_depend, from], with: {a}}}", f"{n}: {{of: [v_depend, from], with: {b}}}"]
        if not it["a_first"]:
            mids.reverse()
        tx, ty = f"{x}: {{extends: entity, mod: {m}}}", f"{y}: {{extends: entity, mod: {n}}}"
    else:
        raise ValueError(cond)
    tail = [tx, ty] if it["x_first"] else [ty, tx]
    return "\n".join(base + mids + tail)


@torch.no_grad()
def score(r, it, cond, target):
    ms = []
    for swap in (False, True):
        opts = list(OPTS)
        if swap:
            opts.reverse()
        yes_no = 2 if swap else 1
        body = f"{HEAD.format(A=it['A'], T=target)}\n{snippet(it, cond)}\n1. {opts[0]}\n2. {opts[1]}"
        l1, l2 = r.logits_12(r.render(None, body))
        ms.append((l1 - l2) if yes_no == 1 else (l2 - l1))
    return sum(ms) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e40_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "items": {}, "summary": {}}
    r = Runner(args.model)
    for cond in ("extends", "inline", "named"):
        if cond in out["summary"]:
            continue
        rows = {}
        for it in items:
            sx, sy = score(r, it, cond, it["X"]), score(r, it, cond, it["Y"])
            rows[str(it["id"])] = {"x": sx, "y": sy, "margin": sx - sy, "snippet": snippet(it, cond)}
        out["items"][cond] = rows
        out["summary"][cond] = {
            "acc": sum(v["margin"] > 0 for v in rows.values()) / len(rows),
            "mean_margin": sum(v["margin"] for v in rows.values()) / len(rows),
            "x_yes": sum(v["x"] > 0 for v in rows.values()) / len(rows),
            "y_yes": sum(v["y"] > 0 for v in rows.values()) / len(rows),
        }
        print(cond, json.dumps(out["summary"][cond]), flush=True)
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    s = out["summary"]
    pre = s["extends"]["acc"] >= 0.75
    gap = s["extends"]["acc"] - s["inline"]["acc"]
    out["judgment"] = {"pre": pre, "gap": gap,
                       "verdict": "not_judged" if not pre else ("by_name" if gap >= 0.25 else "not_by_name")}
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e40_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
