"""体系そのものを数える: 概念の分化（上位から下位を作る）の操作に、規則性があるか。
結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_specific の C（洗練の対がある上下関係）33 組では、32 組が上位の式を1つだけ選んで端を狭め、
  段数は 25 組が 1 だった（洗練の対があるものを選んだ組なので、偏りがある）。利用者の直観:「発達・分化の操作自体に
  規則性がある」。ここでは、体系のすべての直接の上下関係（概念とその親）で、下位が自分で足した式を、操作の種類に分ける。

数え方（型検査器の法則の評価で導いた文 r_parent, r_concept, r_own, r_acc と、式の事実 of, position, with, at, neg, quant を使う）:
  辺: r_parent(c, p) で、c も p も r_concept のもの。
  c が自分で足した式 m'（r_own(c, m')）ごとに、p の式 m（r_acc(p, m)）と比べて、次の順で最初に当たる種類を付ける:
    negate      m' に neg がある
    narrow_end  ある m と動詞と位置が同じで、m に with があり、m' の with が m の with の真の子孫
    add_end     ある m と動詞と位置が同じで、m に with がなく、m' に with がある
    narrow_verb ある m と位置が同じで、m' の動詞が m の動詞の真の子孫（with は問わない）
    limit       ある m と動詞・位置・with が同じで、at か quant が m と違う
    new         p の式のどれとも、動詞が同じか上下にあり、かつ位置が同じ、ということがない（新しい特徴を足す）
    other       上のどれでもない
  narrow_end では、m' の with から m の with までの段数（r_parent をたどる最小）も数える（当てはまる m が複数なら最小）。
  辺の値: c の自前の式の数（n_own）、種類ごとの数、辺の型（自前の式の種類を、重複を除いて並べたもの。自前の式がなければ none）。
判定（3つを別々に読む。どれも登録した値で決め、選び直さない）:
  (a) 種類が少ない: other の式が、すべての自前の式の 5% 以下。
  (b) 一歩ずつ: 自前の式がある辺のうち、自前の式が 1 つの辺が 80% 以上。
  (c) 端を狭めるのが典型: narrow_end が、すべての自前の式の 50% 以上。そのうち段数 1 が 50% 以上。
  3 つとも満たせば「分化の操作に規則性がある（式1つ・端を1段）」とする。満たさないものは、その数を書いて外れとする。
登録の前に分かっていること: sys_specific の C の数（上）。すべての辺の数・種類の数は見ていない。
  見込み: (a) は満たす。(b) は満たす。(c) は満たさないかもしれない（new が多いかもしれない）。

行（sys_differentiation.json）:
  "edge c→p":     n_own, negate, narrow_end, add_end, narrow_verb, limit, new, other, type, min_hop（narrow_end の段数の最小）
  "summary 要約":  辺の数、自前の式の数、種類ごとの式の数、自前の式が1つの辺の数、narrow_end で段数 1 の式の数、辺の型ごとの数

使い方:
  python exp/experiments/sys_differentiation.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
KINDS = ("negate", "narrow_end", "add_end", "narrow_verb", "limit", "new", "other")


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rel = lambda r: F.by.get(r, set())

    def two(r):
        d = collections.defaultdict(set)
        for t in rel(r):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    parent, own, acc, anc = two("r_parent"), two("r_own"), two("r_acc"), two("r_ancestor")
    of, pos, with_, at, quant = two("of"), two("position"), two("with"), two("at"), two("quant")
    neg = {t[0] for t in rel("neg")}
    concept = {t[0] for t in rel("r_concept")}
    one = lambda d, m: next(iter(d[m])) if len(d[m]) == 1 else (frozenset(d[m]) if d[m] else None)
    below = lambda a, b: a != b and b in anc[a]   # a は b の真の子孫

    def hop(a, b):
        seen, front, d = {a}, {a}, 0
        while front:
            if b in front:
                return d
            front = {q for x in front for q in parent[x]} - seen
            seen |= front
            d += 1
        return None

    def kind(m1, ms):
        v1, p1, w1 = one(of, m1), one(pos, m1), one(with_, m1)
        if m1 in neg:
            return "negate", None
        same = [m for m in ms if one(of, m) == v1 and one(pos, m) == p1]
        hs = [hop(w1, one(with_, m)) for m in same if one(with_, m) and w1 and isinstance(w1, str)
              and isinstance(one(with_, m), str) and below(w1, one(with_, m))]
        if hs:
            return "narrow_end", min(h for h in hs if h is not None) if any(h is not None for h in hs) else None
        if any(not with_[m] and with_[m1] for m in same):
            return "add_end", None
        if any(one(pos, m) == p1 and isinstance(v1, str) and isinstance(one(of, m), str) and below(v1, one(of, m)) for m in ms):
            return "narrow_verb", None
        if any(with_[m] == with_[m1] and (at[m] != at[m1] or quant[m] != quant[m1]) for m in same):
            return "limit", None
        rel_v = lambda a, b: isinstance(a, str) and isinstance(b, str) and (a == b or below(a, b) or below(b, a))
        if not any(one(pos, m) == p1 and rel_v(v1, one(of, m)) for m in ms):
            return "new", None
        return "other", None

    rows = {}
    for c in sorted(concept):
        for p in sorted(parent[c] & concept):
            r = {k: 0 for k in KINDS} | {"n_own": len(own[c])}
            hops = []
            for m1 in sorted(own[c]):
                k, h = kind(m1, acc[p])
                r[k] += 1
                if h is not None:
                    hops.append(h)
            r["type"] = "+".join(k for k in KINDS if r[k]) or "none"
            r["min_hop"] = min(hops) if hops else None
            r["n_hop1"] = sum(1 for h in hops if h == 1)
            rows[f"edge {c}→{p}"] = r
    es = list(rows.values())
    summ = {"edges": len(es), "own_formulas": sum(r["n_own"] for r in es)}
    for k in KINDS:
        summ[k] = sum(r[k] for r in es)
    summ["edges_with_own"] = sum(1 for r in es if r["n_own"])
    summ["edges_one_own"] = sum(1 for r in es if r["n_own"] == 1)
    summ["narrow_end_hop1"] = sum(r["n_hop1"] for r in es)
    summ["types"] = dict(collections.Counter(r["type"] for r in es).most_common())
    rows["summary 要約"] = summ
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_differentiation.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
