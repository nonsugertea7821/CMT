"""E55: 検査器の出力は、読み方を例で示せば読まれるか（h_checker_output_read_when_taught）。

系列:
  E54（#729）で、名前で 1 つ答える形の mod の 2 段（named）に、検査器の出力を一行添えても acc は上がらなかった。
  答えをほぼ含む closure の行（X → {A, M}）を添えても、Qwen2.5-1.5B-Instruct 0.750 → 0.719、Qwen3-4B 0.531 → 0.531。
  h_model_misses_checker_output を 2 モデルで支持し、対の解き方として次を登録した（#752）:
    h_checker_output_read_when_taught: {v_read, from: model, to: [type_check_result, application_example]}
  ここでは、出力から答えを読む解き方を 2 例（application_example）添えて、出力が読まれるかを測る。

モデル: Qwen/Qwen2.5-1.5B-Instruct と Qwen/Qwen3-4B（どちらも bf16）。学習はしない。前向き計算だけ。

項目: e52_named_hop.make_items を N_ITEMS=34、seed 10 で作り、先頭 2 つを例、残り 32 を測る項目にする
  （名前は 34 項目のあいだで重ならない）。定義の集まりは、どれも E52 の named と同じ書き方。
条件:
  named_closure  例なし。定義の後に closure の行（E54 の named_closure と同じ。新しい項目で測り直す基準）
  taught_closure 例 2 つ（定義の集まり・closure の行・答え）の後に、named_closure と同じ問い
  taught_named   例 2 つ（定義の集まり・答え。closure の行なし）の後に、closure の行のない問い
    （例を添えること自体の効きを分ける対照）
  例 1 は X が先、例 2 は Y が先に並べる（答えの位置を偏らせない）。例の名前は入れ替えない。
  closure の行は E54 と同じ書き方（「検査器が解いた依存（たどった先まで）: K → {V, W}; ...」。キーも {} の中も辞書順）。
設問・得点は E54 と同じ（E47 の HEAD・score・summ）:
  問いの項目について、名前の割り当て 2 通り（そのまま / X・Y と M・N を入れ替え。closure の行も入れ替えた名前で作る）
  × 定義の並び 2 通り。d = s(X) − s(Y)。pair = [X が先の平均, Y が先の平均]。
  acc = pair の平均 > 0 の割合。order_robust = 両方 > 0 の割合。

判定（事前登録。モデルごと。32 項目）:
  up = taught_closure の acc − named_closure の acc、ctrl = taught_closure の acc − taught_named の acc。
  h_checker_output_read_when_taught:
    支持: up ≥ 0.1875（6 項目以上）かつ ctrl ≥ 0.125（4 項目以上）。
    反証: up ≤ 0.0625（2 項目以下）。
    その他: 判定しない（例を添えて上がっても、closure の行なしでも同じだけ上がるなら、出力を読んだとは言わない）。
  2 つのモデルで支持と反証に分かれたら、両方を結ぶ（mixed）。

開示:
  - E44〜E54 の結果を見てから、この手順を書いた。E54 の named（0.750・0.531）と named_closure（0.719・0.531）を知っている。
  - 例は 2 つで固定。例の選び方・書き方は 1 通りしか試さない（ほかの書き方で上がる可能性は残る）。
  - closure の行は問いの答え（X）を含む。支持は、その易しい条件で例があれば読めることだけを言う。
  - 検査器の出力は手で計算した（cscl の型検査器そのものは呼ばない）。

使い方:
  python e55_checker_taught.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e55_checker_taught.py --model Qwen/Qwen3-4B
  出力: results/e55_<model>.json（途中保存: results/e55_<model>.partial.json。8 項目ごと）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ
import e52_named_hop
from e52_named_hop import snippet

N_ITEMS = 32
N_EX = 2
CONDS = ("named_closure", "taught_closure", "taught_named")
CHUNK = 8


def make_all(seed=10):
    e52_named_hop.N_ITEMS = N_ITEMS + N_EX
    its = e52_named_hop.make_items(seed=seed)
    return its[:N_EX], its[N_EX:]


def deps(it):
    return {it["M"]: [it["A"]], it["N"]: [it["B"]], it["X"]: [it["M"]], it["Y"]: [it["N"]]}


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


def closure_line(it):
    c = closure(deps(it))
    return "検査器が解いた依存（たどった先まで）: " + "; ".join(f"{k} → {{{', '.join(c[k])}}}" for k in sorted(c))


def block(it, x_first, with_line):
    body = f"{HEAD.format(A=it['A'])}\n{snippet(it, 'named', x_first)}"
    return body + ("\n" + closure_line(it) if with_line else "")


def examples(exs, with_line):
    return "\n\n".join(f"例 {k + 1}:\n{block(ex, k == 0, with_line)}\n答え: {ex['X']}" for k, ex in enumerate(exs))


def d_one(r, exs, it, cond, swap_names, x_first):
    it = dict(it, X=it["Y"], Y=it["X"], M=it["N"], N=it["M"]) if swap_names else dict(it)
    with_line = cond.endswith("closure")
    q = block(it, x_first, with_line)
    if cond.startswith("taught"):
        q = f"{examples(exs, with_line)}\n\nでは、次の問いに答えてください。\n{q}"
    prompt = r.render(None, q)
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e55_{short}.partial.json"
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
            raw[str(it["id"])] = [d_one(r, exs, it, cond, s, f) for f in (True, False) for s in (False, True)]
            if (i + 1) % CHUNK == 0 or i + 1 == len(todo):
                part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                print(cond, len(raw), flush=True)
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [(d[0] + d[1]) / 2, (d[2] + d[3]) / 2], "d4": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    s = out["summary"]
    up = s["taught_closure"]["acc"] - s["named_closure"]["acc"]
    ctrl = s["taught_closure"]["acc"] - s["taught_named"]["acc"]
    v = "supported" if up >= 0.1874 and ctrl >= 0.1249 else "refuted" if up <= 0.0626 else "not_judged"
    out["judgment"] = {"up": up, "ctrl": ctrl, "checker_output_read_when_taught": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e55_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
