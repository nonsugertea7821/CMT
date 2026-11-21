"""仮説 h_law_without_domain（法則で決まる概念の分類は、領域に依存しない）を確かめる。
結果を見る前に、この説明と手順を登録した。

式: v_not_depend(concept_by_law, syntax.domain)。concept_by_law は法則（law_rule）で決まる分類で、
  ここでは法則が導く r_concept と r_verb の項の集合で測る。
系列: sys_concept_kind_pair（h_concept_kind_excludes_verb・h_concept_kind_frame_free）と同じく、
  型検査が組んだ事実に法則を当てて、導いた関係を数える。
変種（体系のファイルは書き換えない。T.syntax_facts() が出す事実の列だけを変えてから法則を当てる）:
  L   そのまま。
  D   関係 domain（節点 → 領域）の事実をすべて除く。
  C   関係 domain の事実の領域を、すべて一つの値 __one__ に置き換える（領域を一つに潰す）。
  法則 sees・unique_in_domain・visible_self・layered は domain を前提に持ち、world_rule は law_domain を前提に持つ。
  law_domain は変えない（開示）。
測るもの（変種ごと）:
  n_domain    domain の事実の数
  n_concept   r_concept の項の数
  n_verb      r_verb の項の数
  same_concept  r_concept の項の集合が L と同じなら 1
  same_verb     r_verb の項の集合が L と同じなら 1
  changed_rel   L と項の集合が違う r_ の関係の名前と、L だけ・変種だけの項の数（記述。どこに領域が効くかの観察）
判定（事前に決める）:
  支持: D と C のどちらでも same_concept 1 かつ same_verb 1。
  反証: D か C のどちらかで same_concept 0 か same_verb 0。
  （法則の評価が例外で止まったら、その変種は未決とし、状態は変えない。）
見込み: 概念の分類（concept_kind・verb_inherit）は domain を前提に持たないので、支持の見込み。
  ただし分類の前提にある関係が、domain を前提に持つ法則の結論から導かれていれば、変わりうる。
行（sys_law_without_domain.json）:
  "variant <v>": 上の量（v は L, D, C）
  "summary 要約": same_concept_<V>, same_verb_<V>（V は D, C）
使い方:
  python exp/experiments/sys_law_without_domain.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_law_without_domain.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]


def last(rel):
    return str(rel).split(".")[-1]


def derive(tc, T, O, variant):
    items = []
    for rel, xs in T.syntax_facts():
        if last(rel) == "domain":
            if variant == "D":
                continue
            if variant == "C":
                xs = (xs[0], "__one__") + tuple(xs[2:])
        items.append((rel, xs))
    n_domain = sum(1 for rel, _ in items if last(rel) == "domain")
    F = tc.Facts(items)
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rels = {}
    for k in F.by:
        if last(k).startswith("r_"):
            rels.setdefault(last(k), set()).update(map(str, F.by[k]))
    return n_domain, rels


def main():
    import os
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    res = {v: derive(tc, T, O, v) for v in "LDC"}
    base = res["L"][1]
    rows, summ = {}, {}
    for v, (nd, rels) in res.items():
        row = {"n_domain": nd, "n_concept": len(rels.get("r_concept", ())), "n_verb": len(rels.get("r_verb", ()))}
        if v != "L":
            row["same_concept"] = int(rels.get("r_concept", set()) == base.get("r_concept", set()))
            row["same_verb"] = int(rels.get("r_verb", set()) == base.get("r_verb", set()))
            row["changed_rel"] = {k: {"only_L": len(base.get(k, set()) - rels.get(k, set())),
                                      "only_v": len(rels.get(k, set()) - base.get(k, set()))}
                                  for k in sorted(set(base) | set(rels)) if base.get(k, set()) != rels.get(k, set())}
            summ |= {f"same_concept_{v}": row["same_concept"], f"same_verb_{v}": row["same_verb"]}
        rows[f"variant {v}"] = row
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, r in rows.items():
        print(k, json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
