"""E52: モデルは、名前を辿る 2 段目の依存を、extends でも読まないか（h_model_misses_named_hop #745）。

系列:
  E51（#743、マージ済み）で h_model_misses_mod を支持した。名前で 1 つ答える形で、
  mod が名前を介した 2 段（named: M: {of: [v_depend, from], with: A}、X: {extends: entity, mod: M}）のとき、
  Qwen2.5-1.5B-Instruct 0.625、Qwen3-4B 0.542 と偶然に近かった。1 段の inline は 0.917、1.0。
  落ちているのが「mod の中身を読むこと」か「名前を辿って 2 段目へ行くこと」かは、E51 では分けられない
  （inline では X の行に A の字面がある）。そこで、名前を介した 2 段を extends だけで作る（#744 で登録）。
  式は {v_read, from: model, to: [syntax.extends, syntax.identifier], neg: true}。

モデル: Qwen/Qwen2.5-1.5B-Instruct と Qwen/Qwen3-4B（どちらも bf16）。学習はしない。前向き計算だけ。

項目（24 項目、seed 7。どのモデルも同じ項目）:
  根 A・B（{extends: entity}）。A に依存する X と、B に依存する Y。X と Y は同じ書き方にそろえる:
    extends  X: {extends: A}                                         1 段（前提）
    chain    M: {extends: A}、X: {extends: M}                        extends の 2 段（判定）
    named    M: {of: [v_depend, from], with: A}、X: {extends: entity, mod: M}   mod の 2 段（E51 の named の再現。参考）
  Y は同じ書き方で B（2 段では N を通して B）に依存する。並べ方は E51 と同じ（根 2 行、中間 2 行、X・Y の 2 行）。

設問（E47・E49・E51 と同じ）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。」
  名前の割り当て 2 通り（そのまま / X・Y と M・N を入れ替え）× 定義の並び 2 通り（X が先 / Y が先）= 4 回。
  s(名前) = 応答の頭に名前を置いたときの、名前のトークンの対数確率の和。d = s(X) − s(Y)。
  pair = [X が先の 2 回の平均, Y が先の 2 回の平均]。acc = pair の平均 > 0 の割合。order_robust = 両方 > 0 の割合。
  注: 2 段では M も A に依存するので、M も正しい答えになりうる。測るのは X と Y の比べだけ（E51 の named と同じ）。

判定（事前登録。モデルごと。24 項目）:
  前提: extends の acc ≥ 0.75。崩れたら、そのモデルでは判定しない。
  h_model_misses_named_hop（名前を辿る 2 段目の依存を読まない）は chain で判定する:
    支持: chain の acc ≤ 0.625。
    反証: chain の acc ≥ 0.75。
    その間: 判定しない。
  2 つのモデルで支持と反証に分かれたら、両方を結ぶ（mixed）。
  named は参考（E51 の再現が新しい項目でも出るかを見る。判定には使わない）。

開示:
  - E40〜E51 の結果を見てから、この手順を書いた。E51 の named（0.625、0.542）を知っている。
  - E47 の control（Qwen3-4B、片側だけが mod の 2 段、もう一方は extends）0.917 を知っている。
  - 線（0.625・0.75）は E51 と同じ。項目は新しい（seed 7）。

使い方:
  python e52_named_hop.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e52_named_hop.py --model Qwen/Qwen3-4B
  出力: results/e52_<model>.json（途中保存: results/e52_<model>.partial.json。条件ごとに保存）
"""
import argparse
import json
import random

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ

N_ITEMS = 24
SYL = ["ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so", "ta", "te", "to", "na", "ni", "nu", "ne",
       "no", "ha", "hi", "fu", "he", "ho", "ma", "mi", "mu", "me", "mo", "ra", "ri", "ru", "re", "ro"]
CONDS = ("extends", "chain", "named")


def make_items(seed=7):
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
    elif cond == "chain":
        mids = [f"{m}: {{extends: {a}}}", f"{n}: {{extends: {b}}}"]
        tx, ty = f"{x}: {{extends: {m}}}", f"{y}: {{extends: {n}}}"
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
    part = res / f"e52_{short}.partial.json"
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
    if pre and s["chain"]["acc"] <= 0.6251:
        v = "supported"
    elif pre and s["chain"]["acc"] >= 0.7499:
        v = "refuted"
    out["judgment"] = {"premise": pre, "model_misses_named_hop": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e52_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
