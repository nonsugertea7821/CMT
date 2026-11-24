"""E51: モデルは mod を通した依存を読まないか（h_model_misses_mod #728）。

系列:
  登録（bf111bf）: E43 の control 0.417、E42 の named 0.375・inline 0.583 から。いずれも番号で選ぶ形。
  確かめ方の案は「字面の手がかりのない項目で、mod の 1 段・2 段の依存を、比べの形で複数のモデルに問う」。
  その後、設問の形が判定を左右することがわかった（E48、#725 で h_verdict_by_question_format を支持）。
  名前で答える形では、extends の前提が立ちやすい（E47 0.958、E49 0.833）。
  そこで、名前で答える形で、2 つのモデルに問う。

モデル: Qwen/Qwen3-4B と Qwen/Qwen2.5-1.5B-Instruct（どちらも bf16）。学習はしない。前向き計算だけ。

項目（24 項目、seed 6。どのモデルも同じ項目）:
  根 A・B（{extends: entity}）。A に依存する X と、B に依存する Y。X と Y は同じ書き方にそろえる:
    extends  X: {extends: A}
    inline   X: {extends: entity, mod: {of: [v_depend, from], with: A}}       mod の 1 段（X の行に A の字面がある）
    named    M: {of: [v_depend, from], with: A}、X: {extends: entity, mod: M}  mod の 2 段（X の行に A の字面がない）
  Y は同じ書き方で B（named では N を通して B）に依存する。

設問（E47・E49 と同じ）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。」
  名前の割り当て 2 通り（そのまま / X と Y の名前を入れ替え）× 定義の並び 2 通り（X が先 / Y が先）= 4 回。
  s(名前) = 応答の頭に名前を置いたときの、名前のトークンの対数確率の和。d = s(X) − s(Y)。
  pair = [X が先の 2 回の平均, Y が先の 2 回の平均]。acc = pair の平均 > 0 の割合。order_robust = 両方 > 0 の割合。

判定（事前登録。モデルごと。24 項目）:
  前提: extends の acc ≥ 0.75。崩れたら、そのモデルでは判定しない。
  h_model_misses_mod（mod を通した依存を読まない）は、字面の手がかりのない named で判定する:
    支持: named の acc ≤ 0.625。
    反証: named の acc ≥ 0.75。
    その間: 判定しない。
  2 つのモデルで支持と反証に分かれたら、両方を結ぶ（mixed）。
  inline は参考（X の行に A の字面があるので、mod を読んだとも字面で選んだとも読める）。

開示:
  - E40〜E50 の結果を見てから、この手順を書いた。
  - Qwen3-4B・名前で答える形での近い値を知っている:
    E49 の named 0.625（order_robust 0.042）、E47 の control（P だけが mod の 2 段、Q は extends）0.917。
  - 線（0.625・0.75）は、E40 以降の前提と判定の線にそろえた。
  - 項目は新しい（seed 6）。

使い方:
  python e51_misses_mod.py --model Qwen/Qwen3-4B
  python e51_misses_mod.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e51_<model>.json（途中保存: results/e51_<model>.partial.json。条件ごとに保存）
"""
import argparse
import json
import random

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ

N_ITEMS = 24
SYL = ["ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so", "ta", "te", "to", "na", "ni", "nu", "ne",
       "no", "ha", "hi", "fu", "he", "ho", "ma", "mi", "mu", "me", "mo", "ra", "ri", "ru", "re", "ro"]
CONDS = ("extends", "inline", "named")


def make_items(seed=6):
    rng = random.Random(seed)
    used = set()

    def name():
        while True:
            w = "".join(rng.choice(SYL) for _ in range(3))
            if w not in used and not any(w in u or u in w for u in used):
                used.add(w)
                return w

    items = []
    for i in range(N_ITEMS):
        a, b, x, y, m, n = (name() for _ in range(6))
        items.append({"id": i, "A": a, "B": b, "X": x, "Y": y, "M": m, "N": n, "a_first": rng.random() < 0.5})
    return items


def snippet(it, cond, x_first):
    a, b, x, y, m, n = it["A"], it["B"], it["X"], it["Y"], it["M"], it["N"]
    base = [f"{a}: {{extends: entity}}", f"{b}: {{extends: entity}}"]
    mids = []
    if cond == "extends":
        tx, ty = f"{x}: {{extends: {a}}}", f"{y}: {{extends: {b}}}"
    elif cond == "inline":
        tx = f"{x}: {{extends: entity, mod: {{of: [v_depend, from], with: {a}}}}}"
        ty = f"{y}: {{extends: entity, mod: {{of: [v_depend, from], with: {b}}}}}"
    elif cond == "named":
        mids = [f"{m}: {{of: [v_depend, from], with: {a}}}", f"{n}: {{of: [v_depend, from], with: {b}}}"]
        tx, ty = f"{x}: {{extends: entity, mod: {m}}}", f"{y}: {{extends: entity, mod: {n}}}"
    else:
        raise ValueError(cond)
    if not it["a_first"]:
        base.reverse()
        mids.reverse()
    tail = [tx, ty] if x_first else [ty, tx]
    return "\n".join(base + mids + tail)


def d_one(r, it, cond, swap_names, x_first):
    it = dict(it, X=it["Y"], Y=it["X"], M=it["N"], N=it["M"]) if swap_names else dict(it)
    prompt = r.render(None, f"{HEAD.format(A=it['A'])}\n{snippet(it, cond, x_first)}")
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e51_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "raw": {}, "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        if cond in out["raw"]:
            continue
        out["raw"][cond] = {str(it["id"]): [d_one(r, it, cond, s, f) for f in (True, False) for s in (False, True)]
                            for it in items}
        print(cond, "done", flush=True)
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [(d[0] + d[1]) / 2, (d[2] + d[3]) / 2], "d4": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    s = out["summary"]
    pre = s["extends"]["acc"] >= 0.7499
    v = "not_judged"
    if pre and s["named"]["acc"] <= 0.6251:
        v = "supported"
    elif pre and s["named"]["acc"] >= 0.7499:
        v = "refuted"
    out["judgment"] = {"premise": pre, "model_misses_mod": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e51_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
