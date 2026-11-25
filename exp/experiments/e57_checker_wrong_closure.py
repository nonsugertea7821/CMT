"""E57: 検査器の出力が効くのは、答えが書かれているからか（h_checker_read_by_answer_copy）。

仮説（exp.yaml）: {v_depend, from: redefinition_following, to: [type_check_result, verdict]}。
系列:
  E55（#754）: Qwen3-4B は、例 2 つと closure の行（答え X を含む）で 0.500 → 0.906（例だけ 0.719）。
  E56: 答えを含まない edges の行では、例があっても 0.531（例だけの 0.719 より下）。
  読み: 4B が読んだのは「行に書かれた答えの名前」で、依存をたどったのではないかもしれない。
ここでは、例は E55 と同じ（正しい closure の行と答え）にしたまま、問いの closure の行だけを、
答えが入れ替わった誤った行にする。行の名前を写すなら acc は 0.5 より下に落ち、定義から読むなら例だけの値に近く残る。

モデル: Qwen/Qwen3-4B（bf16）。E55 で closure の行を読んだのは 4B だけなので、4B だけを測る（1.5B は測らない）。
項目と例: E55 と同じ（e55_checker_taught.make_all、seed 10。例 2 つ、測る項目 32）。
条件（ここで測る 1 つ）:
  taught_wrong  例 2 つ（E55 の taught_closure と同じ）の後に、定義と、誤った closure の行を添えた問い。
    誤った行: 依存を X → N、Y → M と入れ替えてから closure を取る（X → {B, N}、Y → {A, M}。M・N の行は正しい）。
    定義の本文は正しいまま。名前の割り当てを入れ替える回は、入れ替えた名前で誤った行を作る。
対照は E55 の結果ファイル（results/e55_Qwen3-4B.json）から読む: taught_closure（0.906）、taught_named（0.719）。
  項目・例・プロンプトの残りは E55 と同じで、前向き計算は決定的なので測り直さない。
設問・得点は E55 と同じ（d = s(X) − s(Y)、X が定義の上での正しい答え）。

判定（事前登録。32 項目）:
  w = taught_wrong の acc。
  支持（答えを写している）: w ≤ 0.3125（誤った行に従う向きが 6 項目以上の差で多い）。
  反証（写していない）: w ≥ taught_named の acc − 0.0625（誤った行を添えても、例だけのときから 2 項目以下しか落ちない）。
  その他: 判定しない（誤った行で下がるが、0.5 を大きく割らない＝行と定義の両方を使う、と読む）。

開示:
  - E55・E56 の結果を見てから、この手順を書いた。
  - 例の書き方と、誤った行の作り方は 1 通りだけ。
  - 「写す」の判定は答えの名前が行にある条件でだけ言える。edges の行で読まれないこと（E56）とは別の問い。
  - 検査器の出力は手で計算した（cscl の型検査器そのものは呼ばない）。

使い方:
  python e57_checker_wrong_closure.py --model Qwen/Qwen3-4B
  出力: results/e57_<model>.json（途中保存: results/e57_<model>.partial.json。8 項目ごと）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ
from e52_named_hop import snippet
from e55_checker_taught import N_ITEMS, CHUNK, make_all, closure, examples

CONDS = ("taught_wrong",)


def wrong_line(it):
    d = {it["M"]: [it["A"]], it["N"]: [it["B"]], it["X"]: [it["N"]], it["Y"]: [it["M"]]}
    c = closure(d)
    return "検査器が解いた依存（たどった先まで）: " + "; ".join(f"{k} → {{{', '.join(c[k])}}}" for k in sorted(c))


def d_one(r, exs, it, swap_names, x_first):
    it = dict(it, X=it["Y"], Y=it["X"], M=it["N"], N=it["M"]) if swap_names else dict(it)
    q = f"{HEAD.format(A=it['A'])}\n{snippet(it, 'named', x_first)}\n{wrong_line(it)}"
    q = f"{examples(exs, True)}\n\nでは、次の問いに答えてください。\n{q}"
    prompt = r.render(None, q)
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e57_{short}.partial.json"
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
            raw[str(it["id"])] = [d_one(r, exs, it, s, f) for f in (True, False) for s in (False, True)]
            if (i + 1) % CHUNK == 0 or i + 1 == len(todo):
                part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                print(cond, len(raw), flush=True)
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [(d[0] + d[1]) / 2, (d[2] + d[3]) / 2], "d4": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    e55 = json.loads((res / f"e55_{short}.json").read_text(encoding="utf-8"))["summary"]
    out["summary"]["taught_closure_e55"] = e55["taught_closure"]
    out["summary"]["taught_named_e55"] = e55["taught_named"]
    w = out["summary"]["taught_wrong"]["acc"]
    tn = e55["taught_named"]["acc"]
    v = "supported" if w <= 0.3126 else "refuted" if w >= tn - 0.0626 else "not_judged"
    out["judgment"] = {"w": w, "drop_from_named": tn - w, "checker_read_by_answer_copy": v}
    print(json.dumps(out["summary"], indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e57_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
