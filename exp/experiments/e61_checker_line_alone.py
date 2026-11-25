"""E61: 検査器の行は、定義と一致するときだけ効くのか（h_checker_line_needs_agreement、#855）。

系列:
  E55（#754）: Qwen3-4B は、例 2 つと正しい closure の行で 0.906（例だけ 0.719）。
  E57: 誤った closure の行（答えが入れ替わった行）を添えても 0.688 で、行の答えを写さなかった。
  読み（未検証）: 行が効くのは、定義と一致するときだけ。定義が誤った行を退けている。
ここでは定義を外し、行だけを置く。定義が誤った行を退けているなら、定義がないと誤った行に従う。

モデル: Qwen/Qwen3-4B（bf16）。E55・E57 と同じく 4B だけを測る。
項目と例: E55 と同じ（e55_checker_taught.make_all、seed 10。例 2 つ、測る項目 32）。
条件（どちらも定義の集まりを置かない。例も問いも、HEAD の文と closure の行だけ）:
  alone_right  例 2 つ（HEAD・正しい closure の行・答え）の後に、HEAD と正しい closure の行。
  alone_wrong  同じ例の後に、HEAD と誤った closure の行（E57 の wrong_line と同じ作り方: X → {B, N}、Y → {A, M}）。
  HEAD は E47 のまま（「次の定義の集まりで…」）。定義の集まりは置かないが、文は変えない（E55・E57 との差を行の有無だけにする）。
設問・得点は E55 と同じ（d = s(X) − s(Y)、X は定義の上での正しい答え。名前の割り当て 2 通り）。
  定義がないので、定義の並び（x_first）でプロンプトは変わらない。名前の割り当て 2 通りだけを測り、
  pair = [そのまま, 入れ替え] とする。acc = pair の平均 > 0 の割合。order_robust は「名前の割り当ての両方 > 0」の割合
  （E55 の order_robust とは中身が違う。判定には使わない）。

判定（事前登録。32 項目）:
  c = alone_right の acc、w = alone_wrong の acc。
  支持: c ≥ 0.6875 かつ w ≤ 0.3125（行だけなら行に従う。誤った行にも従う。E57 で従わなかったのは定義があったから）。
  反証: c ≥ 0.6875 かつ w ≥ 0.5（行だけでも、正しい行には従うが誤った行には従わない。退けたのは定義ではない）。
  その他: 判定しない（c < 0.6875 なら、行だけでは読まれず、一致と行の有無を分けられない）。

開示:
  - E55・E57 の結果を見てから、この手順を書いた。
  - 「誤った」は定義の上での誤り。定義を外すと、誤った行はそれだけでは矛盾を含まない。
    このため alone_wrong で行に従うのは、行を読んだことの表れで、誤りではない。acc は定義の上での正しさで数える。
  - 例の書き方は 1 通りだけ。HEAD の文が定義の集まりに触れるのに置かないことは、読みに影響しうる。
  - 検査器の出力は手で計算した（cscl の型検査器そのものは呼ばない）。

使い方:
  python e61_checker_line_alone.py --model Qwen/Qwen3-4B
  出力: results/e61_<model>.json（途中保存: results/e61_<model>.partial.json。8 項目ごと）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ
from e55_checker_taught import N_ITEMS, CHUNK, make_all, closure_line
from e57_checker_wrong_closure import wrong_line

CONDS = ("alone_right", "alone_wrong")


def examples(exs):
    return "\n\n".join(f"例 {k + 1}:\n{HEAD.format(A=ex['A'])}\n{closure_line(ex)}\n答え: {ex['X']}"
                       for k, ex in enumerate(exs))


def d_one(r, exs, it, cond, swap_names):
    it = dict(it, X=it["Y"], Y=it["X"], M=it["N"], N=it["M"]) if swap_names else dict(it)
    line = closure_line(it) if cond == "alone_right" else wrong_line(it)
    q = f"{examples(exs)}\n\nでは、次の問いに答えてください。\n{HEAD.format(A=it['A'])}\n{line}"
    prompt = r.render(None, q)
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e61_{short}.partial.json"
    exs, items = make_all()
    assert len(items) == N_ITEMS
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "examples": exs, "raw": {}, "items": {}, "summary": {}, "resumed": 0}
    if part.exists():
        out["resumed"] = out.get("resumed", 0) + 1
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        raw = out["raw"].setdefault(cond, {})
        todo = [it for it in items if str(it["id"]) not in raw]
        for i, it in enumerate(todo):
            raw[str(it["id"])] = [d_one(r, exs, it, cond, s) for s in (False, True)]
            if (i + 1) % CHUNK == 0 or i + 1 == len(todo):
                part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                print(cond, len(raw), flush=True)
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": list(d)} for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    c = out["summary"]["alone_right"]["acc"]
    w = out["summary"]["alone_wrong"]["acc"]
    v = ("supported" if c >= 0.6874 and w <= 0.3126 else
         "refuted" if c >= 0.6874 and w >= 0.4999 else "not_judged")
    out["judgment"] = {"c": c, "w": w, "checker_line_needs_agreement": v}
    print(json.dumps(out["summary"], indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e61_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
