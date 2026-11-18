"""体系そのものを数える: 法則 specific を含意（r_has）で読んだときに残る 9 件の違反は、式の上で、正しい上下関係と区別できるか。
結果を見る前に、この説明と手順を登録した。

背景（会話）: 法則 monotone は含意（r_has）で読むようにした。specific の specific_missing も r_acc を r_has に替えると、
  9 件の違反が残る（syntax.position→opposite, exp.backlog_item→std.hypothesis, subj.hour/days_overdue→money,
  subj.plan/runtime.run/subj.attendance→verb_ref, exp.control_preservation→context_following, subj.height→age）。
  どれも機械的に下へ移すと違反は 0 になる。つまり今の法則はこれらを区別できず、区別は名前にしかない。
  式の中に区別の手がかりがあれば、それを法則にする。なければ、名前にしかない区別を式に移す話に進む。
会話で出した案からの訂正（登録の前）: 案の 1「上の概念が持っていて下の概念に足りない式」は、違反の定義（r_has で足りない式がない）から
  いつも空になる。代わりに、下の概念が含意でだけ持つ上の概念の式（E）と、それを含意する下の概念の式（洗練の対）を見る。

数え方（規則で決める。型検査器の法則の評価で導いた文 r_acc, r_own, r_has, r_entail, r_same_slot, r_candidate, with を使う）:
  V（違反の組）: r_candidate(x, y) で、r_acc(y, m) のすべての m に r_has(x, m) があり、r_acc(x, m) がない m が1つ以上あるもの。
     E = { m : r_acc(y, m), r_acc(x, m) がない }。洗練の対 L = { (m', m) : m ∈ E, r_acc(x, m'), r_entail(m', m) }。
  C（比べる組）: y が x の祖先（r_ancestor(x, y)）で、どちらも概念（r_concept）で、
     r_own(x, m'), r_acc(y, m), r_entail(m', m) となる対が1つ以上あるもの（今の体系が上下関係で洗練を書いている組）。
     L = その対の全部。E = L の m の集まり。
  行の値（組ごと。0 か 1、hops と n だけ数）:
    defined_by_refined  y が自分で足した式（r_own(y, ·)）が、どれも E にある（y は、x が洗練した位置だけで決まる）
    independent_slot    L の m のどれかについて、x が、同じ動詞の同じ位置（r_same_slot(m'', m)）に、with の終点が m の終点と
                        上下関係にない（どちらも相手の祖先でも同じでもない）式 m'' を r_acc で持つ（会話の案の 2）
    same_domain         x と y が同じ領域
    y_has_concept_child y の下に、概念が1つ以上ある（y は今、上位として使われている）
    hops                L の対で、m' の with の終点から m の with の終点までの上下の段数の最小
    n                   E の数
判定（V と C の比べ方）: 0/1 の値のうち、V の 9 組すべてで 1、C の組の 10% 以下で 1 のものがあれば、それを法則の候補とする。
  逆（V のすべてで 0、C の 90% 以上で 1）も候補とする。どちらもなければ「今の式では区別できない」と結論する。
登録の前に分かっていること: 違反の 9 組（上）。C の組の数、どの値も見ていない。見込み: independent_slot は V でも少ない
  （V では x が m を含意する式を持つので、同じ位置の別の式は珍しいはず）。区別できない、という結論になりそう。

行（sys_specific.json）:
  "V x→y" / "C x→y":  defined_by_refined, independent_slot, same_domain, y_has_concept_child, hops, n
  "summary 要約":      V と C それぞれの組の数と、値ごとの 1 の数

使い方:
  python exp/experiments/sys_specific.py
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
FLAGS = ("defined_by_refined", "independent_slot", "same_domain", "y_has_concept_child")


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
        hops = [h for m1, m in L for u in with_[m1] for v in with_[m] if (h := up(u, v)) is not None]
        ind = any(m2 not in ent or m not in ent[m2]
                  for _, m in L for m2 in acc[x] if m2 in slot[m] and m2 != m
                  if with_[m2] and with_[m] and not any(related(u, v) for u in with_[m2] for v in with_[m]))
        return {"defined_by_refined": int(bool(own[y]) and own[y] <= E),
                "independent_slot": int(ind),
                "same_domain": int(T.domain(x) == T.domain(y)),
                "y_has_concept_child": int(any(c in concept for c in children[y])),
                "hops": min(hops) if hops else None,
                "n": len(E)}

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
    (OUT / "sys_specific.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
