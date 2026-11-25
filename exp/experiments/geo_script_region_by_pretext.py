"""h_script_region_by_pretext を確かめる: 書き替えた語の類の区画は、その書き方の文章を前に読んだ量に依存するか。

仮説（exp.yaml）: {v_depend, from: midpoint_membership, to: [pre_model_passage, syntax.display]}。
  読み: 書き替え（#779）で G_rate が落ちたのは、ひらがな・カタカナの書き方の語を、学習で読んだ量が少ないから。
  読んだ量が多ければ、書き替えた字面でも類の区画は残る。

系列:
  #364（geo_cross_genus_midpoint）: Qwen2.5-1.5B、120 語、平均で読み、L8 の G_rate 0.779。
  #779（geo_genus_region_immune_display）: 書き替えた語で L8 の G_rate 0.229（反証）。
  #782（最後のトークン）: swap 0.314、#788（外れの次元）: 戻らない（反証）。

読んだ量（pre_model_passage）は直接は測れない。代わりを 2 つ、事前に決める。
  A. モデルを替える（モデルの間）: 日本語の文章を多く学習したモデル 2 つ
     （sbintuitions/sarashina2.2-1b-instruct-v0.1、llm-jp/llm-jp-3-1.8b-instruct）と Qwen2.5-1.5B-Instruct。
  B. 語を分ける（Qwen の中）: BPE の併合は学習の文章の頻度で決まるので、書き替えた字面の
     トークン数 / 文字数（tpc）が小さい語ほど、その字面を多く読んだとみなす。

手順:
  geo_cross_genus_midpoint の GENUS・CROSS・FILLER・rate と、geo_genus_region_immune_display の SWAP を読み込む
  （どちらの main も走らせない）。取り方は #364 と同じ（「w で通し、語のトークン位置の平均、中心化）。
  層: Qwen は 8・14・20。28 層でないモデルは round(L × 層数 / 28)（24 層なら 7・12・17）。判定は L8 相当の層。
  A: モデルごとに、orig と swap の語彙それぞれで G_rate と R_rate（#364 と同じ 200 個、seed 0）。
     keep = (G_swap − R_swap) / (G_orig − R_orig)。
     gap_A = mean(keep(sarashina), keep(llm-jp)) − keep(Qwen)。
  B: Qwen の判定の層で、類の 40 語だけを使う。語 w ごとに、同じ条件（orig か swap）の語彙で、
     各類の重心（w を除く）との余弦が最も大きい類が w の類なら 1（acc）。
     類の 40 語を、書き替えた字面の tpc の中央値で 2 つに分ける（中央値と等しい語は少ない側 hi に入れる）。
     hi = tpc が小さい側（多く読んだ）、lo = 大きい側。
     d_B = (acc_swap(hi) − acc_swap(lo)) − (acc_orig(hi) − acc_orig(lo))。
     p_B: 40 語をでたらめに同じ大きさの 2 つに分ける 2000 回（seed 0）で、d_B 以上になる割合。
訂正（1 回目の実行の後、結果を見る前に。開示）:
  1 回目は B の分け方で止まった（ZeroDivisionError）。Qwen で、書き替えた類の 40 語の tpc は 1.0 が 22 語あり、
  中央値が 1.0 になって lo が空になった（中央値と等しい語を hi に入れる決めのため）。
  そのとき出ていたのは Qwen の A の値（L8 の orig G 0.779・R 0.054、swap G 0.229・R 0.044。#779 と一致）だけで、
  acc・d_B・日本語のモデルの値は出ていない。
  分け方を改める: hi = tpc が最大値より小さい語（BPE が少なくとも 1 か所を併合した字面、18 語）、
  lo = tpc が最大値の語（1 文字 1 トークン、どこも併合されない字面、22 語）。判定の線は変えない。
  記録の median は残すが、分けには使わない。
判定（事前に決める）:
  支持: gap_A ≥ 0.25 かつ d_B ≥ 0.20 かつ p_B ≤ 0.05。
  反証: gap_A ≤ 0.05 かつ d_B ≤ 0.05。
  その他: 判定しない（A と B の片方だけの記録も残す）。

開示（結果を見る前に分かっていること）:
  - Qwen の orig・swap の値（#364・#779）を知っている。日本語のモデル 2 つで、この測りはまだ走らせていない。
  - 日本語のモデルは、トークナイザーも違う。ひらがなの語が少ないトークンになりやすいこと自体が、読んだ量の表れとみなす。
    ただし、モデルの大きさ・層の数・学習の仕方も違うので、A の差のすべてを読んだ量には帰せない。
  - B の tpc は読んだ量の代わりで、トークン数が平均の取り方を変える効きも混じる。orig の差を引くのは、
    もともと分けやすい語に偏る分を除くため。
  - 層の対応（L8 → 7）は相対の深さでの近似。
使い方:
  python exp/experiments/geo_script_region_by_pretext.py
  出力: exp/experiments/results/geo_script_region_by_pretext.json
"""
import importlib.util
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_script_region_by_pretext.json"
MODELS = {
    "qwen": "Qwen/Qwen2.5-1.5B-Instruct",
    "sarashina": "sbintuitions/sarashina2.2-1b-instruct-v0.1",
    "llmjp": "llm-jp/llm-jp-3-1.8b-instruct",
}
BASE_LAYERS = [8, 14, 20]
JUDGE = 8


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def vectors(path, words):
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.float32)
    model.eval()
    n = model.config.num_hidden_layers
    layers = {L: round(L * n / 28) for L in BASE_LAYERS}
    p = len(tok("「", add_special_tokens=False)["input_ids"])
    out = {L: {} for L in BASE_LAYERS}
    ntok = {}
    with torch.no_grad():
        for w in words:
            ids = tok("「" + w, add_special_tokens=False, return_tensors="pt")["input_ids"]
            q = ids.shape[1]
            assert q > p, (path, w)
            assert tok("「", add_special_tokens=False)["input_ids"] == ids[0, :p].tolist(), (path, w)
            ntok[w] = q - p
            hs = model(ids, output_hidden_states=True).hidden_states
            for L in BASE_LAYERS:
                out[L][w] = hs[layers[L]][0, p:q].mean(0)
    return out, layers, ntok


