"""仮説 h_hierarchy_in_object（依存する(深さの限定, 基礎の節)）を確かめる: 上位の関係を基礎の関係にし、その動詞を置けば、
深さをノードの限定（mod）として書けて、しかも体系の分類（違反の組）を変えないか。結果を見る前に、この説明と手順を登録した。

背景（会話）: 型階層の深さが今の定義で書けなかった理由は二つ。欠け2（数えること）は sys_count_atom で埋めた。
  欠け1（反映）: 階層（extends から導く r_ancestor）は法則の関係で、動詞でもノードでもないので、限定の of に置けず、仮説の中身でも
  指せない。類比: Tarski の対象言語とメタ言語（部分型は命題ではなく判断）、形式概念分析（FCA）で束の順序は属性ではない。
  仮説を登録したときの意図: 上位の関係を基礎の関係にして動詞を置けば、ノードの限定で深さを書ける。
  FCA の類比からの予想: 順序を属性にすると、その属性で概念が分類し直される。体系では、限定を持つ（r_has）のに、その限定を積んだ
  概念の下にないものが違反の組（V）になる。深い概念はみな「深い種類」の限定を持つので、V が増えるはず。
操作（この手順の登録のあと、測る前に行う。cscl/library/syntax/syntax.yaml だけを変える。コメントは書かない）:
  1. 基礎の節を足す: base: {above: {display: 上位である, arity: 2}}
  2. 動詞を足す: v_above: {display: 上位に持つ, extends: ontology.occurrent, from: any, to: any, holds: [{is: above, from: from, to: to}]}
  3. 深さの限定を持つノードを足す:
       deep_kind: {display: 上位を3つ以上持つ種類, extends: ontology.kind, mod: {of: [v_above, from], with: any, at: {count: {gt: 2}}}}
  4. 階層から限定へ訳す法則を足す（法則の関係 r_ancestor の個数から、その限定を持つ r_has を導く）:
       has_by_depth: {is: law_rule, display: 上位を3つ以上持つものは、上位を3つ以上持つという限定を持つ}
       - {is: v_assume, from: has_by_depth, to: {is: of, from: var2, to: v_above}}
       - {is: v_assume, from: has_by_depth, to: {is: position, from: var2, to: from}}
       - {is: v_assume, from: has_by_depth, to: {is: at, from: var2, to: "count:\\n  gt: 2"}}
       - {is: v_assume, from: has_by_depth, to: {is: exists, from: var1}}
       - {is: v_assume, from: has_by_depth, to: {is: r_ancestor, from: var1, to: var3, at: {count: {gt: 2}}}}
       - {is: v_derive, from: has_by_depth, to: {is: r_has, from: var1, to: var2}}
     法則の原子の個数の限定は規則の中の定数なので、この法則は閾値 2 の限定にしか効かない（閾値ごとに法則が要る）。
     限定の at の文字列を定数で照らすのは、限定が事実の中で文字列として持たれているため（型検査器の syntax_facts）。
  語の名は v_above, above, deep_kind, has_by_depth。名前の付け方が型検査器に合わないときは、意味を変えずに直して開示する。

数え方（引数 before / after）:
  errors       型検査の誤りの数
  ec_errors    exp の検査の誤りの数
  deep_script  上位（T.ancestors）を3つ以上持つノードの数（deep_kind 自身を除く）
  deep_law     deep_kind の限定を r_has で持つノードの数（deep_kind 自身と、その下位を除く）。before は 0
  mismatch     deep_script と deep_law の対称差の大きさ（after だけ。before は 0）
  V            違反の組の数（sys_kind_ref と同じ数え方: r_candidate のうち acc[y] ⊆ has[x] かつ acc[y] ⊄ acc[x]）
  new_V        before にない違反の組の数
  new_V_deep   new_V のうち、上の側（y）が deep_kind の組の数
判定: after で errors 0、ec_errors 0、mismatch 0 なら「深さをノードの限定として書けた」。そのうえで
  new_V が 0 なら支持（v_support）: 深さの限定は基礎の節（上位の関係）に依存して、体系の分類を変えずに書ける。
  new_V が 0 でなければ反証（v_contradict）: 書けるが、限定として書いた深さは属性として働き、概念を分類し直す。
  errors か ec_errors が出るか、mismatch が 0 でなければ、内容を書いて外れとし、状態は変えない（訂正するかは別に決める）。
登録の前に分かっていること（下調べ。測っていない）:
  - 限定は事実の中で、式の YAML の文字列を名に持ち、of, position, with, axis, at の事実を持つ（at の値も文字列）。
  - r_has は、自前と祖先の式（r_acc）と、式どうしの含意（r_entail）から導かれる。限定を持つかは式で決まり、ノードの上下からは
    導かれない。なので、操作 4 の法則がなければ、deep_kind の限定を持つのは deep_kind とその下位だけになる。
  - main の今の V は 3（sys_kind_ref after2 の後、ほかの操作で変わっていない見込み。before で測る）。
見込み: errors 0、ec_errors 0、mismatch 0。new_V は 0 でなく、ほとんどが new_V_deep（反証）。r_candidate を導く法則（sees）に
  ほかの条件があれば new_V は小さくなる。

行（sys_hierarchy_object_<引数>.json）:
  "summary 要約": errors, ec_errors, deep_script, deep_law, mismatch, V, new_V, new_V_deep
  "V x→y":        1
  "mismatch x":   law（0 か 1）, script（0 か 1）

使い方:
  python exp/experiments/sys_hierarchy_object.py before|after
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
DEEP = "syntax.deep_kind"


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
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))

    def two(r):
        d = collections.defaultdict(set)
        for t in F.by.get(r, ()):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    acc, has = two("r_acc"), two("r_has")
    V = sorted((x, y) for x, y in F.by.get("r_candidate", set()) if acc[y] <= has[x] and not acc[y] <= acc[x])
    below = {DEEP} | {n for n in T.N if DEEP in T.ancestors(n)}
    deep_script = {n for n in T.N if n not in below and len(T.ancestors(n)) > 2}
    ms = [t[1] for t in F.by.get("mod", ()) if t[0] == DEEP]
    deep_law = {x for x in T.N if x not in below and any(m in has[x] for m in ms)}
    mism = sorted(deep_script ^ deep_law) if label != "before" else []
    old_V = set()
    if label != "before":
        prev = json.loads((OUT / "sys_hierarchy_object_before.json").read_text(encoding="utf-8"))["rows"]
        old_V = {tuple(k[2:].split("→")) for k in prev if k.startswith("V ")}
    new = [p for p in V if p not in old_V] if label != "before" else []
    summ = {"errors": n_err, "ec_errors": ec_err, "deep_script": len(deep_script), "deep_law": len(deep_law),
            "mismatch": len(mism), "V": len(V), "new_V": len(new), "new_V_deep": sum(1 for _, y in new if y == DEEP)}
    rows = {"summary 要約": summ} | {f"V {a}→{b}": {"v": 1} for a, b in V} | \
        {f"mismatch {x}": {"law": int(x in deep_law), "script": int(x in deep_script)} for x in mism}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_hierarchy_object_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print([f"{a}→{b}" for a, b in new if b != DEEP][:20])
    for x in mism[:20]:
        print("mismatch", x, rows[f"mismatch {x}"])
    for e in errs[:10]:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"])
    main(sys.argv[1])
