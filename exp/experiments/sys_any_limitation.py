"""仮説 h_any_not_vacuous（依存する(何でもを端に持つ限定, 位置の指定)）を確かめる: 端に any を持つ限定
{of: [v, pos], with: any} を満たす概念が、位置の指定 [v, pos] で決まるか（空でも全体でもなく、of に応じて決まるか）。

背景（会話）: signature をアフィンに映すと、any は全体・ゼロの条件に当たる。限定の with の any は存在の数量化
  （「pos に何かの v を持つ」）と読む（claims の解決先の調べ）。それが空虚でないなら、any を端に持つ限定の中身は
  位置の指定（of）だけから来る。
操作: 体系のファイルを変えない。読み込んだ体系に、測るための見本の種類（probe）をメモリの上で足して、法則を回す。

数え方（引数 after）:
  slots      体系の限定の項に現れる (動詞, 位置) の組（of と position の事実から）
  probe p    slot (v, pos) ごとに、lang.probe_<i>: {extends: ontology.kind, mod: {of: [v, pos], with: any}} を足す
  C          比べる概念: T.is_concept のノードと最上位（tc.TOPS）。probe は除く
  sat(p)     C のうち、p の項を r_has に持つもの
  ideal(p)   C のうち、of が v で position が pos の項を r_has に持つもの（端は何でもよい）
  probes           probe の数
  ideal_nonempty   ideal(p) が空でない probe の数
  sat_nonempty     sat(p) が空でない probe の数
  match            ideal(p) が空でなく、sat(p) = ideal(p) の probe の数
  distinct_sat     ideal(p) が空でない probe の、sat(p) の異なり数
  any_ancestor     r_ancestor(w, any) の事実の数（entail_by_with が端 w から any へ含意を運ぶ足場）
  actual_terms     体系にもとからある、with が any の限定の項の数
  actual_sat       それらの項を r_has に持つ C の概念の数（延べ）
判定: errors 0、ec_errors 0 のもとで、ideal_nonempty が 0 でなく、match = ideal_nonempty なら支持（v_support）。
  match < ideal_nonempty なら反証（v_contradict）。ideal_nonempty が 0 なら、問えないので外れとし、状態は変えない。
  errors か ec_errors が出たら外れとする。distinct_sat、any_ancestor、actual_* は記述で、判定に使わない。
登録の前に分かっていること（下調べ。開示する）:
  - 体系にもとからある with: any の限定は syntax.deep_kind の一つだけで、それを満たすのは専用の法則 has_by_depth
    （of が v_above、position が from、at が count > 2 と決め打ち）による。
  - entail_by_with は r_ancestor(w3, w4) を要るが、any はノードでなく、祖先の鎖に入らない（見込み any_ancestor 0）。
  - この手順の素案を、記録しない下書きで一度走らせた。そこでは probe 87、sat_nonempty 0 だった。
    なので、この実験は結果をほぼ知った上での確かめで、判定の基準はその前に決めたものから変えていない。
見込み: errors 0、ec_errors 0。sat_nonempty 0、match 0 で反証。any_ancestor 0。

行（sys_any_limitation_after.json）:
  "summary 要約": 上の数
  "probe v@pos":  ideal（数）, sat（数）, match（0 か 1）。ideal が空でないものだけ

使い方:
  python exp/experiments/sys_any_limitation.py after
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "exp/src")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    n_err = len(tc.errors)
    errs = list(tc.errors)
    with contextlib.redirect_stdout(io.StringIO()):
        import exp_check
        del tc.errors[:]
        try:
            exp_check.build()
        except SystemExit:
            pass
    ec_err = len(tc.errors)
    errs += list(tc.errors)

    F0 = tc.Facts(T.syntax_facts())
    pos0 = collections.defaultdict(set)
    for t in F0.by.get("position", ()):
        pos0[t[0]].add(t[1])
    slots = sorted({(t[1], p) for t in F0.by.get("of", ()) for p in pos0[t[0]]})
    with_any = {t[0] for t in F0.by.get("with", ()) if t[1] == "any"}
    probes = {}
    for i, (v, p) in enumerate(slots):
        nid = f"lang.probe_{i}"
        T.N[nid] = {"display": f"probe {i}", "extends": "ontology.kind", "mod": {"of": [v, p], "with": "any"}}
        probes[nid] = (v, p)

    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    mods, has = collections.defaultdict(set), collections.defaultdict(set)
    for t in F.by.get("mod", ()):
        mods[t[0]].add(t[1])
    for t in F.by.get("r_has", ()):
        if len(t) == 2:
            has[t[0]].add(t[1])
    of = {t[0]: t[1] for t in F.by.get("of", ())}
    pos = collections.defaultdict(set)
    for t in F.by.get("position", ()):
        pos[t[0]].add(t[1])
    C = sorted(n for n in T.N if (T.is_concept(n) or n in tc.TOPS) and n not in probes)

    rows, ideal_ne, sat_ne, match, sats = {}, 0, 0, 0, set()
    for nid, (v, p) in probes.items():
        term = next(iter(mods[nid]))
        sat = frozenset(x for x in C if term in has[x])
        ideal = frozenset(x for x in C if any(of.get(m) == v and p in pos[m] for m in has[x]))
        sat_ne += bool(sat)
        if ideal:
            ideal_ne += 1
            match += sat == ideal
            sats.add(sat)
            rows[f"probe {v}@{p}"] = {"ideal": len(ideal), "sat": len(sat), "match": int(sat == ideal)}
    actual = with_any
    summ = {"errors": n_err, "ec_errors": ec_err, "slots": len(slots), "probes": len(probes),
            "ideal_nonempty": ideal_ne, "sat_nonempty": sat_ne, "match": match, "distinct_sat": len(sats),
            "any_ancestor": sum(1 for t in F.by.get("r_ancestor", ()) if len(t) == 2 and t[1] == "any"),
            "actual_terms": len(actual), "actual_sat": sum(1 for x in C for m in actual if m in has[x])}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_any_limitation_{label}.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, r in list(rows.items())[:15]:
        print(k, r)
    for e in errs[:10]:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] == ["after"]
    main(sys.argv[1])
