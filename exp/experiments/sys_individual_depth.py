"""仮説 h_individual_depth（依存する(個体の深さ, 種類)）を確かめる: 個体の深さを、個体が属する種類から式で数えると、
「浅い端だけで定義される」の法則が個体の端にも及び、スクリプトの数えと一致するか。結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_count_atom で、浅さを法則（r_deep_end, r_shallow）で書いた。法則の r_ancestor は種類（ノード）にだけ祖先を導き、
  個体には導かない。そこで個体の端は法則でもスクリプトでも数えないことにし（前提 exists）、個体の深さは仮説として残した。
  種類の深さは祖先（r_ancestor）の数。個体はどの種類でもないので、個体の祖先にあたるのは、個体が属する種類とその上位
  （r_ind_kind, 「個体の種類か、その上位である」）。個体の深さをその数と読む（種類の深さ + 1）。r_ind_kind は is から導くので、
  この読みでは個体の深さは種類から決まる（仮説の中身）。
操作（この手順の登録のあと、測る前に行う。cscl/library/syntax/syntax.yaml だけを変える。コメントは書かない）:
  法則 2 つを足す。今ある deep_end と shallow_ends は変えない（ノードの端の扱いは変わらない）:
       deep_end_ind: {is: law_rule, display: 自前の式の端に、属する種類が3つ以上ある個体があれば、深い端を持つ}
       shallow_ends_ind: {is: law_rule, display: 自前の式の端に個体があり、深い端を持たなければ、浅い端だけで定義される}
       - {is: v_assume, from: deep_end_ind, to: {is: r_own, from: var1, to: var2}}
       - {is: v_assume, from: deep_end_ind, to: {is: with, from: var2, to: var3}}
       - {is: v_assume, from: deep_end_ind, to: {is: r_ind_kind, from: var3, to: var4, at: {count: {gt: 2}}}}
       - {is: v_derive, from: deep_end_ind, to: {is: r_deep_end, from: var1}}
       - {is: v_assume, from: shallow_ends_ind, to: {is: r_own, from: var1, to: var2}}
       - {is: v_assume, from: shallow_ends_ind, to: {is: with, from: var2, to: var3}}
       - {is: v_assume, from: shallow_ends_ind, to: {is: r_ind_kind, from: var3, to: var4}}
       - {is: v_assume, from: shallow_ends_ind, to: {is: r_deep_end, from: var1, neg: true}}
       - {is: v_derive, from: shallow_ends_ind, to: {is: r_shallow, from: var1}}

数え方（引数 before / after）:
  errors       型検査の誤りの数
  ec_errors    exp の検査（exp/src/exp_check.py）の誤りの数
  law_shallow  r_shallow が導かれた概念の数
  script       スクリプトで浅い概念の数: 自前の式（r_own）の with の終点の深さの最大が 2 以下。終点の深さは、ノードなら
               T.ancestors の数、個体なら 1 + その種類（T.I）の T.ancestors の数（属する種類とその上位の数）。法則の事実を使わない
  mismatch     law_shallow と script の対称差の大きさ
  ind          個体の終点を持つ概念の数
  uncovered    ind のうち、r_shallow も r_deep_end も導かれない概念の数
  changed      新しい法則を除いた規則（deep_end と shallow_ends も除く）で閉じた事実を before と比べ、違う関係の数
  extra        新しい法則を入れて閉じた事実のうち、入れないときになく、r_deep_end と r_shallow でもない文の数
  shifted      before と比べて r_shallow に入ったか出た概念の数（記述。判定に使わない）
  v_shallow    違反の組（sys_kind_ref と同じ数え方）のうち、上の側（y）が r_shallow に入る組の数（記述。判定に使わない）
判定: after で errors 0、ec_errors 0 のもとで、mismatch 0、uncovered 0、changed 0、extra 0 を満たせば支持（v_support）。
  errors か ec_errors が出たら、内容を書いて外れとし、状態は変えない（訂正するかは別に決める）。
  errors と ec_errors が 0 で、mismatch か uncovered が 0 でなければ反証（v_contradict）: 種類から数えた個体の深さでは、
  法則とスクリプトの浅さが合わないか、個体の端の概念が分類されない。changed か extra が 0 でなければ、内容を書いて外れとする。
登録の前に分かっていること（下調べ。法則を変えずに今の体系を見た）:
  - 個体の終点を持つ概念は 14、終点の個体は 13（subj の曜日・地域・品物、exp の選択肢と this_design）。
  - その 13 の個体で、r_ind_kind の終点の集まりは、種類とその祖先（r_ancestor）の集まりに等しい。数は 2（honshu, tomato, shrimp）、
    4（曜日）、5（選択肢、this_design）。
  - 数え方が法則とスクリプトで同じ読みになるよう作ったので、mismatch は 0 になる見込みが高い。この実験が確かめるのは、
    個体の深さを種類からの式（r_ind_kind の個数）で書けて、法則の層を壊さず（changed, extra）、個体の端の概念がすべて
    分類されること（uncovered）。
見込み: errors 0、ec_errors 0、mismatch 0、uncovered 0、changed 0、extra 0。shifted は 14 以下（個体の端が浅い概念が r_shallow に入る）。

行（sys_individual_depth_<引数>.json）:
  "summary 要約": errors, ec_errors, law_shallow, script, mismatch, ind, uncovered, changed, extra, shifted, v_shallow
  "mismatch y":   law（0 か 1）, script（0 か 1）, depth（スクリプトの深さの最大）
  "shift y":      before（0 か 1）, after（0 か 1）, depth（after だけ）
  "rel r":        n, h（before だけ。関係ごとの文の数と、文の並びのハッシュ）
  "shallow y":    1（before だけ。r_shallow の概念）

使い方:
  python exp/experiments/sys_individual_depth.py before|after
"""
import collections
import contextlib
import hashlib
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
LAWS = {"deep_end", "shallow_ends", "deep_end_ind", "shallow_ends_ind"}
NEW_LAWS = LAWS | {"syntax." + x for x in LAWS}
NEW_RELS = {"r_deep_end", "r_shallow", "syntax.r_deep_end", "syntax.r_shallow"}


