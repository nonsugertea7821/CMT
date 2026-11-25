"""h_midpoint_by_token_position を確かめる: 中点の帰属は、語のどのトークン位置を読むかに依存するか。

仮説（exp.yaml）: {v_depend, from: midpoint_membership, to: label_token_positions}。
  読み: 複数トークンに分かれた語の意味は、前の層で最後のトークンに組み上がる（detokenization）。
  語のトークン全部を平均して読むと、断片のトークンが混ざり、類の成分が薄まる。

系列:
  #364（geo_cross_genus_midpoint）: 120 語、平均で読み、L8 の G_rate 0.779。
  #779（geo_genus_region_immune_display）: 字面を書き替えた語（多くはひらがな）では、平均で読むと L8 の G_rate 0.229、
    元と書き替えを混ぜると 0.436（drop 0.343、反証）。

手順:
  geo_cross_genus_midpoint の GENUS・CROSS・FILLER・MODEL・LAYERS・JUDGE・rate と、
  geo_genus_region_immune_display の SWAP・mixed_rate を読み込む（どちらの main も走らせない）。
  元の 120 語と書き替えの 120 語を、#364 と同じく「w で通す。語のトークン位置は p..q-1（p は「だけの長さ）。
  読み方 3 つ:
    mean: 語のトークン位置の平均（#364・#779 と同じ。値の一致を記録する）。
    last: 語の最後のトークン位置。
    first: 語の最初のトークン位置（参考）。
  読み方ごとに、#779 と同じ条件 orig・swap・mixed の G_rate・C_rate と、L8 の R_rate・holds を計算する。
  語ごとのトークン数（q − p）を記録する。
  記録のみ: L8・last で、書き替えの語のトークン数が 1・2・3 以上の成員の組（swap 条件で、a と b のトークン数の大きいほう）ごとの当たりの率。
判定（事前に決める。L8 だけで）:
  rec = G_rate(swap, last) − G_rate(swap, mean)。
  支持: rec ≥ 0.15 かつ holds(swap, last)。
  反証: rec < 0.05。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #364 と #779 の mean の値を知っている。
  - 1 トークンの語では、mean・last・first は同じ値になる。元の字面の語は 1 トークンが多いので、orig は読み方でほとんど変わらない見込み。
  - last は、語の後ろに何も続かない位置なので、次に来る語の予測の成分も入りうる。
  - トークン数と書き方（ひらがな・カタカナ・漢字）は一緒に動く。読み方を替えて戻る量は測れるが、学んだ量の効きとはまだ分けられない。
使い方:
  python exp/experiments/geo_midpoint_by_token_position.py
  出力: exp/experiments/results/geo_midpoint_by_token_position.json
"""
import importlib.util
import itertools
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_midpoint_by_token_position.json"
READS = ["mean", "last", "first"]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mean(xs):
    return sum(xs) / len(xs)


def vectors(g, words):
    tok = AutoTokenizer.from_pretrained(g.MODEL)
    model = AutoModelForCausalLM.from_pretrained(g.MODEL, torch_dtype=torch.float32)
    model.eval()
    p = len(tok("「", add_special_tokens=False)["input_ids"])
    out = {r: {L: {} for L in g.LAYERS} for r in READS}
    ntok = {}
    with torch.no_grad():
        for w in words:
            ids = tok("「" + w, add_special_tokens=False, return_tensors="pt")["input_ids"]
            q = ids.shape[1]
            assert q > p, w
            ntok[w] = q - p
            hs = model(ids, output_hidden_states=True).hidden_states
            for L in g.LAYERS:
                h = hs[L][0]
                out["mean"][L][w] = h[p:q].mean(0)
                out["last"][L][w] = h[q - 1]
                out["first"][L][w] = h[p]
    return out, ntok


def main():
    g = module("geo_cross_genus_midpoint")
    s = module("geo_genus_region_immune_display")
    sets = {**{k: ("G", v) for k, v in g.GENUS.items()}, **{k: ("C", v) for k, v in g.CROSS.items()}}
    base = [w for _, ws in sets.values() for w in ws] + g.FILLER
    SWAP = s.SWAP
    vec, ntok = vectors(g, base + [SWAP[w] for w in base])
    mixed_vocab = [("o", w) for w in base] + [("s", w) for w in base]
    form = {k: i for i, k in enumerate(mixed_vocab)}
    idx = {w: i for i, w in enumerate(base)}
    rng = random.Random(0)
    rsets = [rng.sample(base, 8) for _ in range(200)]
    res = {"reads": {}, "ntok": ntok}
    for rd in READS:
        layers = {}
        for L in g.LAYERS:
            Xo = torch.stack([vec[rd][L][w] for w in base])
            Xs = torch.stack([vec[rd][L][SWAP[w]] for w in base])
            Xm = torch.cat([Xo, Xs])
            Xo = Xo - Xo.mean(0, keepdim=True)
            Xs = Xs - Xs.mean(0, keepdim=True)
            Xm = Xm - Xm.mean(0, keepdim=True)
            conds = {
                "orig": (lambda ws, X=Xo: g.rate(ws, base, X, idx)),
                "swap": (lambda ws, X=Xs: g.rate(ws, base, X, idx)),
                "mixed": (lambda ws, X=Xm: s.mixed_rate(ws, mixed_vocab, X, form)),
            }
            row = {}
            for c, f in conds.items():
                G = mean([f(ws) for k, (_, ws) in sets.items() if k in g.GENUS])
                C = mean([f(ws) for k, (_, ws) in sets.items() if k in g.CROSS])
                row[c] = {"G_rate": G, "C_rate": C}
                if L == g.JUDGE:
                    R = mean([f(ws) for ws in rsets])
                    row[c].update(R_rate=R, holds=1 if G - R >= 0.15 else 0)
            row["drop"] = row["orig"]["G_rate"] - row["mixed"]["G_rate"]
            layers[str(L)] = row
            print(rd, L, json.dumps(row), flush=True)
        res["reads"][rd] = layers
    X = torch.stack([vec["last"][g.JUDGE][SWAP[w]] for w in base])
    X = X - X.mean(0, keepdim=True)
    by_n = {}
    for k in g.GENUS:
        ws = g.GENUS[k]
        for a, b in itertools.combinations(ws, 2):
            m = (X[idx[a]] + X[idx[b]]) / 2
            sims = torch.nn.functional.cosine_similarity(X, m.unsqueeze(0), dim=1)
            sims[idx[a]] = -2
            sims[idx[b]] = -2
            n = min(max(ntok[SWAP[a]], ntok[SWAP[b]]), 3)
            by_n.setdefault(str(n), []).append(1.0 if base[int(sims.argmax())] in ws else 0.0)
    res["swap_last_by_ntok"] = {n: {"rate": mean(v), "pairs": len(v)} for n, v in sorted(by_n.items())}
    j = {rd: res["reads"][rd][str(g.JUDGE)] for rd in READS}
    rec = j["last"]["swap"]["G_rate"] - j["mean"]["swap"]["G_rate"]
    v = ("supported" if rec >= 0.15 and j["last"]["swap"]["holds"] else "refuted" if rec < 0.05 else "not_judged")
    res["judgment"] = {"rec": rec, "holds_swap_last": j["last"]["swap"]["holds"], "midpoint_by_token_position": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = g.MODEL
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["swap_last_by_ntok"]))
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