def genus_acc(words, genus_of, X, idx):
    hits = {}
    for w in words:
        sims = {}
        for gname in set(genus_of.values()):
            mates = [v for v in words if genus_of[v] == gname and v != w]
            c = torch.stack([X[idx[v]] for v in mates]).mean(0)
            sims[gname] = float(torch.nn.functional.cosine_similarity(X[idx[w]], c, dim=0))
        hits[w] = 1.0 if max(sims, key=sims.get) == genus_of[w] else 0.0
    return hits


def main():
    g = module("geo_cross_genus_midpoint")
    s = module("geo_genus_region_immune_display")
    SWAP = s.SWAP
    sets = {**{k: ("G", v) for k, v in g.GENUS.items()}, **{k: ("C", v) for k, v in g.CROSS.items()}}
    base = [w for _, ws in sets.values() for w in ws] + g.FILLER
    idx = {w: i for i, w in enumerate(base)}
    rng = random.Random(0)
    rsets = [rng.sample(base, 8) for _ in range(200)]
    genus_of = {w: k for k, ws in g.GENUS.items() for w in ws}
    gwords = list(genus_of)
    res = {"models": {}, "rev": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                               capture_output=True, text=True).stdout.strip()}
    B = None
    for key, path in MODELS.items():
        vec, layers, ntok = vectors(path, base + [SWAP[w] for w in base])
        row = {"path": path, "layers": {str(L): layers[L] for L in BASE_LAYERS}, "conds": {}}
        for L in BASE_LAYERS:
            r = {}
            for c, ws in (("orig", base), ("swap", [SWAP[w] for w in base])):
                R = torch.stack([vec[L][w] for w in ws])
                X = R - R.mean(0, keepdim=True)
                G = mean([g.rate(m, base, X, idx) for k, (_, m) in sets.items() if k in g.GENUS])
                C = mean([g.rate(m, base, X, idx) for k, (_, m) in sets.items() if k in g.CROSS])
                r[c] = {"G_rate": G, "C_rate": C}
                if L == JUDGE:
                    r[c]["R_rate"] = mean([g.rate(m, base, X, idx) for m in rsets])
                    r[c]["acc"] = genus_acc(gwords, genus_of, X, idx)
            if L == JUDGE:
                den = r["orig"]["G_rate"] - r["orig"]["R_rate"]
                row["keep"] = (r["swap"]["G_rate"] - r["swap"]["R_rate"]) / den if den > 0 else None
            row["conds"][str(L)] = r
            print(key, L, json.dumps({c: {k: v for k, v in x.items() if k != "acc"} for c, x in r.items()}), flush=True)
        row["tokens_swap"] = {w: ntok[SWAP[w]] for w in gwords}
        row["tokens_orig"] = {w: ntok[w] for w in gwords}
        res["models"][key] = row
        if key == "qwen":
            tpc = {w: ntok[SWAP[w]] / len(SWAP[w]) for w in gwords}
            med = mean(sorted(tpc.values())[len(tpc) // 2 - 1: len(tpc) // 2 + 1])
            top = max(tpc.values())
            hi = [w for w in gwords if tpc[w] < top]
            lo = [w for w in gwords if tpc[w] == top]
            acc = {c: row["conds"][str(JUDGE)][c]["acc"] for c in ("orig", "swap")}

            def dd(h, l):
                return ((mean([acc["swap"][w] for w in h]) - mean([acc["swap"][w] for w in l]))
                        - (mean([acc["orig"][w] for w in h]) - mean([acc["orig"][w] for w in l])))

            d = dd(hi, lo)
            prng = random.Random(0)
            cnt = 0
            for _ in range(2000):
                sh = prng.sample(gwords, len(gwords))
                cnt += dd(sh[:len(hi)], sh[len(hi):]) >= d - 1e-12
            B = {"tpc": tpc, "median": med, "hi": hi, "lo": lo,
                 "acc_swap_hi": mean([acc["swap"][w] for w in hi]), "acc_swap_lo": mean([acc["swap"][w] for w in lo]),
                 "acc_orig_hi": mean([acc["orig"][w] for w in hi]), "acc_orig_lo": mean([acc["orig"][w] for w in lo]),
                 "d_B": d, "p_B": cnt / 2000}
            print("B", json.dumps({k: v for k, v in B.items() if k not in ("tpc", "hi", "lo")}), flush=True)
        del vec
    k = {m: res["models"][m]["keep"] for m in MODELS}
    gap = (mean([k["sarashina"], k["llmjp"]]) - k["qwen"]) if None not in k.values() else None
    res["B"] = B
    if gap is None:
        v = "not_judged"
    elif gap >= 0.25 and B["d_B"] >= 0.20 and B["p_B"] <= 0.05:
        v = "supported"
    elif gap <= 0.05 and B["d_B"] <= 0.05:
        v = "refuted"
    else:
        v = "not_judged"
    res["judgment"] = {"keep": k, "gap_A": gap, "d_B": B["d_B"], "p_B": B["p_B"], "script_region_by_pretext": v}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
