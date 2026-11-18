"""体系そのものを数える: 規則の前提の原子に書いた個数の限定（at: {count}）を評価器が評価すれば、「浅い端だけで定義される」を
法則として書け、スクリプトが数えた浅さと一致するか。結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_draw_on で、読みの中身の語「浅い端だけの定義」を式で書けず、役割（role）と同じ限定になった（named_mod の誤り）。
  浅さは型階層の深さ（祖先の数）で、体系には二つの欠けがある。
  欠け1（反映）: 階層（extends から導く r_ancestor）は動詞でないので、限定の of に置けない。
  欠け2（数えること）: 法則の評価器は否定つきの Datalog で集計を持たない。一階の言語では鎖の長さを一様に定義できず、閾値ごとに
    式の形（変数の数）が変わる。一方、体系は文法に at: {count} を持ち、個数の軸は source: any（どの関係でも数えられる）と言っている。
    統語の約束を、翻訳（評価器）が果たしていない。
  この実験は欠け2だけを扱う。法則の規則は導いた関係を直接使えるので、欠け1がなくても浅さを法則として書ける。
操作（この手順の登録のあと、測る前に行う）:
  1. 評価器（cscl/bootstrap/type_checker/type_checker.py の compile_atoms, _match, strata）: 前提の原子が at: {count: c} を持つとき、
     その原子を、束縛済みの変数を固定して満たす組（束縛されていない位置の値の組）の数が c に入ることと読む。c の書き方は
     型検査器の count_ok と同じ（数か {gt|ge|lt|le: 数}）。数えた原子の変数は外に束縛しない。数える関係は否定と同じく下の層に置く
     （層の計算で +1）。肯定の前提のあと、否定の前提と同じ順で見る。at を持たない原子の扱いは変えない。
  2. cscl/library/syntax/syntax.yaml に、導く関係 2 つと法則 2 つを足す（ほかは変えない。コメントは書かない）:
       r_deep_end: {is: law_relation, display: 深い端を持つ}
       r_shallow: {is: law_relation, display: 浅い端だけで定義される}
       deep_end: {is: law_rule, display: 自前の式の端に、祖先が3つ以上ある種類があれば、深い端を持つ}
       shallow_ends: {is: law_rule, display: 自前の式に端があり、深い端を持たなければ、浅い端だけで定義される}
       - {is: v_assume, from: deep_end, to: {is: r_own, from: var1, to: var2}}
       - {is: v_assume, from: deep_end, to: {is: with, from: var2, to: var3}}
       - {is: v_assume, from: deep_end, to: {is: r_ancestor, from: var3, to: var4, at: {count: {gt: 2}}}}
       - {is: v_derive, from: deep_end, to: {is: r_deep_end, from: var1}}
       - {is: v_assume, from: shallow_ends, to: {is: r_own, from: var1, to: var2}}
       - {is: v_assume, from: shallow_ends, to: {is: with, from: var2, to: var3}}
       - {is: v_assume, from: shallow_ends, to: {is: r_deep_end, from: var1, neg: true}}
       - {is: v_derive, from: shallow_ends, to: {is: r_shallow, from: var1}}

数え方（引数 before / after）:
  errors        型検査の誤りの数
  ec_errors     exp の検査（exp/src/exp_check.py）の誤りの数
  law_shallow   r_shallow が導かれた概念の数
  script        sys_specific_depth の定義で浅い概念の数: 自前の式（r_own）の with の終点の深さ（T.ancestors の数）が
                あり、その最大が 2 以下。r_own を持つすべての概念で数える
  mismatch      law_shallow と script の対称差の大きさ
  changed       関係ごとに、新しい 2 つの法則を除いた規則で閉じた事実を before と比べ、新しい法則の識別子を含まない文が
                違う関係の数（評価器の変更が、at を持たない規則の結果を変えないことの確かめ）
  extra         新しい法則を入れて閉じた事実のうち、入れないときになく、r_deep_end と r_shallow でもない文の数
判定: after で errors 0、ec_errors 0、mismatch 0、changed 0、extra 0 を満たせば「統語の count を評価器が果たせば、浅さは
  法則として書け、スクリプトの浅さと一致する」。満たさないものは、その内容を書いて外れとする。
登録の前に分かっていること: before では r_deep_end と r_shallow はない。sys_specific_depth は V と C の組の y だけを数えた
  （すべての概念では数えていない）。T.ancestors と r_ancestor が同じ祖先を返すかは確かめていない（T.ancestors は形の指定 form を
  持つノードで、位置の型を上位にする）。
見込み: errors 0、ec_errors 0、changed 0、extra 0。mismatch は 0 か、form を端に持つ概念の数だけ出る。

行（sys_count_atom_<引数>.json）:
  "summary 要約": errors, ec_errors, law_shallow, script, mismatch, changed, extra
  "mismatch y":   law（0 か 1）, script（0 か 1）, depth（スクリプトの深さの最大）
  "rel r":        n（before だけ。関係ごとの文の数と、文の並びのハッシュ）

使い方:
  python exp/experiments/sys_count_atom.py before|after
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
NEW_LAWS = {"syntax.deep_end", "syntax.shallow_ends", "deep_end", "shallow_ends"}
NEW_RELS = {"r_deep_end", "r_shallow", "syntax.r_deep_end", "syntax.r_shallow"}


def closure(T, O, rules):
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
    F = closure(T, O, rules)
    F0 = closure(T, O, base)
    own, with_ = collections.defaultdict(set), collections.defaultdict(set)
    for t in F.by.get("r_own", ()):
        own[t[0]].add(t[1])
    for t in F.by.get("with", ()):
        if len(t) == 2:
            with_[t[0]].add(t[1])
    script, depth = set(), {}
    for y in own:
        ds = [len(T.ancestors(e)) for m in own[y] for e in with_[m]]
        if ds:
            depth[y] = max(ds)
            if max(ds) <= 2:
                script.add(y)
    law = {t[0] for r in NEW_RELS if r.endswith("r_shallow") for t in F.by.get(r, ())}
    mism = sorted(law ^ script)
    rows = {}
    if label == "before":
        changed = extra = 0
        rows |= {f"rel {r}": {"n": v[0], "h": v[1]} for r, v in sorted(digest(F0).items())}
    else:
        prev = json.loads((OUT / "sys_count_atom_before.json").read_text(encoding="utf-8"))["rows"]
        old = {k[4:]: [v["n"], v["h"]] for k, v in prev.items() if k.startswith("rel ")}
        now = digest(F0, skip=NEW_LAWS | NEW_RELS)
        changed = sum(1 for r in set(old) | set(now) if old.get(r) != now.get(r))
        extra = sum(1 for r, xs in F.by.items() if r not in NEW_RELS for x in xs if not F0.has(r, x))
        for r in sorted(set(old) | set(now)):
            if old.get(r) != now.get(r):
                print("changed", r, old.get(r), now.get(r))
    summ = {"errors": n_err, "ec_errors": ec_err, "law_shallow": len(law), "script": len(script),
            "mismatch": len(mism), "changed": changed, "extra": extra}
    rows = {"summary 要約": summ} | {f"mismatch {y}": {"law": int(y in law), "script": int(y in script), "depth": depth.get(y)}
                                    for y in mism} | rows
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_count_atom_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for y in mism[:20]:
        print("mismatch", y, rows[f"mismatch {y}"])
    for e in tc.errors[:10]:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"])
    main(sys.argv[1])
