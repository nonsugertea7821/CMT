"""E56: 答えを含まない直接の辺でも、読み方を例で示せば読まれるか（b_checker_output_read_when_taught_edges）。

系列:
  E54（#729）: 検査器の出力を添えても、例がなければ acc は上がらない（closure でも edges でも）。
  E55（#754）: 例 2 つを添えると、Qwen3-4B は closure の行（答え X を含む）を読んだ（0.500 → 0.906、例だけ 0.719）。
    Qwen2.5-1.5B-Instruct は動かなかった。h_checker_output_read_when_taught は mixed。
  E55 の closure の行は答えを含むので、読めたのは「行から答えの名前を写す」ことかもしれない。
  ここでは、答えを含まない直接の辺（E54 の edges: K → V を 1 本ずつ。X → M; M → A ...）で、
  例があれば 2 段をたどって読めるかを測る（#755 で登録した残り項目）。

モデル: Qwen/Qwen2.5-1.5B-Instruct と Qwen/Qwen3-4B（どちらも bf16）。学習はしない。前向き計算だけ。

項目と例: E55 と同じ（e52_named_hop.make_items、N_ITEMS=34、seed 10。先頭 2 つを例、残り 32 を測る）。
条件（ここで測る 2 つ）:
  named_edges   例なし。定義の後に edges の行
  taught_edges  例 2 つ（定義の集まり・edges の行・答え）の後に、named_edges と同じ問い
  edges の行は E54 と同じ書き方（「検査器が解いた依存: K → V; ...」。辺は K、V の辞書順）。
  例 1 は X が先、例 2 は Y が先（E55 と同じ）。
対照 taught_named（例 2 つ、行なし）は E55 の結果ファイル（results/e55_<model>.json）の値を読んで使う。
  項目・例・プロンプトが E55 と同じで、前向き計算は決定的なので、測り直さない（4B の計算を減らすため）。
設問・得点は E55 と同じ（E47 の HEAD・score・summ。名前 2 通り × 並び 2 通り。acc と order_robust）。

判定（事前登録。モデルごと。32 項目）:
  up = taught_edges の acc − named_edges の acc、ctrl = taught_edges の acc − taught_named の acc（E55）。
  b_checker_output_read_when_taught_edges（edges でも、例があれば読める）:
    支持: up ≥ 0.1875 かつ ctrl ≥ 0.125。
    反証: up ≤ 0.0625。
    その他: 判定しない。
  E55 で動かなかった 1.5B は、反証の見込みが高いことを開示しておく。

開示:
  - E54・E55 の結果を見てから、この手順を書いた。E54 の named_edges（1.5B 0.656、4B 0.500。項目は seed 9 で別）を知っている。
  - 対照を E55 から読むので、E55 の結果ファイルが変わると ctrl が変わる（記録済みのファイルは書き換えない）。
  - 例の書き方は 1 通りだけ。
  - 検査器の出力は手で計算した（cscl の型検査器そのものは呼ばない）。

使い方:
  python e56_checker_taught_edges.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e56_checker_taught_edges.py --model Qwen/Qwen3-4B
  出力: results/e56_<model>.json（途中保存: results/e56_<model>.partial.json。8 項目ごと）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ
from e52_named_hop import snippet
from e55_checker_taught import N_ITEMS, CHUNK, make_all, deps

CONDS = ("named_edges", "taught_edges")


def edges_line(it):
    d = deps(it)
    return "検査器が解いた依存: " + "; ".join(f"{k} → {y}" for k in sorted(d) for y in sorted(d[k]))


def block(it, x_first):
    return f"{HEAD.format(A=it['A'])}\n{snippet(it, 'named', x_first)}\n{edges_line(it)}"


def examples(exs):
    return "\n\n".join(f"例 {k + 1}:\n{block(ex, k == 0)}\n答え: {ex['X']}" for k, ex in enumerate(exs))


def d_one(r, exs, it, cond, swap_names, x_first):
    it = dict(it, X=it["Y"], Y=it["X"], M=it["N"], N=it["M"]) if swap_names else dict(it)
    q = block(it, x_first)
    if cond == "taught_edges":
        q = f"{examples(exs)}\n\nでは、次の問いに答えてください。\n{q}"
    prompt = r.render(None, q)
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e56_{short}.partial.json"
    e55 = json.loads((res / f"e55_{short}.json").read_text(encoding="utf-8"))
    exs, items = make_all()
    assert len(items) == N_ITEMS and exs == e55["examples"]
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "examples": exs, "raw": {}, "items": {}, "summary": {}, "resumed": 0}
    if part.exists():
        out["resumed"] = out.get("resumed", 0) + 1
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        raw = out["raw"].setdefault(cond, {})
        todo = [it for it in items if str(it["id"]) not in raw]
        for i, it in enumerate(todo):
            raw[str(it["id"])] = [d_one(r, exs, it, cond, s, f) for f in (True, False) for s in (False, True)]
            if (i + 1) % CHUNK == 0 or i + 1 == len(todo):
                part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                print(cond, len(raw), flush=True)
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [(d[0] + d[1]) / 2, (d[2] + d[3]) / 2], "d4": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    out["items"]["taught_named_e55"] = e55["items"]["taught_named"]
    out["summary"]["taught_named_e55"] = e55["summary"]["taught_named"]
    s = out["summary"]
    up = s["taught_edges"]["acc"] - s["named_edges"]["acc"]
    ctrl = s["taught_edges"]["acc"] - s["taught_named_e55"]["acc"]
    v = "supported" if up >= 0.1874 and ctrl >= 0.1249 else "refuted" if up <= 0.0626 else "not_judged"
    out["judgment"] = {"up": up, "ctrl": ctrl, "checker_output_read_when_taught_edges": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e56_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
