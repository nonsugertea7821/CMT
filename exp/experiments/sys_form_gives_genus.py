"""仮説 h_form_gives_genus（式: v_depend(syntax.extends, syntax.form)。上位の型は form からも導かれる）を確かめる。
結果を見る前に、この説明と手順を登録した。

出どころ: #675。form: [v, k] で定めた語 w に、動詞 v の端 k の型 t を上位として足すと、型の鎖が閉じた。
問い: その「form からの上位」を、検査器はすでに導いているか（検査が与えるものが体系にあるか）。
対象: form の事実 (w, v) と position の事実 (w, k) を持ち、v の端 k の型 t（関係 from か to の事実 (v, t)）が any でない語 w。
検査器の上位の関係: 法則を評価した後の事実の集まり F.by から、above・r_ancestor・r_parent・r_kind_up を読む。
  主: above（ontology の v_above が holds で置く関係。「上位に持つ」）。ほかは記述。
  各関係 R について、R の推移閉包で w から t に届く対象の割合 cover_R を数える（w を第1引数とする向き）。
  向きの読み違いに備え、逆向き（t から w）の割合 cover_R_rev も記述として数える。
判定（事前に決める。主の関係 above で）:
  支持: cover_above >= 0.9。
  反証: cover_above <= 0.1。
  そのほかは mixed。
行（sys_form_gives_genus.json）: "summary 要約"
使い方:
  python exp/experiments/sys_form_gives_genus.py
"""
import collections
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_form_gives_genus.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
RELS = ["above", "r_ancestor", "r_parent", "r_kind_up"]


def last(x):
    return str(x).split(".")[-1]


def main():
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
        items = list(T.syntax_facts())
        F = tc.Facts(items)
        tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    form, pos, slot = {}, {}, collections.defaultdict(dict)
    for rel, xs in items:
        r = last(rel)
        if len(xs) < 2 or not all(isinstance(x, str) for x in xs[:2]):
            continue
        if r == "form":
            form[xs[0]] = xs[1]
        elif r == "position":
            pos[xs[0]] = xs[1]
        elif r in ("from", "to"):
            slot[xs[0]][r] = xs[1]
    targets = {}
    for w, v in form.items():
        t = slot.get(v, {}).get(pos.get(w))
        if t and t != "any":
            targets[w] = t

    def edges(R):
        e = collections.defaultdict(set)
        for xs in F.by.get(R, ()):
            xs = tuple(xs)
            if len(xs) >= 2 and isinstance(xs[0], str) and isinstance(xs[1], str):
                e[xs[0]].add(xs[1])
        return e

    def reach(e, a, b):
        seen, stack = {a}, [a]
        while stack:
            for y in e.get(stack.pop(), ()):
                if y == b:
                    return True
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return False

    s = {"n_target": len(targets)}
    per = {}
    for R in RELS:
        e = edges(R)
        fw = [w for w, t in targets.items() if reach(e, w, t)]
        bw = [w for w, t in targets.items() if reach(e, t, w)]
        s[f"cover_{R}"] = len(fw) / len(targets) if targets else 0.0
        s[f"cover_{R}_rev"] = len(bw) / len(targets) if targets else 0.0
        s[f"n_pairs_{R}"] = sum(len(v) for v in e.values())
        per[R] = {"hit": sorted(fw), "rev_hit": sorted(bw)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"rev": rev, "rows": {"summary 要約": s}, "targets": targets, "per_relation": per}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
