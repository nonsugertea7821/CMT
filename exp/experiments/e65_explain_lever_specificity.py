"""E65: E64 で explain のベクトルが apply を上げたのは、explain の学習から来たのか（h_explain_lever_transfers_to_apply_15b）。

系列:
  E64（#864、支持）: 1.5B に、説明の設問で学習した層 8 のベクトル（vec_ex）を概念の語の位置に加えると、
    explain 0.833 → 1.0、apply 0.583 → 0.833、joint 0.458 → 0.750。joint になった 9 概念のうち 7 つは apply が変わったもの。
  そこで登録した: h_explain_lever_transfers_to_apply_15b: v_transfer(usage_explain, usage_apply)、範囲 model_15b。
  問い: apply の上がりは、explain で学習した向きから来たのか、それとも層 8 に同じ大きさのものを足せば何でも起きるのか。

手（対照のベクトル）:
  vec_rand: 概念ごとに、乱数の向き（torch.Generator、種 = 6500 + 概念の並びの番号、標準正規）を、
    E64 で学習したその概念のベクトルの大きさ（E64 の train[概念].norm）にそろえる。学習はしない。
  E64 のベクトル（partial.pt）はリポジトリになく、手元の作業ツリーも片付けたので残っていない。学習し直さず、
  vec_ex と vec_none の値は E64 の結果ファイル（results/e64_Qwen2.5-1.5B-Instruct.json）の行を使う。

測り（E64 と同じ。e64.patch と e58.measure、near の前置きあり、4 つの使い方）:
  vec_rand    文中の概念の語の位置すべてに vec_rand を加える。
  vec_none_re ベクトルなし（E64 の vec_none と同じになるかの確かめ。判定には使わない）。

判定（事前登録。Qwen2.5-1.5B-Instruct、float32。24 概念）:
  hit = margin > 0。acc = hit の割合。
  da_ex = E64 の apply の上がり（vec_ex − vec_none、0.25）。da_rand = apply(vec_rand) − apply(E64 の vec_none)。
  前提（対照が壊しすぎていない）: vec_rand の para の acc ≥ 0.875 かつ recite の acc ≥ 0.875。
    満たさなければ判定しない（乱数の向きが使い方を広く壊しているなら、apply が上がらないことは特定性の証拠にならない）。
  支持: da_ex − da_rand ≥ 0.083（2 概念以上）。
  反証: da_rand ≥ da_ex（乱数の向きでも同じだけ上がる）。
  それ以外: 判定しない。
  記述: vec_rand の explain・joint、概念ごとの apply の変わり方（E64 の vec_ex と比べて）、vec_none_re と E64 の vec_none の一致。

開示:
  - E64 の結果（da_ex = 0.25、概念ごとの動き）を見てから書いた。
  - 乱数の向きは概念ごとに 1 本だけ。種を変えた繰り返しはしない。
  - vec_ex は E64 の測りの値を使い、ここでは測り直さない。同じ走りの中で vec_ex と vec_rand を並べてはいない。
    vec_none_re が E64 の vec_none と合えば、測りの決定性の確かめになる。合わなければ、それを開示し、判定は E64 の値で行う。
  - 支持でも、「explain の学習が apply に効く」ことの一部（向きの特定性）しか言えない。
    explain の教師の中身（答えを示して理由を選ばせる）が apply の答えを含むなら、それは転移でなく漏れでありうる。
  - 4B は範囲の外（仮説が model_15b に限る）。測らない。

使い方:
  MALLOC_ARENA_MAX=2 python e65_explain_lever_specificity.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e65_<model>.json（途中保存 results/e65_<model>.partial.json）
"""
import argparse
import json

import torch

import e58_cross_usage_consistency as e58
from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector
from e58_cross_usage_consistency import USAGES, measure, summarize
from e64_explain_lever_joint import patch

CONDS = ("vec_rand", "vec_none_re")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--layer", type=int, default=8)
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2c"]
    choice = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    concepts = sorted({it["defs"][0] for it in items})
    e64 = json.loads((ROOT / "results" / f"e64_{short}.json").read_text(encoding="utf-8"))

    r = Runner(args.model, args.dtype)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)
    d_model = r.model.config.hidden_size

    rand = {}
    for i, c in enumerate(concepts):
        g = torch.Generator().manual_seed(6500 + i)
        v = torch.randn(d_model, generator=g)
        rand[c] = (v / v.norm() * e64["train"][c]["norm"]).to(next(r.model.parameters()).dtype)

    mpart = ROOT / "results" / f"e65_{short}.partial.json"
    rows = json.loads(mpart.read_text(encoding="utf-8")) if mpart.exists() else {c: {} for c in CONDS}
    resumed = int(mpart.exists())
    for cond in CONDS:
        for it in items:
            L = it["defs"][0]
            if L in rows[cond]:
                continue
            patch(r, inj, None if cond == "vec_none_re" else {L: rand[L]})
            rows[cond][L] = measure(r, "near", it, defs, choice[L])
            print(cond, L, {u: round(x, 3) for u, x in rows[cond][L].items()}, flush=True)
            mpart.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    summary = {c: summarize(rows[c]) for c in CONDS}
    s_none, s_ex = e64["summary"]["vec_none"], e64["summary"]["vec_ex"]
    s_rand = summary["vec_rand"]
    da_ex = s_ex["acc"]["apply"] - s_none["acc"]["apply"]
    da_rand = s_rand["acc"]["apply"] - s_none["acc"]["apply"]
    eps = 1e-9
    if not (s_rand["acc"]["para"] >= 0.875 - eps and s_rand["acc"]["recite"] >= 0.875 - eps):
        v = "not_judged"
    elif da_ex - da_rand >= 0.083 - eps:
        v = "supported"
    elif da_rand >= da_ex - eps:
        v = "refuted"
    else:
        v = "not_judged"
    hit = lambda rs, L, u: rs[L][u] > 0
    nr, xr, rr = e64["rows"]["vec_none"], e64["rows"]["vec_ex"], rows["vec_rand"]
    per = {L: {"none": hit(nr, L, "apply"), "ex": hit(xr, L, "apply"), "rand": hit(rr, L, "apply")} for L in sorted(rr)}
    same_none = sum(int(all((rows["vec_none_re"][L][u] > 0) == (nr[L][u] > 0) for u in USAGES)) for L in rows["vec_none_re"])
    max_abs = max(abs(rows["vec_none_re"][L][u] - nr[L][u]) for L in rows["vec_none_re"] for u in USAGES)
    paired = {"da_ex": da_ex, "da_rand": da_rand, "gap": da_ex - da_rand,
              "n_apply_up_ex": sum(int(p["ex"] and not p["none"]) for p in per.values()),
              "n_apply_up_rand": sum(int(p["rand"] and not p["none"]) for p in per.values()),
              "n_apply_down_rand": sum(int(p["none"] and not p["rand"]) for p in per.values()),
              "n_none_re_same_hits": same_none, "none_re_max_abs_diff": max_abs}
    res = {"model": args.model, "args": vars(args), "rand_norm": {c: rand[c].float().norm().item() for c in concepts},
           "rows": rows, "summary": summary, "paired": paired, "per_apply": per,
           "judgment": {"explain_lever_transfers_to_apply_15b": v}, "resumed": resumed}
    (ROOT / "results" / f"e65_{short}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in CONDS:
        s = summary[c]
        print(c, {u: round(a, 3) for u, a in s["acc"].items()}, "joint", round(s["joint"], 3))
    print(paired, res["judgment"])


if __name__ == "__main__":
    main()
