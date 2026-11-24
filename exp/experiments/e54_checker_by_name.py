"""E54: 名前で答える形で、検査器の出力を渡すと、mod の 2 段の依存を答えられるか（h_verdict_by_checker #727、h_model_misses_checker_output）。

系列:
  E44（このブランチ、#729）は番号の選択肢の形で測り、decoy_closure 0.542 で判定しなかった。
  どの条件でも両方の順で正しい項目が 0 で、選択肢の位置の偏りが強かった。
  その後、E47 で設問を「名前で 1 つ答える形」に揃え（名前の入れ替え × 定義の並び）、E51〜E53 で次を測った:
    mod の 2 段（named: M: {of: [v_depend, from], with: A}、X: {extends: entity, mod: M}）は
    Qwen2.5-1.5B-Instruct 0.625 / 0.542 / 0.719、Qwen3-4B 0.542 / 0.417 / 0.531（E51 / E52 / E53）。
  ここでは、その named の定義の集まりに、検査器の出力を一行添えて、名前で答える形で測り直す。

モデル: Qwen/Qwen2.5-1.5B-Instruct と Qwen/Qwen3-4B（どちらも bf16）。学習はしない。前向き計算だけ。

項目: 32 項目、seed 9（e52_named_hop.make_items を N_ITEMS=32 で使う。E52・E53 とは別の項目）。
条件（定義の集まりは、どれも E52 の named と同じ）:
  named          検査器の出力なし（基準）
  named_edges    定義の後に「検査器が解いた依存: K → V; ...」（直接の依存。mod の with と mod。entity は除く）
  named_closure  定義の後に「検査器が解いた依存（たどった先まで）: K → {V, W}; ...」（推移的に閉じたもの）
  行は E44 と同じ書き方。キーも、{} の中も、名前の辞書順に並べる。
設問・得点は E52 と同じ（E47 の HEAD・score・summ）:
  名前の割り当て 2 通り（そのまま / X・Y と M・N を入れ替え。検査器の行も入れ替えた名前で作る）× 定義の並び 2 通り。
  d = s(X) − s(Y)。pair = [X が先の平均, Y が先の平均]。acc = pair の平均 > 0 の割合。order_robust = 両方 > 0 の割合。

判定（事前登録。モデルごと。32 項目）:
  h_verdict_by_checker（判定は検査器の出力に頼れる。E44 と同じ線）:
    支持: named_closure の acc ≥ 0.75。
    反証: named_closure の acc ≤ 0.5。
    その間: 判定しない。
  h_model_misses_checker_output（モデルは検査器の出力を読まない。差 = named_closure の acc − named の acc）:
    支持: 差 ≤ 0.0625（2 項目以下）。
    反証: 差 ≥ 0.1875（6 項目以上）。
    その間: 判定しない。
  2 つのモデルで支持と反証に分かれたら、両方を結ぶ（mixed）。
  named_edges は参考（直接の辺だけで 2 段をたどれるか。判定には使わない）。

開示:
  - E44〜E53 の結果を見てから、この手順を書いた。named の値（上に書いたもの）を知っている。
  - closure の行は、問いの答え（A に依存するもの）を、ほぼそのまま含む（X → {A, M}）。
    支持は、その易しい条件で頼れることだけを言い、検査器なしで読めることは言わない。
  - 検査器の出力は手で計算した（cscl の型検査器そのものは呼ばない）。
  - E44 は番号の選択肢の形で、このブランチの結果として残す。E54 は設問の形を変えた別の測りで、E44 の判定を上書きしない。

使い方:
  python e54_checker_by_name.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e54_checker_by_name.py --model Qwen/Qwen3-4B
  出力: results/e54_<model>.json（途中保存: results/e54_<model>.partial.json。8 項目ごと）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import HEAD, score, summ
import e52_named_hop
from e52_named_hop import snippet

N_ITEMS = 32
CONDS = ("named", "named_edges", "named_closure")
CHUNK = 8


def make_items(seed=9):
    e52_named_hop.N_ITEMS = N_ITEMS
    return e52_named_hop.make_items(seed=seed)


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


def checker_line(it, kind):
    d = deps(it)
    if kind == "edges":
        return "検査器が解いた依存: " + "; ".join(f"{k} → {y}" for k in sorted(d) for y in sorted(d[k]))
    c = closure(d)
    return "検査器が解いた依存（たどった先まで）: " + "; ".join(f"{k} → {{{', '.join(c[k])}}}" for k in sorted(c))


def d_one(r, it, cond, swap_names, x_first):
    it = dict(it, X=it["Y"], Y=it["X"], M=it["N"], N=it["M"]) if swap_names else dict(it)
    body = snippet(it, "named", x_first)
    if cond != "named":
        body += "\n" + checker_line(it, cond.split("_")[1])
    prompt = r.render(None, f"{HEAD.format(A=it['A'])}\n{body}")
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e54_{short}.partial.json"
    items = make_items()
    assert len(items) == N_ITEMS
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "raw": {}, "items": {}, "summary": {}, "resumed": 0}
    if part.exists():
        out["resumed"] = out.get("resumed", 0) + 1
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        raw = out["raw"].setdefault(cond, {})
        todo = [it for it in items if str(it["id"]) not in raw]
        for i, it in enumerate(todo):
            raw[str(it["id"])] = [d_one(r, it, cond, s, f) for f in (True, False) for s in (False, True)]
            if (i + 1) % CHUNK == 0 or i + 1 == len(todo):
                part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                print(cond, len(raw), flush=True)
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [(d[0] + d[1]) / 2, (d[2] + d[3]) / 2], "d4": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    s = out["summary"]
    c = s["named_closure"]["acc"]
    v1 = "supported" if c >= 0.7499 else "refuted" if c <= 0.5001 else "not_judged"
    diff = c - s["named"]["acc"]
    v2 = "supported" if diff <= 0.0626 else "refuted" if diff >= 0.1874 else "not_judged"
    out["judgment"] = {"verdict_by_checker": v1, "closure_minus_named": diff, "model_misses_checker_output": v2}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e54_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
