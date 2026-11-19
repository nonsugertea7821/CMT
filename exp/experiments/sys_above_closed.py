"""仮説 h_above_closed（依存する(上位の順序, extends)）を確かめる: 上位（above）に順序の法則と「上位は祖先である」の法則を足しても、
今の体系の事実と誤りは変わらず、祖先でない上位を直接書いた世界は誤りになるか。結果を見る前に、この説明と手順を登録した。

背景（登録の commit 46dce5d）: 今の体系で above は、法則 above_by_ancestor（祖先は上位である）からだけ導かれる。推移・非対称は
  r_ancestor（extends の閉包と非循環の法則）から外延で成り立つだけで、above 自身の法則としては書かれていない。橋は片道
  （祖先 ⇒ above）で、above ⇒ 祖先 がない。種類どうしの事実で v_above を直接書いても、法則の層では above の文にならない
  （syntax_facts は kind_fact の of・from・to として置く）ので、縛られない。
操作（この手順の登録のあと、測る前に行う。cscl/library/syntax/syntax.yaml だけを変える。コメントは書かない）:
  法則 4 つを足す。今ある above_by_ancestor は変えない:
       above_by_fact: {is: law_rule, display: 種類どうしの事実で上位に持つと書いたものは、上位である}
       above_is_ancestor: {is: law_rule, display: 上位は祖先である}
       above_asymmetric: {is: law_rule, display: 上位の逆は上位でない}
       above_transitive: {is: law_rule, display: 上位の上位は上位である}
       - {is: v_assume, from: above_by_fact, to: {is: of, from: var1, to: v_above}}
       - {is: v_assume, from: above_by_fact, to: {is: from, from: var1, to: var2}}
       - {is: v_assume, from: above_by_fact, to: {is: to, from: var1, to: var3}}
       - {is: v_derive, from: above_by_fact, to: {is: above, from: var2, to: var3}}
       - {is: v_assume, from: above_is_ancestor, to: {is: above, from: var1, to: var2}}
       - {is: v_require, from: above_is_ancestor, to: {is: r_ancestor, from: var1, to: var2}}
       - {is: v_assume, from: above_asymmetric, to: {is: above, from: var1, to: var2}}
       - {is: v_require, from: above_asymmetric, to: {is: above, from: var2, to: var1, neg: true}}
       - {is: v_assume, from: above_transitive, to: {is: above, from: var1, to: var2}}
       - {is: v_assume, from: above_transitive, to: {is: above, from: var2, to: var3}}
       - {is: v_require, from: above_transitive, to: {is: above, from: var1, to: var3}}

数え方（引数 before / after）:
  errors       型検査の誤りの数
  ec_errors    exp の検査（exp/src/exp_check.py）の誤りの数
  law_errors   誤りのうち、新しい法則（above_*）に反するものの数
  above        閉じた事実の above の文の数
  changed      新しい法則を除いた規則で閉じた事実を before と比べ、違う関係の数
  extra        新しい法則を入れて閉じた事実のうち、入れないときにない文の数
  probe_non    （after だけ）作業木の写しで、cscl/design/claims.yaml に種類どうしの事実
               {is: v_above, from: above_order, to: individual_depth}（祖先でない組。どちらも quality の下の兄弟）を足して
               型検査したときの、新しい法則に反する誤りの数
  probe_non_all 同じ写しでの誤りの総数
  probe_anc    同じく {is: v_above, from: above_order, to: quality}（祖先の組）を足したときの、新しい法則に反する誤りの数
  probe_anc_all 同じ写しでの誤りの総数
判定: after で errors 0、ec_errors 0、changed 0、extra 0、probe_anc_all 0、probe_non ≥ 1 なら支持（v_support）。
  after で law_errors ≥ 1（今の上位が順序でないか、祖先でない上位がある）か、probe_non 0（祖先でない上位を書いても縛られない）なら
  反証（v_contradict）。それ以外（新しい法則以外の誤り、changed か extra が 0 でない、probe_anc_all が 0 でない）は、
  内容を書いて外れとし、状態は変えない。
登録の前に分かっていること（下調べ）:
  - 登録の commit の数え: above は 2478 組で、反射 0、対称 0、推移の欠け 0。
  - 写しで v_above の種類どうしの事実を足すと、T.KF に ('ontology.v_above', {from, to}) が入り、syntax_facts に
    of('kind_fact 0', 'ontology.v_above') が出る（法則を足さずに確かめた。誤り 0）。
見込み: 支持。

行（sys_above_closed_<引数>.json）:
  "summary 要約": 上の数
  "rel r":        n, h（before だけ。関係ごとの文の数と、文の並びのハッシュ）
  "error i":      新しい法則に反する誤りの文（after と probe。先頭 20）

訂正（after を走らせた後に書き足す。開示）:
  after で changed が 4 になった。違った関係は is・domain・r_written・r_ind_kind で、増えた文は新しい法則の個体
  （above_by_fact ほか 4 つ）そのものについての文（法則であること、領域、綴り、属する種類）だけだった。
  手本の sys_individual_depth は digest で新しい法則の名を含む文を除いていたが、この手順はそれを落としていた。
  そこで changed を、新しい法則の名を含む文を除いて数え直す（sys_above_closed_fix.py。結果は sys_above_closed_after_fix.json。
  before と after の記録は上書きしない）。数え直しでは before の側も同じ除き方で、記録の rel の行ではなく、
  手順の登録の commit（577cbcc）の syntax.yaml で閉じた事実を作り直して比べる。
  判定は、changed をこの数え直しに置き換えて、上の規則で行う。訂正なので、手で見てもらう。

使い方:
  python exp/experiments/sys_above_closed.py before|after
"""
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "exp/src")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
LAWS = {"above_by_fact", "above_is_ancestor", "above_asymmetric", "above_transitive"}
NEW_LAWS = LAWS | {"syntax." + x for x in LAWS}
PROBE_ANCHOR = "  - {is: v_refer, from: h_above_closed,"
PROBE = """
import contextlib, io, json, sys
sys.path.insert(0, "cscl/bootstrap/type_checker")
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    tc.build()
print(json.dumps([str(e) for e in tc.errors], ensure_ascii=False))
"""


