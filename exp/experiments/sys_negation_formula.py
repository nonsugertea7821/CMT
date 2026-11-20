"""仮説 h_negation_formula（否定の限定は型検査器に依存しない）を確かめる: 否定の限定の意味を検査器のコードで決めている
法則 definition_stratified（law_given、Python の check_definition_stratified）を、規則で書いた法則（law_rule）に移しても、
同じ判定になるか。結果を見る前に、この説明と手順を登録した。

範囲: 法則のうち、表示語が「否定の限定」に触れる law_given を数える（n_given_neg）。definition_stratified がそれに当たる。
  この実験は、その法則を式に移せるかを問う。否定の限定を読む検査器のほかの箇所（記述: 除外に使う箇所）は対象にしない。
操作（一時の写しで行う。体系のファイルは書き換えない）:
  syntax.yaml の写しに、規則の法則を足す（定義の辺と到達、そして層分けの要求）:
    r_def_edge, r_def_reach（law_relation）
    def_edge_extends: extends(x, y) → r_def_edge(x, y)
    def_edge_mod:     mod(x, y)     → r_def_edge(x, y)   （名前を付けた修飾語と、式の中の限定の両方）
    def_edge_with:    with(x, y)    → r_def_edge(x, y)   （限定から使う語へ）
    def_reach_edge:   r_def_edge(x, y) → r_def_reach(x, y)
    def_reach_step:   r_def_edge(x, z), r_def_reach(z, y) → r_def_reach(x, y)
    stratified_rule:  with(x, y), neg(x, w), r_def_reach(y, x) を前提に、same(x, x) の否定を求める（前提が立てば必ず違反）
  検査器のコードは変えない（Python の definition_stratified も同時に走る）。
  版（claims.yaml の写しの nodes に試しのノードを足す。P0 は足さない）:
    P0 足さない
    P1 自分を否定で限定する:   zz_a: mod {of: [v_refer, from], with: zz_a, neg: true}
    P2 否定を通る2つの循環:    zz_a: mod 否定 with zz_b、zz_b extends zz_a
    P3 否定を通らない循環:     P2 から neg を外す
    P4 名前を付けた否定の修飾語: zz_m: {of: [v_refer, from], with: zz_c, neg: true}、zz_c: mod zz_m
    P5 循環のない否定:         zz_a: mod 否定 with quality
    P6 3つの循環:             zz_a: mod 否定 with zz_c、zz_c extends zz_b、zz_b extends zz_a
数える量（版ごと。tc の build を写しで 1 回）:
  py_<v>   definition_stratified の誤りが 1 つ以上あれば 1、なければ 0
  law_<v>  stratified_rule の誤りが 1 つ以上あれば 1、なければ 0
  other_<v> それ以外の誤りの数（記述）
  agree    py_<v> = law_<v> の版の数（7 のうち）
  n_given_neg 表示語に「否定の限定」を含む law_given の数
判定（事前に決める）:
  agree = 7 かつ other_P0 = 0 なら支持。agree < 7 か other_P0 > 0 なら反証。
  P1・P2・P4・P6 で py が 1、P0・P3・P5 で py が 0 にならない（Python 側が見込みと違う）なら、版の作りの誤りとして mixed。
行（sys_negation_formula.json）:
  "summary 要約": agree, n_given_neg と、版ごとの py_<v>, law_<v>, other_<v>
  "texts": 版ごとの誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_negation_formula.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_negation_formula.json"
SYN, CLAIMS = "cscl/library/syntax/syntax.yaml", "cscl/design/claims.yaml"

LAW_IND_ANCHOR = "  definition_stratified: {is: law_given, display: 定義の循環は否定の限定を通らない（自分を限定するものは肯定の位置にだけ現れる）}\n"
LAW_INDS = ("  r_def_edge: {is: law_relation, display: 定義が使う語である}\n"
            "  r_def_reach: {is: law_relation, display: 定義をたどって届く}\n"
            "  def_edge_extends: {is: law_rule, display: 上位は定義が使う語}\n"
            "  def_edge_mod: {is: law_rule, display: 修飾は定義が使う語}\n"
            "  def_edge_with: {is: law_rule, display: 限定の相手は定義が使う語}\n"
            "  def_reach_edge: {is: law_rule, display: 定義が使う語には届く}\n"
            "  def_reach_step: {is: law_rule, display: 定義が使う語から届くものにも届く}\n"
            "  stratified_rule: {is: law_rule, display: 否定の限定の相手から、その限定に届かない}\n")
LAW_FACT_ANCHOR = "  - {is: v_require, from: acyclic, to: {is: same, from: var1, to: var2, neg: true}}\n"
LAW_FACTS = ("  - {is: v_assume, from: def_edge_extends, to: {is: extends, from: var1, to: var2}}\n"
             "  - {is: v_derive, from: def_edge_extends, to: {is: r_def_edge, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: def_edge_mod, to: {is: mod, from: var1, to: var2}}\n"
             "  - {is: v_derive, from: def_edge_mod, to: {is: r_def_edge, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: def_edge_with, to: {is: with, from: var1, to: var2}}\n"
             "  - {is: v_derive, from: def_edge_with, to: {is: r_def_edge, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: def_reach_edge, to: {is: r_def_edge, from: var1, to: var2}}\n"
             "  - {is: v_derive, from: def_reach_edge, to: {is: r_def_reach, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: def_reach_step, to: {is: r_def_edge, from: var1, to: var3}}\n"
             "  - {is: v_assume, from: def_reach_step, to: {is: r_def_reach, from: var3, to: var2}}\n"
             "  - {is: v_derive, from: def_reach_step, to: {is: r_def_reach, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: stratified_rule, to: {is: with, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: stratified_rule, to: {is: neg, from: var1, to: var3}}\n"
             "  - {is: v_assume, from: stratified_rule, to: {is: r_def_reach, from: var2, to: var1}}\n"
             "  - {is: v_require, from: stratified_rule, to: {is: same, from: var1, to: var1, neg: true}}\n")

NODE_ANCHOR = "  negated_limitation: {display: 否定の限定, extends: quality, mod: {of: [v_refer, from], with: syntax.neg}}\n"
M = "{of: [v_refer, from], with: %s%s}"
NEG = ", neg: true"
CASES = {
    "P0": "",
    "P1": "  zz_a: {display: 試しA, extends: quality, mod: %s}\n" % (M % ("zz_a", NEG)),
    "P2": ("  zz_a: {display: 試しA, extends: quality, mod: %s}\n" % (M % ("zz_b", NEG))
           + "  zz_b: {display: 試しB, extends: zz_a}\n"),
    "P3": ("  zz_a: {display: 試しA, extends: quality, mod: %s}\n" % (M % ("zz_b", ""))
           + "  zz_b: {display: 試しB, extends: zz_a}\n"),
    "P4": ("  zz_m: {display: 試しM, extends: quality, of: [v_refer, from], with: zz_c, neg: true}\n"
           "  zz_c: {display: 試しC, extends: quality, mod: zz_m}\n"),
    "P5": "  zz_a: {display: 試しA, extends: quality, mod: %s}\n" % (M % ("quality", NEG)),
    "P6": ("  zz_a: {display: 試しA, extends: quality, mod: %s}\n" % (M % ("zz_c", NEG))
           + "  zz_b: {display: 試しB, extends: zz_a}\n"
           + "  zz_c: {display: 試しC, extends: zz_b}\n"),
}

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T, O, _ = tc.build()
        crash = ""
    except Exception as e:
        T, O, crash = None, None, repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
py = [e for e in errs if "definition_stratified" in e]
law = [e for e in errs if "stratified_rule" in e]
other = [e for e in errs if e not in py and e not in law]
n_given_neg = None
if O is not None:
    n_given_neg = sum(1 for x in (O.get("individuals") or {}).values()
                      if tc.short(x.get("is") or "") == "law_given" and "否定の限定" in (x.get("display") or ""))
print(json.dumps({"py": int(bool(py)), "law": int(bool(law)), "other": len(other), "n_given_neg": n_given_neg,
                  "texts": (py + law + other)[:6]}, ensure_ascii=False))
'''


def put(s, anchor, add):
    assert s.count(anchor) == 1, anchor
    return s.replace(anchor, anchor + add)


def run(case):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        p = d / SYN
        s = put(p.read_text(), LAW_IND_ANCHOR, LAW_INDS)
        p.write_text(put(s, LAW_FACT_ANCHOR, LAW_FACTS))
        if CASES[case]:
            p = d / CLAIMS
            p.write_text(put(p.read_text(), NODE_ANCHOR, CASES[case]))
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        return json.loads(r.stdout.strip().splitlines()[-1])


def main():
    summary, texts = {}, {}
    for c in CASES:
        r = run(c)
        print(c, r["py"], r["law"], r["other"], flush=True)
        summary[f"py_{c}"], summary[f"law_{c}"], summary[f"other_{c}"] = r["py"], r["law"], r["other"]
        texts[c] = r["texts"]
        if c == "P0":
            summary["n_given_neg"] = r["n_given_neg"]
    summary["agree"] = sum(summary[f"py_{c}"] == summary[f"law_{c}"] for c in CASES)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
