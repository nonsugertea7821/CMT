"""仮説 h_charts_meet_at_ontology_top（どの領域も ontology.continuant に依存する。式: v_depend(syntax.domain, ontology.continuant)）を確かめる。
結果を見る前に、この説明と手順を登録した。

出どころ: #668（h_signature_all_charts の反証）。閉包の読みで、24 の領域すべてが届く語は any と ontology の 14 語だった。
開示（すでに見えていること）:
  閉包の読み（事実の引数を辿る）で、すべての領域が ontology.continuant に届くことは #668 で見えている。判定には使わない。
  直の読みの共通部分は空（n_I = 0）だったので、直に continuant を使う領域が全部ではないことも見えている。判定には使わない。
主の読み（まだ見ていないもの）: 型の鎖。
  語 w の祖先: 関係 extends と is の事実（第1引数 w、第2引数が親）を辿って届く語すべて。
  上位: 領域が ontology の語で、名の末尾が continuant か occurrent のもの（続く物と出来事の区別。式の to は continuant だけしか取れないため、区別の両側を数える）。
  領域 D（signature と ontology を除く）の語のうち、extends か is の事実を持つもの（型を持つ語）を数える。
測るもの:
  n_domain        数えた領域の数
  n_typed         型を持つ語の数（全領域）
  word_frac       型を持つ語のうち、祖先に上位を持つものの割合
  dom_all         型を持つ語がすべて上位に届く領域の割合
  dom_any         型を持つ語の一つでも上位に届く領域の割合
  cont_frac / occ_frac  型を持つ語のうち、祖先に continuant / occurrent を持つ割合（記述）
  direct_cont     continuant を直に引数に使う領域の割合（記述。#668 の直の読みと同じ辿り方）
  per_domain      領域ごとの n_typed・届く数（記述）
  miss            上位に届かない語を、届く根（祖先のうち親を持たない語）ごとに数えたもの（記述）
判定（事前に決める。主の読みで）:
  支持: dom_all = 1（どの領域の、型を持つどの語も上位に届く）。
  反証: word_frac < 0.9、または dom_any < 1（上位に一語も届かない領域がある）。
  そのほかは mixed。
行（sys_charts_meet_ontology_top.json）: "summary 要約": 上の数の量
使い方:
  python exp/experiments/sys_charts_meet_ontology_top.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_charts_meet_ontology_top.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]


def last(rel):
    return str(rel).split(".")[-1]


def main():
    import os
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    items = list(T.syntax_facts())
    home = {}
    for rel, xs in items:
        if last(rel) == "domain" and isinstance(xs[0], str):
            home.setdefault(xs[0], str(xs[1]))
    words = set(home)
    parent = collections.defaultdict(set)
    for rel, xs in items:
        if last(rel) in ("extends", "is") and len(xs) >= 2 and isinstance(xs[0], str) and isinstance(xs[1], str):
            parent[xs[0]].add(xs[1])
    top = {w for w in words if home[w] == "ontology" and last(w) in ("continuant", "occurrent")}
    cont = {w for w in top if last(w) == "continuant"}
    occ = top - cont

    def anc(w):
        seen, stack = set(), [w]
        while stack:
            for p in parent.get(stack.pop(), ()):
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    doms = sorted({d for d in home.values() if d not in ("signature", "ontology")})
    per, miss = {}, collections.Counter()
    n_typed = n_hit = n_cont = n_occ = 0
    for d in doms:
        ws = [w for w, h in home.items() if h == d and parent.get(w)]
        hit = 0
        for w in ws:
            a = anc(w)
            if a & top:
                hit += 1
            else:
                roots = sorted(x for x in a | {w} if not parent.get(x))
                miss[",".join(map(str, roots)) or str(w)] += 1
            n_cont += bool(a & cont)
            n_occ += bool(a & occ)
        per[d] = {"n_typed": len(ws), "hit": hit}
        n_typed += len(ws)
        n_hit += hit
    used = [d for d in doms if per[d]["n_typed"]]
    direct = collections.defaultdict(set)
    for rel, xs in items:
        if last(rel) == "domain":
            continue
        if isinstance(xs[0], str) and xs[0] in words:
            direct[home[xs[0]]] |= {x for x in xs[1:] if isinstance(x, str)}
    s = {"n_domain": len(doms), "n_domain_typed": len(used), "n_typed": n_typed,
         "word_frac": n_hit / n_typed if n_typed else 0.0,
         "dom_all": sum(per[d]["hit"] == per[d]["n_typed"] for d in used) / len(used) if used else 0.0,
         "dom_any": sum(per[d]["hit"] > 0 for d in used) / len(used) if used else 0.0,
         "cont_frac": n_cont / n_typed if n_typed else 0.0, "occ_frac": n_occ / n_typed if n_typed else 0.0,
         "direct_cont": sum(bool(direct[d] & cont) for d in doms) / len(doms) if doms else 0.0,
         "n_top": len(top)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"rev": rev, "rows": {"summary 要約": s}, "top": sorted(top), "per_domain": per,
           "miss": dict(miss.most_common(40)), "domains_untyped": [d for d in doms if not per[d]["n_typed"]]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
