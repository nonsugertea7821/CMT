"""h_region_by_expression を確かめる: 同じ上位概念の中で、中点に落ちる成員は、式の残りの部分が組に近いものか。

仮説（exp.yaml）: v_depend(midpoint_membership, syntax.concept_expression)。
  読み: 中点が成員に落ちる度合いは、上位概念（extends）だけでなく、式のほかの部分にも依る。
  h_midpoint_depends_genus（支持）は、自然な語で、上位概念の集まりがまとまることを示した。
  ここでは、体系の概念の表示語で、上位概念を固定したうえで、式の残りが区画の中の位置に効くかを問う。
  識別子が辞書の鍵として一意であるには、区画が上位概念より細かく、式の全体で分かれている必要がある
  （利用者の見方: 式は概念の幾何的座標空間を示し、鍵の一意性はその形状から来る）。この実験は、その前提の前半を測る。

手順:
  モデル Qwen/Qwen2.5-1.5B-Instruct（ローカルのキャッシュ、float32、CPU）。語の通し方と層は geo_axis_readout_midpoint と同じ
  （関数 vectors をそのスクリプトから読み込み、その main は走らせない。「w を通し、w のトークン位置で平均。判定は層 8、層 14・20 は記録のみ）。
  概念: 実行のときの体系（tc.build()）で、extends と display を文字列で持つ節点。
    表示語が同じ節点が複数あるときは、同じベクトルを使う。全概念のベクトルの平均を引く（中心化）。
  式の特徴: 節点から extends・display・gloss を除いた残りを、道（キーを . でつなぐ。リストの添字は道に入れない）と葉の組に平らにする。
    葉が節点の名前なら、二つの特徴 (道, 名前) と (道, <その名前の extends>) を入れる。ほかの葉は (道, 値) を一つ入れる。
    sim(a, b) = 二つの特徴の集まりの Jaccard（どちらも空なら 0）。
  上位概念の群: extends が同じ概念の集まりのうち、4 つ以上のもの。
  中点の位置の得点: 群 S の中の組 (a, b) ごとに、
    m = (a + b) / 2。S から a, b を除いた成員のうち、m に余弦で最も近いもの c* を選ぶ。
    各成員 c の近さ s(c) = min(sim(c, a), sim(c, b))。
    pct(a, b) = c* の s を、a, b を除いた成員の中で順位にした百分位（同順位は平均の順位。0 が最低、1 が最高、偶然なら 0.5 前後）。
  統計量 T = すべての群のすべての組の pct の平均。
  帰無: 各群の中で、概念と特徴の集まりの対応をでたらめに入れ替えて（ベクトルは動かさない）T を計算する。2000 回（numpy の default_rng(0)）。
    null_mean = その平均、p = T_null ≥ T の割合。
  記録だけ（判定には使わない）:
    - 表示語の字の重なり（字の 2-gram の Jaccard）を sim の代わりに使った T_surface と、その帰無の p。
      表示語は式から訳した名前なので（d_cscl_display_derived）、式の重なりが表示語の字の重なりを通して効く見込みがある。
    - 群ごとの T と組の数。
    - 式の重なりと余弦の相関（群の中の組で、Spearman）。
    - 探り: subj.approval と subj.payment、subj.v_approve と subj.v_pay（体系で、表示語と名前を除くと式が同じ組。#954 で P の衝突）。
      それぞれの組の余弦、各概念の全概念の中で最も近い 5 つ。
  行（geo_region_by_expression.json）: summary {n_concepts, n_groups, n_pairs, T_L8, null_mean_L8, p_L8, T_surface_L8, p_surface_L8, ...}、
    groups、probe、judgment
判定（事前に決める。層 8 だけで）:
  支持: T − null_mean ≥ 0.05 かつ p ≤ 0.05。
  そうでなければ反証。

開示（結果を見る前に分かっていること）:
  - モデルを通す前に、体系だけで群を数えた（登録の時点で、表示語と extends を持つ概念は 759、4 つ以上の群は 42、群の中の組は 10009、最大の群は ontology.quality の 109）。
    式の残りが完全に同じ概念は、群の中にわずかしかない（3 つ以上そろう組み合わせは 10 余り）。そのため完全一致ではなく、重なりの度合いで測る。
  - 表示語は式から訳されるので、式が近い概念は表示語の字も近いことが多い。T が高くても、モデルが式を読んでいるとは言えない。
    言えるのは、鍵（表示語）がモデルの中で式の近さに沿った位置に置かれているか、まで。字の重なりの T_surface を並べて記録する。
  - 群の大きさは偏る（ontology.quality が組の大半を占める）。群ごとの T を記録する。
  - 語を文脈なしで通すので、多義の表示語は意味が定まらない。
  - モデルを通す前に、でたらめなベクトル（64 次元の正規乱数）で計算だけを試した: T = 0.508、帰無 100 回の平均 0.499。
  - 探りの組は、特徴に参照先の名前（subj.v_approve と subj.v_pay など）が入るので、特徴の集まりは同じにならない（same_features は偽）。
    式が名前の入れ替えだけで同じ、という #954 の意味での一致は、ここでは余弦と近い語を記録するだけで見る。
使い方:
  python exp/experiments/geo_region_by_expression.py
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
OUT = ROOT / "exp/experiments/results/geo_region_by_expression.json"
DROP = ("extends", "display", "gloss")
MIN_GROUP = 4
N_NULL = 2000
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
    feat = {q: features(N, q) for q in concepts}
    surf = {q: bigrams(disp[q]) for q in concepts}
    groups = {}
    for q in concepts:
        groups.setdefault(N[q]["extends"], []).append(q)
    groups = {g: ms for g, ms in sorted(groups.items()) if len(ms) >= MIN_GROUP}
    SF, SS = simmats(groups, feat), simmats(groups, surf)
    words = sorted(set(disp.values()))
    vec = g1.vectors(words)
    idx = {q: i for i, q in enumerate(concepts)}
    summary = {"n_concepts": len(concepts), "n_groups": len(groups),
               "n_pairs": sum(len(ms) * (len(ms) - 1) // 2 for ms in groups.values())}
    per_layer = {}
    probe = {}
    for L in g1.LAYERS:
        X = torch.stack([vec[L][disp[q]] for q in concepts])
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
                row = {"cos": float(Xn[idx[a]] @ Xn[idx[b]]), "same_features": feat[a] == feat[b]}
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
    OUT.write_text(json.dumps({"_source": "exp/experiments/geo_region_by_expression.py", "_commit": rev, "model": g1.MODEL,
                               "summary": summary, "judgment": {"h_region_by_expression": j},
                               "groups": {f"L{L}": v for L, v in per_layer.items()},
                               "probe": {f"L{L}": v for L, v in probe.items()}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps(probe[J], ensure_ascii=False))
    print(json.dumps({"h_region_by_expression": j}))


if __name__ == "__main__":
    main()
