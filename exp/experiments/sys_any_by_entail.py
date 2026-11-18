"""仮説 h_any_by_entail（依存する(何でもを端に持つ限定, 上位の順序)）を確かめる: 限定の端 w を上位の順序で any の
下に置く法則を足すと、端に any を持つ限定 {of: [v, pos], with: any} を満たす概念が「pos に何かの v を持つ概念」と
一致するか。結果を見る前に、この説明と手順を登録した。

背景: h_any_not_vacuous の反証（#155, sys_any_limitation_after）で、どの slot でも any の限定を満たす概念は 0 だった。
  含意を運ぶ entail_by_with は r_ancestor(w3, w4) を要るが、any は祖先の鎖の外にある。
操作（after の前に、体系に一つの法則を足す。before は足す前の main）:
  syntax.yaml に法則 any_above_end を足す: with(var1, var2) かつ same(var2, any) でない ならば r_ancestor(var2, any)。
  （限定の端 w を、上位の順序で any の下に置く。v_above の事実も above_by_ancestor から増える）
  法則のほかは変えない。足した後に tc か ec が通らなければ、法則は足したままにして、外れとして記録する。

数え方（引数 before / after。sys_any_limitation と同じ見本の種類 probe を、読み込んだ体系にメモリの上で足す）:
  slots, probes   体系の限定の項に現れる (動詞, 位置) の組と、組ごとの probe {of: [v, pos], with: any}
  C               T.is_concept のノードと最上位（tc.TOPS）。probe は除く
  sat(p)          C のうち、p の項を r_has に持つもの
  ideal(p)        C のうち、of が v、position が pos、with が any でない項を r_has に持つもの
                  （sys_any_limitation の ideal と違い、any の項を除く。後では any の項が含意で増えるので、循環を避ける）
  ideal_nonempty, sat_nonempty, match（ideal が空でなく sat = ideal）, distinct_sat（ideal が空でない probe の sat の異なり数）
  any_ancestor    r_ancestor(w, any) の事実の数
  副作用（記述）: above（above の事実の数）, deep（deep_kind の項を r_has に持つ C の数）, candidate（r_candidate の数）
判定（after で）: errors 0、ec_errors 0 のもとで、ideal_nonempty が 0 でなく match = ideal_nonempty なら支持（v_support）。
  match < ideal_nonempty なら反証（v_contradict）。ideal_nonempty が 0、または errors か ec_errors が 0 でなければ外れとし、
  状態は変えない。before は比べるための記録で、判定に使わない。副作用は記述で、判定に使わない。
下調べ（開示）: この手順は走らせていない。any は法則の中で定数として書ける（root_kind が same(var1, any) を使う）。
  r_ancestor は above・deep_end（count > 2）・acyclic・specific_candidate などの前提に使われるので、副作用が出うる。
見込み: before は match 0（sys_any_limitation と同じ）。after は match = ideal_nonempty で支持。ただし above が増え、
  deep_end や deep_kind の数え方が変わって、tc か ec が通らない見込みもある（そのときは外れ）。

行（sys_any_by_entail_<label>.json）:
  "summary 要約": 上の数
  "probe v@pos":  ideal（数）, sat（数）, match（0 か 1）。ideal が空でないものだけ

訂正（after の後）: probe の mod を、リストでなく辞書 {of: ..., with: any} のまま足していた。tc.build は読み込みのときに
  mod を [辞書] に直すが、build の後に足した probe は直らず、syntax_facts が辞書の鍵を回して、項が "of" と "with" という
  語になっていた。なので before と after の probe の数（sat, match）は、意図した限定を測っていない。any_ancestor、above、
  deep、candidate、errors、ec_errors は probe に依らないので、そのまま有効。
  直し: probe の mod を [{of: [v, pos], with: any}] にする。直した手順で before_fix（法則を足す前の syntax.yaml に
  一時的に戻して走らせ、戻す）と after_fix を取る。判定は after_fix で、上の判定の基準をそのまま使う。
  同じ誤りは sys_any_limitation（#155、h_any_not_vacuous の反証）にもある。before_fix はその確かめを兼ねる。

使い方:
  python exp/experiments/sys_any_by_entail.py before       （法則を足す前）
  python exp/experiments/sys_any_by_entail.py after        （法則を足した後）
  python exp/experiments/sys_any_by_entail.py before_fix   （訂正: 法則を足す前）
  python exp/experiments/sys_any_by_entail.py after_fix    （訂正: 法則を足した後）
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
    probes = {}
    for i, (v, p) in enumerate(slots):
        nid = f"lang.probe_{i}"
        T.N[nid] = {"display": f"probe {i}", "extends": "ontology.kind", "mod": ({"of": [v, p], "with": "any"} if label in ("before", "after")
                                                                    else [{"of": [v, p], "with": "any"}])}
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
    pos, wth = collections.defaultdict(set), collections.defaultdict(set)
    for t in F.by.get("position", ()):
        pos[t[0]].add(t[1])
    for t in F.by.get("with", ()):
        wth[t[0]].add(t[1])
    C = sorted(n for n in T.N if (T.is_concept(n) or n in tc.TOPS) and n not in probes)

    rows, ideal_ne, sat_ne, match, sats = {}, 0, 0, 0, set()
    for nid, (v, p) in probes.items():
        term = next(iter(mods[nid]))
        sat = frozenset(x for x in C if term in has[x])
        ideal = frozenset(x for x in C if any(of.get(m) == v and p in pos[m] and "any" not in wth[m] for m in has[x]))
        sat_ne += bool(sat)
        if ideal:
            ideal_ne += 1
            match += sat == ideal
            sats.add(sat)
            rows[f"probe {v}@{p}"] = {"ideal": len(ideal), "sat": len(sat), "match": int(sat == ideal)}
    deep = next(iter(mods.get("syntax.deep_kind", ())), None)
    summ = {"errors": n_err, "ec_errors": ec_err, "slots": len(slots), "probes": len(probes),
            "ideal_nonempty": ideal_ne, "sat_nonempty": sat_ne, "match": match, "distinct_sat": len(sats),
            "any_ancestor": sum(1 for t in F.by.get("r_ancestor", ()) if len(t) == 2 and t[1] == "any"),
            "above": sum(1 for t in F.by.get("above", ()) if len(t) == 2),
            "deep": sum(1 for x in C if deep and deep in has[x]),
            "candidate": sum(1 for t in F.by.get("r_candidate", ()) if len(t) == 2)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_any_by_entail_{label}.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, r in list(rows.items())[:15]:
        print(k, r)
    for e in errs[:10]:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"], ["before_fix"], ["after_fix"])
    main(sys.argv[1])
