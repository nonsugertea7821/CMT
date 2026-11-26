"""h_region_by_opaque_expression を確かめる: 表示語を通さず、識別子を無意味にした式だけを通しても、中点に落ちる成員は式の残りが組に近いか。

仮説（exp.yaml）: v_depend(midpoint_membership, opaque_expression)。
  #960（h_region_by_expression、支持）では、表示語を通して、上位概念の群の中で中点に最も近い成員が、式の残りの近い成員に偏った
  （層 8 で T = 0.615、帰無 0.500）。ただし表示語の字の重なりでも同じ偏り（0.624）が出て、式と字を分けられなかった。
  ここでは表示語を一切通さない。モデルが見るのは、式の形と、上位の公理（ontology・syntax）の名前だけ。

手順（#960 の geo_region_by_expression と同じ。違うのは、モデルに通す文字列だけ）:
  モデル・層・語の通し方は geo_axis_readout_midpoint の vectors（「を前に置き、文字列のトークン位置で平均。判定は層 8、層 14・20 は記録のみ）。
  概念・群・式の特徴・中点の位置の得点・統計量 T・帰無（群の中で式の割り当てを入れ替える、2000 回、numpy の default_rng(0)）・
  字の重なり（表示語の字の 2-gram）は #960 と同じ。判定に使う特徴は #960 と同じ式の特徴（参照先の名前と、その extends を含む）。
  通す文字列（無意味にした式）:
    節点から display と gloss を除き、キーの順のまま {k: v, ...} の形に書く。
    値が節点の名前で、ontology. か syntax. で始まるものは、そのまま書く。
    ほかの節点の名前は、その式の中で出てきた順に X01, X02, ... に置き換える（式ごとに番号を振り直す。式をまたいで同じ記号が同じ節点を指すことはない）。
    節点の名前でない値は、そのまま書く。
  記録だけ（判定には使わない）:
    - 字の重なりの T_surface（モデルは表示語を見ないので、これが高ければ、表示語の字と式の近さが体系の中で絡んでいる分）。
    - 群ごとの T、式の重なりと余弦の相関、探り（承認と入金、承認する・入金する）。
    - 無意味にした式の文字列が同じになる概念の数。
判定（事前に決める。層 8 だけで）:
  支持: T − null_mean ≥ 0.05 かつ p ≤ 0.05。
  そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - モデルを通す前に、体系だけで文字列を作った（登録の時点で、759 の概念から 511 通りの文字列。同じ文字列の概念は同じベクトルになる）。
    同じ文字列の成員は組の片方と同じ位置に置かれるので、中点に最も近くなりやすい。これは式の形が同じことの直接の反映で、偏りとして扱わない。
  - 番号を式ごとに振り直すので、参照先が同じかどうかはモデルに見えない（見えるのは、ontology・syntax の名前と、形）。
    判定の特徴は参照先の名前を含むので、モデルに見えない差も特徴に入る。そのぶん T は下がる方向に偏る。
  - extends が ontology・syntax でない群（exp の群など）では、上位概念も X01 になる。群の中ではすべて同じなので、群の中の比較には効かない。
  - 承認と入金は、無意味にした式の文字列が同じになる（{extends: ontology.process, mod: [{of: [X01, to]}]}）。モデルの中でも同じ位置になる。
  - 文字列はトークンが長い（最長 294 字）ので、語のときより、形の記号（括弧・キー）が平均に多く入る。
使い方:
  python exp/experiments/geo_region_by_opaque_expression.py
"""
import contextlib
import importlib.util
import io
import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_region_by_opaque_expression.json"
DROP = ("extends", "display", "gloss")
MIN_GROUP = 4
N_NULL = 2000
KEEP = ("ontology.", "syntax.")
PROBE = [("subj.approval", "subj.payment"), ("subj.v_approve", "subj.v_pay")]


