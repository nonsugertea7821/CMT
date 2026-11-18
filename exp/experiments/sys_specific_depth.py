"""体系そのものを数える: 法則 specific を含意（r_has）で読んだときに残る 9 件の違反（V）は、上の概念 y の定義が
「上の方の一般的な端」だけで書かれていることで、正しい上下関係（C）と区別できるか。
結果を見る前に、この説明と手順を登録した。ただし、下に書くとおり、同じ V と C を一度見たあとの登録である。

背景: sys_specific（4cefbcd 登録、98983d8 記録）は、登録した4つの値のどれでも V と C を区別できなかった。
  そのあと（登録せずに）9 組を開いて見たところ、x はどれも「y の自前の式の端を 1 か所だけ狭めたもの」で、
  この形は C の 32/33 組も同じだった。さらに、y の自前の式（r_own(y, ·)）の with の終点の祖先の数を数えると、
  V では 0〜2 が 8、3 以上が 1、C では 0〜2 が 3、3 以上が 30 だった（式の数で数えたもの。組の数ではない）。
  閾値 2 は、この数を見てから選んだ。だからこの観察は、同じデータでの確かめで、新しいデータでの検証ではない。
  ここで登録するのは、見た数を組ごとの値に直したときに、どこまで分かれるかを、決めた判定で読むことである。

数え方（V, C の組と、r_acc, r_own, r_entail, with は sys_specific と同じ。組の作り方はそのまま使う）:
  深さ(e)  = e の祖先の数（型検査器の T.ancestors(e) の数）
  行の値（組ごと）:
    y_def_shallow   y の自前の式の with の終点がすべて、深さ 2 以下（y の自前の式がなければ 0）
    y_def_shallow1  同じく、深さ 1 以下（閾値を変えたときの確かめ）
    y_def_shallow3  同じく、深さ 3 以下（同上）
    y_def_depth     y の自前の式の with の終点の深さの最大（数）
判定: sys_specific と同じ。y_def_shallow が V の 9 組すべてで 1、C の 10% 以下で 1 なら、法則の候補とする。
  それに届かず、V の 80% 以上（8 組以上）で 1、C の 10% 以下で 1 なら「傾向がある（法則にはしない）」とし、
  V で 0 の組を書き出す。どちらでもなければ「区別できない」とする。閾値 1 と 3 の値は、判定に使わず、併せて書く。
登録の前に分かっていること: 上の式の数（組ごとの値は見ていない）。V の深い端 1 つは
  control_preservation→context_following の y（端 exp.case）のものと見込む。見込み: 「傾向がある」になる。

行（sys_specific_depth.json）:
  "V x→y" / "C x→y":  y_def_shallow, y_def_shallow1, y_def_shallow3, y_def_depth
  "summary 要約":      V と C それぞれの組の数と、0/1 の値ごとの 1 の数

使い方:
  python exp/experiments/sys_specific_depth.py
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
FLAGS = ("y_def_shallow", "y_def_shallow1", "y_def_shallow3")


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rel = lambda r: F.by.get(r, set())
    acc, own, has, ent, slot, with_ = (collections.defaultdict(set) for _ in range(6))
    for a, b in rel("r_acc"):
        acc[a].add(b)
    for a, b in rel("r_own"):
        own[a].add(b)
    for a, b in rel("r_has"):
        has[a].add(b)
    for a, b in rel("r_entail"):
        ent[a].add(b)
    for a, b in rel("r_same_slot"):
        slot[a].add(b)
    for a, b in rel("with"):
        with_[a].add(b)
    concept = {a for (a,) in rel("r_concept")}
    anc = collections.defaultdict(set)
    for a, b in rel("r_ancestor"):
        anc[a].add(b)
    parent = collections.defaultdict(set)
    for a, b in rel("r_parent"):
        parent[a].add(b)
    children = collections.defaultdict(set)
    for a, bs in parent.items():
        for b in bs:
            children[b].add(a)

    def up(a, b):
        """a から上位をたどって b に着くまでの段数（着かなければ None）。"""
        seen, frontier, d = {a}, {a}, 0
        while frontier:
            if b in frontier:
                return d
            frontier = {p for x in frontier for p in parent[x]} - seen
            seen |= frontier
            d += 1
        return None

    def related(u, v):
        return u == v or u in anc[v] or v in anc[u]

    def row(x, y, E, L):
        ds = [len(T.ancestors(e)) for m in own[y] for e in with_[m]]
        r = {f"y_def_shallow{s}": int(bool(ds) and max(ds) <= t) for s, t in (("", 2), ("1", 1), ("3", 3))}
        return r | {"y_def_depth": max(ds) if ds else None}

    rows = {}
    for x, y in sorted(rel("r_candidate")):
        if acc[y] <= has[x] and not acc[y] <= acc[x]:
            E = acc[y] - acc[x]
            rows[f"V {x}→{y}"] = row(x, y, E, {(m1, m) for m in E for m1 in acc[x] if m in ent[m1]})
    for x in sorted(concept):
        for y in sorted(anc[x] & concept):
            L = {(m1, m) for m1 in own[x] for m in acc[y] if m in ent[m1]}
            if L:
                rows[f"C {x}→{y}"] = row(x, y, {m for _, m in L}, L)
    summ = {}
    for g in "VC":
        rs = [v for k, v in rows.items() if k[0] == g]
        summ[f"{g}_pairs"] = len(rs)
        for f in FLAGS:
            summ[f"{g}_{f}"] = sum(r[f] for r in rs)
    rows["summary 要約"] = summ
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sys_specific_depth.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