def closure(T, rules, O):
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(rules, F, tc.variables(O))
    return F


def digest(F, skip=()):
    out = {}
    for r, xs in F.by.items():
        keep = sorted(str(x) for x in xs if not any(str(a) in skip for a in x))
        if keep:
            out[r] = [len(keep), hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]]
    return out


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    n_err = len(tc.errors)
    with contextlib.redirect_stdout(io.StringIO()):
        import exp_check
        del tc.errors[:]
        try:
            exp_check.build()
        except SystemExit:
            pass
    ec_err = len(tc.errors)
    rules = tc.law_rules(O)
    base = [(lid, l) for lid, l in rules if lid not in NEW_LAWS]
    F = closure(T, rules, O)
    F0 = closure(T, base, O)
    own, with_ = collections.defaultdict(set), collections.defaultdict(set)
    for t in F.by.get("r_own", ()):
        own[t[0]].add(t[1])
    for t in F.by.get("with", ()):
        if len(t) == 2:
            with_[t[0]].add(t[1])

    def deep(e):
        if e in T.N:
            return len(T.ancestors(e))
        k = T.q(T.I[e]) if isinstance(T.I.get(e), str) else None
        return 1 + len(T.ancestors(k)) if k in T.N else None

    script, depth, ind = set(), {}, set()
    for y in own:
        ends = [e for m in own[y] for e in with_[m]]
        if any(e not in T.N and isinstance(T.I.get(e), str) for e in ends):
            ind.add(y)
        ds = [d for e in ends for d in [deep(e)] if d is not None]
        if ds:
            depth[y] = max(ds)
            if max(ds) <= 2:
                script.add(y)
    rel = lambda name: {t[0] for r in NEW_RELS if r.endswith(name) for t in F.by.get(r, ())}
    law, deep_ = rel("r_shallow"), rel("r_deep_end")
    mism = sorted(law ^ script)
    uncovered = sorted(y for y in ind if y not in law and y not in deep_)
    two = lambda r: {(t[0], t[1]) for t in F.by.get(r, ()) if len(t) == 2}
    acc, has = collections.defaultdict(set), collections.defaultdict(set)
    for a, b in two("r_acc"):
        acc[a].add(b)
    for a, b in two("r_has"):
        has[a].add(b)
    V = [(x, y) for x, y in two("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x]]
    rows = {}
    if label == "before":
        changed = extra = shifted = 0
        shift = []
        rows |= {f"rel {r}": {"n": v[0], "h": v[1]} for r, v in sorted(digest(F0, skip=NEW_LAWS | NEW_RELS).items())}
        rows |= {f"shallow {y}": {"v": 1} for y in sorted(law)}
    else:
        prev = json.loads((OUT / "sys_individual_depth_before.json").read_text(encoding="utf-8"))["rows"]
        old = {k[4:]: [v["n"], v["h"]] for k, v in prev.items() if k.startswith("rel ")}
        now = digest(F0, skip=NEW_LAWS | NEW_RELS)
        changed = sum(1 for r in set(old) | set(now) if old.get(r) != now.get(r))
        extra = sum(1 for r, xs in F.by.items() if r not in NEW_RELS for x in xs if not F0.has(r, x))
        for r in sorted(set(old) | set(now)):
            if old.get(r) != now.get(r):
                print("changed", r, old.get(r), now.get(r))
        before = {k[8:] for k in prev if k.startswith("shallow ")}
        shift = sorted(before ^ law)
        shifted = len(shift)
        rows |= {f"shift {y}": {"before": int(y in before), "after": int(y in law), "depth": depth.get(y)} for y in shift}
    summ = {"errors": n_err, "ec_errors": ec_err, "law_shallow": len(law), "script": len(script), "mismatch": len(mism),
            "ind": len(ind), "uncovered": len(uncovered), "changed": changed, "extra": extra, "shifted": shifted,
            "v_shallow": sum(1 for _, y in V if y in law)}
    rows = {"summary 要約": summ} | {f"mismatch {y}": {"law": int(y in law), "script": int(y in script), "depth": depth.get(y)}
                                    for y in mism} | rows
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_individual_depth_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for y in mism[:20]:
        print("mismatch", y, rows[f"mismatch {y}"])
    for y in uncovered:
        print("uncovered", y)
    for y in shift:
        print("shift", y, rows[f"shift {y}"])
    for e in tc.errors[:10]:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"])
    main(sys.argv[1])