def first():
    spec = importlib.util.spec_from_file_location("geo1", ROOT / "exp/experiments/geo_axis_readout_midpoint.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def system():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, _, _ = tc.build()
    return T.N


def features(N, q):
    out = set()

    def walk(path, x):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(f"{path}.{k}" if path else k, v)
        elif isinstance(x, list):
            for v in x:
                walk(path, v)
        elif isinstance(x, str) and x in N:
            out.add((path, x))
            e = N[x].get("extends") if isinstance(N[x], dict) else None
            out.add((path, f"<{json.dumps(e, ensure_ascii=False, sort_keys=True)}>"))
        else:
            out.add((path, json.dumps(x, ensure_ascii=False)))

    walk("", {k: v for k, v in N[q].items() if k not in DROP})
    return frozenset(out)


def render(N, q):
    code = {}

    def r(x):
        if isinstance(x, dict):
            return "{" + ", ".join(f"{k}: {r(v)}" for k, v in x.items()) + "}"
        if isinstance(x, list):
            return "[" + ", ".join(r(v) for v in x) + "]"
        if isinstance(x, str) and x in N and not x.startswith(KEEP):
            code.setdefault(x, f"X{len(code) + 1:02d}")
            return code[x]
        return str(x)

    return r({k: v for k, v in N[q].items() if k not in ("display", "gloss")})


def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def bigrams(s):
    return frozenset(s[i:i + 2] for i in range(len(s) - 1)) or frozenset([s])


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def nearest_table(groups, X, idx):
    tab = {}
    for g, ms in groups.items():
        V = X[[idx[q] for q in ms]]
        V = torch.nn.functional.normalize(V, dim=1)
        rows = []
        for i, j in itertools.combinations(range(len(ms)), 2):
            m = (V[i] + V[j]) / 2
            sims = V @ m
            sims[i] = sims[j] = -2
            rows.append((i, j, int(sims.argmax())))
        tab[g] = rows
    return tab


def simmats(groups, feat):
    return {g: np.array([[jac(feat[a], feat[b]) for b in ms] for a in ms]) for g, ms in groups.items()}


def stat(groups, tab, S, perm=None):
    per, tot, cnt = {}, 0.0, 0
    for g, ms in groups.items():
        M = S[g] if perm is None else S[g][np.ix_(perm[g], perm[g])]
        n = len(ms)
        I, J, C = (np.array(x) for x in zip(*tab[g]))
        s = np.minimum(M[:, I], M[:, J]).T
        sc = s[np.arange(len(C)), C][:, None]
        mask = np.ones_like(s, dtype=bool)
        mask[np.arange(len(I)), I] = False
        mask[np.arange(len(J)), J] = False
        less = ((s < sc) & mask).sum(1)
        eq = ((s == sc) & mask).sum(1) - 1
        pct = (less + eq / 2) / (n - 3)
        per[g] = float(pct.mean())
        tot += float(pct.sum())
        cnt += len(pct)
    return tot / cnt, per


def null(groups, tab, S, seed):
    rng = np.random.default_rng(seed)
    return [stat(groups, tab, S, {g: rng.permutation(len(ms)) for g, ms in groups.items()})[0] for _ in range(N_NULL)]


def spearman(xs, ys):
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def main():
    N = system()
    g1 = first()
    concepts = sorted(q for q, n in N.items() if isinstance(n, dict)
                      and isinstance(n.get("extends"), str) and isinstance(n.get("display"), str))
    disp = {q: N[q]["display"] for q in concepts}
    text = {q: render(N, q) for q in concepts}
    feat = {q: features(N, q) for q in concepts}
    surf = {q: bigrams(disp[q]) for q in concepts}
    groups = {}
    for q in concepts:
        groups.setdefault(N[q]["extends"], []).append(q)
    groups = {g: ms for g, ms in sorted(groups.items()) if len(ms) >= MIN_GROUP}
    SF, SS = simmats(groups, feat), simmats(groups, surf)
    words = sorted(set(text.values()))
    vec = g1.vectors(words)
    idx = {q: i for i, q in enumerate(concepts)}
    summary = {"n_concepts": len(concepts), "n_groups": len(groups),
               "n_texts": len(set(text.values())), "n_pairs": sum(len(ms) * (len(ms) - 1) // 2 for ms in groups.values())}
    per_layer = {}
    probe = {}
    for L in g1.LAYERS:
        X = torch.stack([vec[L][text[q]] for q in concepts])
        X = X - X.mean(0, keepdim=True)
        tab = nearest_table(groups, X, idx)
        T, per = stat(groups, tab, SF)
        nl = null(groups, tab, SF, 0)
        Ts, pers = stat(groups, tab, SS)
        nls = null(groups, tab, SS, 0)
        Xn = torch.nn.functional.normalize(X, dim=1)
        jx, cy = [], []
        for ms in groups.values():
            for a, b in itertools.combinations(ms, 2):
                jx.append(jac(feat[a], feat[b]))
                cy.append(float(Xn[idx[a]] @ Xn[idx[b]]))
        summary[f"T_L{L}"] = T
        summary[f"null_mean_L{L}"] = sum(nl) / len(nl)
        summary[f"p_L{L}"] = sum(1 for v in nl if v >= T) / len(nl)
        summary[f"T_surface_L{L}"] = Ts
        summary[f"null_mean_surface_L{L}"] = sum(nls) / len(nls)
        summary[f"p_surface_L{L}"] = sum(1 for v in nls if v >= Ts) / len(nls)
        summary[f"spearman_expr_cos_L{L}"] = spearman(jx, cy)
        per_layer[L] = {g: {"n": len(groups[g]), "T": per[g], "T_surface": pers[g]} for g in groups}
        pr = {}
        for a, b in PROBE:
            if a in idx and b in idx:
                row = {"cos": float(Xn[idx[a]] @ Xn[idx[b]]), "same_features": feat[a] == feat[b], "same_text": text[a] == text[b]}
                for q in (a, b):
                    s = Xn @ Xn[idx[q]]
                    s[idx[q]] = -2
                    top = torch.topk(s, 5).indices.tolist()
                    row[f"near {q}"] = [[concepts[i], disp[concepts[i]], round(float(s[i]), 4)] for i in top]
                pr[f"{a} / {b}"] = row
        probe[L] = pr
    J = g1.JUDGE
    gap = summary[f"T_L{J}"] - summary[f"null_mean_L{J}"]
    j = "support" if gap >= 0.05 and summary[f"p_L{J}"] <= 0.05 else "refute"
    summary["gap_L8"] = gap
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/geo_region_by_opaque_expression.py", "_commit": rev, "model": g1.MODEL,
                               "summary": summary, "judgment": {"h_region_by_opaque_expression": j},
                               "groups": {f"L{L}": v for L, v in per_layer.items()},
                               "probe": {f"L{L}": v for L, v in probe.items()}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps(probe[J], ensure_ascii=False))
    print(json.dumps({"h_region_by_opaque_expression": j}))


if __name__ == "__main__":
    main()
