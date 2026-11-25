"""E64: explain を上げる手で、1.5B の joint は付いてくるか（h_consistency_bound_by_explain）。

系列:
  E58（#847）で使い方をまたぐ一貫 joint を測った（1.5B の near 0.458）。
  E63（#861）で、opaque 改名は 1.5B の apply を動かさなかった（0.583 → 0.583）が、joint は 0.458 → 0.542 に上がった。
  上がったのは explain（0.833 → 0.958）と para（0.958 → 1.0）。そこで次を登録した（#862）:
    h_consistency_bound_by_explain: v_rely(cross_usage_consistency, usage_explain)、範囲 model_15b
  E63 の near で、explain だけを外していた概念は 3 つ（完了・売上・平日）。
  ここでは explain を直接上げる手を入れて、joint が付いてくるかを測る。

手（ベクトル。E36 の ex と同じ作り方）:
  E36 の train_explain を import して、概念ごとに 1 本、層 8 のベクトルを学習し直す（ゼロから、Adam、lr 0.1、30 歩、--micro 4）。
  教師は E36 と同じ: train_qa_ja.json の学習用の設問に、答えを示して理由を選ばせる形（定義の前置きなし）。評価の G2c の設問は使わない。
  E36 の ex.pt はリポジトリにも手元にもないので、学習し直す。E36 のスクリプトは走らせない（記録済みの結果を上書きするため）。
  E36 では、この手で E36 の形の explain が 0.417 → 1.0、apply が 0.375 → 0.667 になった（near の前置きなしの形）。

測り（E58 の measure をそのまま使う。near の前置きあり、4 つの使い方）:
  vec_none  ベクトルなし（E58・E63 の near の測り直し）
  vec_ex    同じ設問・同じ前置きで、文中の概念の語の位置すべてにベクトルを加える（E3 の build_delta と同じ置き方）
  recite は nll の差なので、prompt と answer を別々にトークン化したまま（E58 と同じ）、それぞれの語の位置に置いた delta をつなぐ。

判定（事前登録。Qwen2.5-1.5B-Instruct、float32。24 概念）:
  hit[c][u] = margin > 0。joint = 4 つすべて hit の割合。
  E = vec_none で、explain だけを外し、ほかの 3 つは hit の概念の集まり。
  de = explain の acc の上がり（vec_ex − vec_none）、da = apply の上がり、dj = joint の上がり。
  前提: |E| ≥ 2 かつ de ≥ 0.083（2 概念以上）。満たさなければ判定しない。
  支持: dj ≥ 0.083 かつ、E のうち半分以上（切り上げ）が vec_ex で joint の hit になる。
  反証: dj ≤ 0。
  それ以外: 判定しない。
  da は判定に使わず報告する（ベクトルは apply も上げうる。E のうち joint に変わった概念は、もともと apply が hit なので、
  そこでの joint の上がりは apply の上がりによらない）。

開示:
  - E63 の 1.5B の数字（near の acc と、explain だけを外した 3 概念）を見てから、この手順を書いた。
  - ベクトルはほかの使い方（para・recite・apply）を下げうる。その場合 dj ≤ 0 になって反証になりうるが、
    それは「この手で joint が付いてこない」ことで、explain に依ること自体を否定するとは限らない。
    そのときは、E の概念の行で、どの使い方が外れに変わったかを書く。
  - 学習の教師の形（前置きなし）と、測りの形（near の前置きあり）は違う。
  - 4B は範囲の外（仮説が model_15b に限る）。測らない。

途中保存:
  学習: results/e64_<model>.partial.pt（概念ごと）。測り: results/e64_<model>.partial.json（条件と概念ごと）。
  再実行で続きから進める。MALLOC_ARENA_MAX=2 を付けて走らせる。

使い方:
  MALLOC_ARENA_MAX=2 python e64_explain_lever_joint.py --model Qwen/Qwen2.5-1.5B-Instruct --micro 4
  出力: results/e64_<model>.json
"""
import argparse
import json
import time

import torch

import e58_cross_usage_consistency as e58
from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, build_delta
from e36_explain_to_apply import explain_pairs, train_explain
from e58_cross_usage_consistency import USAGES, measure, summarize

CONDS = ("vec_none", "vec_ex")


