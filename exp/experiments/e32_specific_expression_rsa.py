"""E32: 概念ベクトルの固有成分の似かたは、概念式の似かたと合うか（h_specific_composes_from_expression、#55）。

仮説（exp.yaml）: v_agree(specific_vector_component, concept_expression)。
  E16 で、E3 の概念ベクトル v_c を共通成分 m（概念をまたいだ平均）と固有成分 s_c = v_c − m に分けた。
  固有成分が概念式の組み立て（上位・限定の動詞・相手）と合っているかを、モデルを走らせずに、記録済みのベクトルで見る。

手順（規則で決める）:
  ベクトル: exp/experiments/results/e3_Qwen2.5-1.5B-Instruct_L8_defqa.pt（E16 が使ったもの）。概念は E16 と同じ
    （concepts_ja.json の G2c・G2k の項目の defs、24）。s_c = v_c − m。
  概念式: 各概念を表示名で exp/src/subj.yaml の nodes に対応させ、次の記号の集合 X(c) を作る:
    上位の連鎖（tc.build() の T.up をたどる。any と概念自身は入れない）、mod の動詞（of の 0 番目）と向き（of の 1 番目を
    "side:" を付けて）、mod の with、mod の at の軸の名（"axis:" を付けて）、neg が真なら "neg"。
    mod が並びなら、各要素から同じように集める。名は短い名。
  似かた:
    ベクトル: 概念の組ごとの余弦。式: 組ごとの X の Jaccard。
    合い: 276 組の上で、二つの似かたのスピアマンの順位相関 rho。
    有意性: 概念のラベルを並べ替える置換（Mantel、10000 回、乱数の種 0）で、置換の rho が観測以上になる割合 p（片側）。
  条件: specific（s_c）を判定に使う。full（v_c）もあわせて測り、報告する（判定に使わない）。
  行（e32_specific_expression_rsa.json）: "cond specific"・"cond full": {rho, p}、"concept <表示>": {node, symbols}
  要約: rho_specific, p_specific, rho_full, p_full, n_concepts, n_pairs, mean_jaccard
判定（事前に決める）: rho_specific > 0 かつ p_specific < 0.05 なら支持。そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - E3 のベクトルは、日本語の定義文を読ませた活性から作った。定義文と概念式は同じ概念を書いたものなので、合いが出ても、
    式の構造でなく定義文の語の重なりを通っているかもしれない。この実験は二つを分けない。
  - 式の似かたの数え方（記号の集合と Jaccard）は、ここで決めた一つだけ。
  - 結果は予想しない。
使い方:
  python exp/experiments/e32_specific_expression_rsa.py
"""
import contextlib
import io
import json
import random
import subprocess
import sys
from pathlib import Path

import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
VEC = ROOT / "exp/experiments/results/e3_Qwen2.5-1.5B-Instruct_L8_defqa.pt"
DATA = ROOT / "exp/experiments/data/concepts_ja.json"
OUT = ROOT / "exp/experiments/results/e32_specific_expression_rsa.json"
N_PERM, SEED = 10000, 0


def ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def symbols(T, tc, q, node):
    X = set()
    u = T.up(q)
    hops = 0
    while u and u != "any" and hops < 50:
        X.add(tc.short(u))
        u, hops = T.up(u), hops + 1
    mods = node.get("mod")
    for m in (mods if isinstance(mods, list) else [mods] if mods else []):
        of = m.get("of") or []
        if of:
            X.add(str(of[0]))
        if len(of) > 1:
            X.add(f"side:{of[1]}")
        if m.get("with") is not None:
            X.add(str(m["with"]))
        for a in (m.get("at") or {}):
            X.add(f"axis:{a}")
        if m.get("neg"):
            X.add("neg")
    return X


def main():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cs = sorted({d for it in data["items"] if it["group"] in ("G2c", "G2k") for d in it["defs"]})
    nodes = yaml.safe_load((ROOT / "exp/src/subj.yaml").read_text(encoding="utf-8"))["nodes"]
    by = {v.get("display"): k for k, v in nodes.items()}
    vec = torch.load(VEC)
    vec = vec[0] if isinstance(vec, tuple) else vec
    V = {c: vec[c].float() for c in cs}
    m = torch.stack([V[c] for c in cs]).mean(0)
    conds = {"specific": {c: V[c] - m for c in cs}, "full": V}
    X = {c: symbols(T, tc, T.resolve(by[c], "subj"), nodes[by[c]]) for c in cs}
    pairs = [(i, j) for i in range(len(cs)) for j in range(i + 1, len(cs))]
    jac = lambda a, b: len(X[a] & X[b]) / len(X[a] | X[b]) if X[a] | X[b] else 0.0
    rows = {}
    s = {"n_concepts": len(cs), "n_pairs": len(pairs)}
    J = [jac(cs[i], cs[j]) for i, j in pairs]
    s["mean_jaccard"] = sum(J) / len(J)
    for name, W in conds.items():
        cos = {(i, j): torch.nn.functional.cosine_similarity(W[cs[i]], W[cs[j]], dim=0).item() for i, j in pairs}
        C = [cos[p] for p in pairs]
        rho = spearman(C, J)
        rng = random.Random(SEED)
        hit = 0
        for _ in range(N_PERM):
            perm = list(range(len(cs)))
            rng.shuffle(perm)
            Jp = [jac(cs[perm[i]], cs[perm[j]]) for i, j in pairs]
            hit += spearman(C, Jp) >= rho
        p = hit / N_PERM
        rows[f"cond {name}"] = {"rho": rho, "p": p}
        s[f"rho_{name}"], s[f"p_{name}"] = rho, p
        print(name, round(rho, 4), p, flush=True)
    for c in cs:
        rows[f"concept {c}"] = {"node": by[c], "symbols": sorted(X[c])}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "支持" if s["rho_specific"] > 0 and s["p_specific"] < 0.05 else "反証")


if __name__ == "__main__":
    main()
