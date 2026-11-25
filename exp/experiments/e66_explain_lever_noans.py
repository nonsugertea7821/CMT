"""E66: 1.5B で explain の手が apply を上げたのは、教師に入っていた事例の答えに頼るのか（h_explain_lever_apply_by_case_answers_15b）。

系列:
  E64（#864、支持）: 説明の設問で学習した層 8 のベクトル（vec_ex）で、apply 0.583 → 0.833。
  E65（#888、支持）: 同じ大きさの乱数の向き（vec_rand）では apply 0.583 → 0.417。学習した向きのほうが apply を上げる。
  E65 のあとで教師を読んだ: 学習の設問（train_qa_ja.json）は G2c の設問と文としては重ならない（0/24）。
    ただし教師の文は「次の問いの答えは「はい／いいえ」です。そう判断する理由として…」で、事例の答えが入っている。
  そこで登録した: h_explain_lever_apply_by_case_answers_15b: v_rely(usage_apply, teaching)、範囲 model_15b。
  問い: 事例の答えを抜いた教師で学習しても、apply は同じだけ上がるか。

手（ベクトル）:
  vec_noans: E64 と同じ学習（E36 の train_explain、ゼロから、Adam、lr 0.1、30 歩、--micro 4、層 8）。
    教師だけを変える: 指示を E20 の EXPLAIN_NOANS（「次の問いに答えるときの理由として正しいほうを選び、…」）にし、
    事例の答えを文に入れない。設問・選択肢（「〈語〉は〈定義〉を指すから」）・正答の番号は E64 と同じ。
  vec_ex は学習し直さず、E64 の結果ファイルの値を使う（E64 のベクトルは残っていない）。

測り（E64 と同じ。e64.patch と e58.measure、near の前置きあり、4 つの使い方）:
  vec_noans  文中の概念の語の位置すべてに vec_noans を加える。
  測りの explain は E64 と同じ形（事例の答えを示す）。

判定（事前登録。Qwen2.5-1.5B-Instruct、float32。24 概念）:
  hit = margin > 0。acc = hit の割合。基準は E64 の vec_none（apply 0.583、explain 0.833）。
  da_ex = 0.25（E64）。da_noans = apply(vec_noans) − apply(E64 の vec_none)。
  de_noans = explain(vec_noans) − explain(E64 の vec_none)。
  前提（答えを抜いても説明の手であること）: de_noans ≥ 0.083（2 概念以上）。満たさなければ判定しない。
  支持: da_ex − da_noans ≥ 0.083（答えを抜くと、apply の上がりが 2 概念以上減る）。
  反証: da_noans ≥ da_ex（答えを抜いても、apply は同じかそれ以上上がる）。
  それ以外: 判定しない。
  記述: vec_noans の para・recite・joint、概念ごとの apply の変わり方（E64 の vec_ex、E65 の vec_rand と比べて）、
    学習の損失と大きさ（E64 の vec_ex の大きさと比べて）。

開示:
  - E64・E65 の結果と、教師の文を読んでから書いた。
  - 教師から抜いたのは事例の答えだけではない。指示の文も変わる（「答えは…です。そう判断する理由」→「答えるときの理由」）。
    支持でも、apply の上がりが「答えの語」に頼るのか「判断の理由を問う指示」に頼るのかは分けない。
  - vec_ex は E64 の値を使い、同じ走りで学習し直していない。学習が同じ結果を再現するかは確かめていない。
  - 前提を満たさない（答えを抜くと explain も上がらない）なら、答えを抜いた教師は説明の手として別物で、
    apply の比べは判定に使わない。
  - 4B は範囲の外（仮説が model_15b に限る）。測らない。

途中保存:
  学習: results/e66_<model>.partial.pt（概念ごと。リポジトリには足さない）。
  測り: results/e66_<model>.partial.json（概念ごと）。再実行で続きから進める。

使い方:
  MALLOC_ARENA_MAX=2 python e66_explain_lever_noans.py --model Qwen/Qwen2.5-1.5B-Instruct --micro 4
  出力: results/e66_<model>.json
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner
from e20_explain_transfer import EXPLAIN_NOANS
from e3_concept_vectors import Injector
from e36_explain_to_apply import train_explain
from e58_cross_usage_consistency import USAGES, measure, summarize
from e64_explain_lever_joint import patch


def noans_pairs(r, label, qa, pair):
    out = []
    for ex in qa:
        for swap in (False, True):
            opts = [f"「{label}」は{pair['project']}を指すから", f"「{label}」は{pair['ordinary']}を指すから"]
            no = 1
            if swap:
                opts.reverse()
                no = 2
            body = f"{EXPLAIN_NOANS}\n{ex['q']}\n1. {opts[0]}\n2. {opts[1]}"
            out.append((r.render(None, body), str(no)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--micro", type=int, default=None)
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2c"]
    choice = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]
    concepts = sorted({it["defs"][0] for it in items})
    e64 = json.loads((ROOT / "results" / f"e64_{short}.json").read_text(encoding="utf-8"))
    e65 = json.loads((ROOT / "results" / f"e65_{short}.json").read_text(encoding="utf-8"))

    r = Runner(args.model, args.dtype)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)

    tpart = ROOT / "results" / f"e66_{short}.partial.pt"
    vec, log = torch.load(tpart) if tpart.exists() else ({}, {})
    for c in concepts:
        if c in vec:
            continue
        t0 = time.time()
        v, losses = train_explain(r, inj, c, noans_pairs(r, c, qa[c], choice[c]), args.steps, args.lr, args.micro)
        vec[c] = v
        log[c] = {"loss_first": losses[0], "loss_last": losses[-1], "norm": v.norm().item(),
                  "n_train": 2 * len(qa[c]), "micro": args.micro}
        print(f"[train] {c}: loss {losses[0]:.2f} -> {losses[-1]:.2f} |v|={v.norm():.1f} {time.time() - t0:.0f}s",
              flush=True)
        torch.save((vec, log), tpart)

    mpart = ROOT / "results" / f"e66_{short}.partial.json"
    rows = json.loads(mpart.read_text(encoding="utf-8")) if mpart.exists() else {"vec_noans": {}}
    resumed = int(mpart.exists())
    for it in items:
        L = it["defs"][0]
        if L in rows["vec_noans"]:
            continue
        patch(r, inj, {L: vec[L]})
        rows["vec_noans"][L] = measure(r, "near", it, defs, choice[L])
        print("vec_noans", L, {u: round(x, 3) for u, x in rows["vec_noans"][L].items()}, flush=True)
        mpart.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    s = summarize(rows["vec_noans"])
    s_none, s_ex = e64["summary"]["vec_none"], e64["summary"]["vec_ex"]
    da_ex = s_ex["acc"]["apply"] - s_none["acc"]["apply"]
    da_noans = s["acc"]["apply"] - s_none["acc"]["apply"]
    de_noans = s["acc"]["explain"] - s_none["acc"]["explain"]
    eps = 1e-9
    if not de_noans >= 0.083 - eps:
        v = "not_judged"
    elif da_ex - da_noans >= 0.083 - eps:
        v = "supported"
    elif da_noans >= da_ex - eps:
        v = "refuted"
    else:
        v = "not_judged"
    hit = lambda rs, L: rs[L]["apply"] > 0
    nr, xr, rr, qr = e64["rows"]["vec_none"], e64["rows"]["vec_ex"], e65["rows"]["vec_rand"], rows["vec_noans"]
    per = {L: {"none": hit(nr, L), "ex": hit(xr, L), "rand": hit(rr, L), "noans": hit(qr, L)} for L in sorted(qr)}
    up = lambda k: sorted(L for L, p in per.items() if p[k] and not p["none"])
    down = lambda k: sorted(L for L, p in per.items() if p["none"] and not p[k])
    paired = {"da_ex": da_ex, "da_noans": da_noans, "de_noans": de_noans, "gap": da_ex - da_noans,
              "up_ex": up("ex"), "up_noans": up("noans"), "up_rand": up("rand"),
              "down_ex": down("ex"), "down_noans": down("noans"), "down_rand": down("rand"),
              "n_up_noans": len(up("noans")), "n_down_noans": len(down("noans")),
              "n_up_noans_and_ex": len(set(up("noans")) & set(up("ex"))),
              "norm_ratio_mean": sum(log[c]["norm"] / e64["train"][c]["norm"] for c in concepts) / len(concepts)}
    res = {"model": args.model, "args": vars(args), "train": log, "rows": rows, "summary": {"vec_noans": s},
           "paired": paired, "per_apply": per, "judgment": {"explain_lever_apply_by_case_answers_15b": v},
           "resumed": resumed}
    (ROOT / "results" / f"e66_{short}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("vec_noans", {u: round(a, 3) for u, a in s["acc"].items()}, "joint", round(s["joint"], 3))
    print(paired, res["judgment"])


if __name__ == "__main__":
    main()