def patch(r, inj, vec):
    """e58 の two_choice と nll を、vec を語の位置に加える版に差し替える。vec が None なら加えない。"""
    d_model = r.model.config.hidden_size

    def logits_last(text):
        if vec is None:
            ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
            inj.delta = None
        else:
            ids, inj.delta = build_delta(r.tok, text, vec, d_model)
        out = r.model(ids).logits[0, -1]
        inj.delta = None
        return out

    @torch.no_grad()
    def two_choice(r_, user_of):
        ms = []
        for swap in (False, True):
            body, correct_no = user_of(swap)
            last = logits_last(r_.render(None, body))
            l1, l2 = last[r_.id1].item(), last[r_.id2].item()
            ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
        return sum(ms) / 2

    @torch.no_grad()
    def nll(r_, prompt, answer):
        p = r_.tok(prompt, add_special_tokens=False).input_ids
        a = r_.tok(answer, add_special_tokens=False).input_ids
        if vec is None:
            ids = torch.tensor([p + a])
            inj.delta = None
        else:
            _, dp = build_delta(r_.tok, prompt, vec, d_model)
            _, da_ = build_delta(r_.tok, answer, vec, d_model)
            ids = torch.tensor([p + a])
            inj.delta = torch.cat([dp, da_], dim=1)
        labels = ids.clone()
        labels[:, : len(p)] = -100
        out = r_.model(ids, labels=labels).loss.item()
        inj.delta = None
        return out

    e58.two_choice = two_choice
    e58.nll = nll


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

    r = Runner(args.model, args.dtype)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)

    tpart = ROOT / "results" / f"e64_{short}.partial.pt"
    ex, log = torch.load(tpart) if tpart.exists() else ({}, {})
    for c in concepts:
        if c in ex:
            continue
        t0 = time.time()
        v, losses = train_explain(r, inj, c, explain_pairs(r, c, qa[c], choice[c]), args.steps, args.lr, args.micro)
        ex[c] = v
        log[c] = {"loss_first": losses[0], "loss_last": losses[-1], "norm": v.norm().item(),
                  "n_train": 2 * len(qa[c]), "micro": args.micro}
        print(f"[train] {c}: loss {losses[0]:.2f} -> {losses[-1]:.2f} |v|={v.norm():.1f} {time.time() - t0:.0f}s",
              flush=True)
        torch.save((ex, log), tpart)

    mpart = ROOT / "results" / f"e64_{short}.partial.json"
    rows = json.loads(mpart.read_text(encoding="utf-8")) if mpart.exists() else {c: {} for c in CONDS}
    resumed = int(mpart.exists())
    for cond in CONDS:
        for it in items:
            L = it["defs"][0]
            if L in rows[cond]:
                continue
            patch(r, inj, None if cond == "vec_none" else {L: ex[L]})
            rows[cond][L] = measure(r, "near", it, defs, choice[L])
            print(cond, L, {u: round(x, 3) for u, x in rows[cond][L].items()}, flush=True)
            mpart.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    summary = {c: summarize(rows[c]) for c in CONDS}
    hit = {c: {L: {u: rows[c][L][u] > 0 for u in USAGES} for L in rows[c]} for c in CONDS}
    E = sorted(L for L, h in hit["vec_none"].items() if not h["explain"] and all(h[u] for u in USAGES if u != "explain"))
    E_joint = sorted(L for L in E if all(hit["vec_ex"][L].values()))
    de = summary["vec_ex"]["acc"]["explain"] - summary["vec_none"]["acc"]["explain"]
    da = summary["vec_ex"]["acc"]["apply"] - summary["vec_none"]["acc"]["apply"]
    dj = summary["vec_ex"]["joint"] - summary["vec_none"]["joint"]
    eps = 1e-9
    if not (len(E) >= 2 and de >= 0.083 - eps):
        v = "not_judged"
    elif dj >= 0.083 - eps and len(E_joint) >= (len(E) + 1) // 2:
        v = "supported"
    elif dj <= eps:
        v = "refuted"
    else:
        v = "not_judged"
    res = {"model": args.model, "args": vars(args), "train": log, "rows": rows, "summary": summary,
           "paired": {"de": de, "da": da, "dj": dj, "E": E, "E_joint": E_joint, "nE": len(E), "nE_joint": len(E_joint)},
           "judgment": {"consistency_bound_by_explain": v}, "resumed": resumed}
    (ROOT / "results" / f"e64_{short}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in CONDS:
        s = summary[c]
        print(c, {u: round(a, 3) for u, a in s["acc"].items()}, "joint", round(s["joint"], 3))
    print(res["paired"], res["judgment"])


if __name__ == "__main__":
    main()
