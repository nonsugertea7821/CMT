"""E53: 名前を介した mod の 2 段は、extends の 2 段より読まれないか（h_model_misses_named_mod #747）。

系列:
  E51（#743）で h_model_misses_mod を支持した（mod の 2 段 named が偶然に近い）。
  E52（#746）で、名前を介した 2 段を extends で作った chain と、mod で作った named を同じ項目で比べた:
    Qwen2.5-1.5B-Instruct  chain 0.625、named 0.542（差 0.083）
    Qwen3-4B               chain 0.667、named 0.417（差 0.250）
  4B では、名前を辿る段だけでは説明しきれない、mod に固有の落ちがあるかもしれない（#747 で登録）。
  式は {v_read, from: model, to: [syntax.mod, syntax.identifier], neg: true}。
  ここでは、chain と named の差を、新しい項目（seed 8、32 項目）と 2 つのモデルで測る。

モデル: Qwen/Qwen2.5-1.5B-Instruct と Qwen/Qwen3-4B（どちらも bf16）。学習はしない。前向き計算だけ。

項目（32 項目、seed 8。どのモデルも同じ項目）と条件は E52 と同じ書き方:
    extends  X: {extends: A}                                                  1 段（前提）
    chain    M: {extends: A}、X: {extends: M}                                 extends の 2 段
    named    M: {of: [v_depend, from], with: A}、X: {extends: entity, mod: M}  mod の 2 段
設問・得点・pair・acc・order_robust は E52（E47 の HEAD・score・summ）と同じ。

判定（事前登録。モデルごと。32 項目。差 = chain の acc − named の acc）:
  前提: extends の acc ≥ 0.75。崩れたら、そのモデルでは判定しない。
  支持: named の acc ≤ 0.625 かつ 差 ≥ 0.125（4 項目以上）。
  反証: 差 ≤ 0（named が chain 以上）、または named の acc ≥ 0.75。
  それ以外: 判定しない。
  2 つのモデルで支持と反証に分かれたら、両方を結ぶ（mixed）。

開示:
  - E52 の結果（上の 4 つの値）を見てから、この手順と線を書いた。差の線 0.125 は、E52 1.5B の差 0.083 より上、
    4B の差 0.25 より下に置いた。E52 の値は判定に使わない（項目を新しくした）。
  - 途中保存は 8 項目ごと。コンテナが約 10 分で落ちるので、partial から再開する。

使い方:
  python e53_named_mod.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e53_named_mod.py --model Qwen/Qwen3-4B
  出力: results/e53_<model>.json（途中保存: results/e53_<model>.partial.json）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e47_extends_unnamed import summ
from e52_named_hop import d_one, make_items as make_items_e52
import e52_named_hop

N_ITEMS = 32
CONDS = ("extends", "chain", "named")
CHUNK = 8


def make_items(seed=8):
    e52_named_hop.N_ITEMS = N_ITEMS
    return make_items_e52(seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e53_{short}.partial.json"
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
    diff = s["chain"]["acc"] - s["named"]["acc"]
    pre = s["extends"]["acc"] >= 0.7499
    v = "not_judged"
    if pre and s["named"]["acc"] <= 0.6251 and diff >= 0.1249:
        v = "supported"
    elif pre and (diff <= 1e-9 or s["named"]["acc"] >= 0.7499):
        v = "refuted"
    out["judgment"] = {"premise": pre, "chain_minus_named": diff, "model_misses_named_mod": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e53_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