def closure(T, rules, O):
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(rules, F, tc.variables(O))
    return F


def digest(F):
    out = {}
    for r, xs in F.by.items():
        keep = sorted(str(x) for x in xs)
        if keep:
            out[r] = [len(keep), hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]]
    return out


def is_new(e):
    return any(f"法則 {x}（" in str(e) or f"法則 syntax.{x}（" in str(e) for x in LAWS)


def probe(fact):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        c = Path(d) / "cscl/design/claims.yaml"
        s = c.read_text(encoding="utf-8")
        assert s.count(PROBE_ANCHOR) == 1
        c.write_text(s.replace(PROBE_ANCHOR, f"  - {fact}\n" + PROBE_ANCHOR), encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        errs = json.loads(out.stdout.strip().splitlines()[-1])
    return errs


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    errs = list(tc.errors)
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
    law_errs = [str(e) for e in errs if is_new(e)]
    rows = {}
    summ = {"errors": len(errs), "ec_errors": ec_err, "law_errors": len(law_errs), "above": len(F.by.get("above", ()))}
    if label == "before":
        summ |= {"changed": 0, "extra": 0}
        rows |= {f"rel {r}": {"n": v[0], "h": v[1]} for r, v in sorted(digest(F0).items())}
    else:
        prev = json.loads((OUT / "sys_above_closed_before.json").read_text(encoding="utf-8"))["rows"]
        old = {k[4:]: [v["n"], v["h"]] for k, v in prev.items() if k.startswith("rel ")}
        now = digest(F0)
        summ["changed"] = sum(1 for r in set(old) | set(now) if old.get(r) != now.get(r))
        summ["extra"] = sum(1 for r, xs in F.by.items() for x in xs if not F0.has(r, x))
        non = probe("{is: v_above, from: above_order, to: individual_depth}")
        anc = probe("{is: v_above, from: above_order, to: quality}")
        summ |= {"probe_non": sum(map(is_new, non)), "probe_non_all": len(non),
                 "probe_anc": sum(map(is_new, anc)), "probe_anc_all": len(anc)}
        rows |= {f"error probe_non {i}": {"text": e} for i, e in enumerate(non[:20])}
        rows |= {f"error probe_anc {i}": {"text": e} for i, e in enumerate(anc[:20])}
    rows |= {f"error {label} {i}": {"text": e} for i, e in enumerate(law_errs[:20])}
    rows = {"summary 要約": summ} | rows
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_above_closed_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, v in rows.items():
        if k.startswith("error"):
            print(k, v["text"])


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"])
    main(sys.argv[1])
