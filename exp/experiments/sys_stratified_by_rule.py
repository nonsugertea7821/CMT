"""仮説 h_stratified_by_rule（定義の循環は、今ある文の上の導いた関係で書ける:
v_depend(definition_cycle, syntax.law_relation)）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: h_law_given_by_facts（#436）を、残りの law_given ごとに確かめる一つ目。
  definition_stratified（check_definition_stratified）は、定義の辺（extends、名前を付けた修飾語の with、
  限定の with）をたどり、否定の限定の辺が循環の中にあれば咎める。その辺は syntax_facts の文
  （extends、with、mod、neg、exists）に既にある。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  syntax.yaml の写しに、関係と規則を足す（文は足さない）。
    関係: r_def_edge（定義の辺）、r_def_neg（否定の定義の辺）、r_def_back（否定の辺の始点へ戻る道）を law_relation として置く。
    def_by_extends: extends(var1, var2) かつ exists(var2) から r_def_edge(var1, var2)
    def_by_with:    with(var1, var2) かつ exists(var1) かつ exists(var2) から r_def_edge(var1, var2)
    def_by_mod:     mod(var1, var3) かつ with(var3, var2) かつ exists(var2) から r_def_edge(var1, var2)
    def_neg_with:   with(var1, var2) かつ neg(var1, 'true') かつ exists(var1) かつ exists(var2) から r_def_neg(var1, var2)
    def_neg_mod:    mod(var1, var3) かつ with(var3, var2) かつ neg(var3, 'true') かつ exists(var2) から r_def_neg(var1, var2)
    def_back_start: r_def_neg(var1, var2) から r_def_back(var2, var1)
    def_back_step:  r_def_back(var1, var2) かつ r_def_edge(var1, var3) から r_def_back(var3, var2)
    stratified_rule: r_def_neg(var1, var2) なら、r_def_back(var1, var1) が成り立たないことを求める
      （否定の辺 var1→var2 の終点から、辺をたどって始点 var1 に戻れない）。
版（lang の写しにノードを足す。アンカーは negated_limitation の行）:
  B 何も足さない
  V 否定の循環: zz_x は zz_y を否定で限定し、zz_y は zz_x の下位
  P 肯定の循環: V から否定を除く
  W 循環しない否定: zz_x は quality を否定で限定する
  版ごとに tc.build() を 1 回走らせる。
数える量（版 v ごと）:
  py_<v>     法則 definition_stratified（Python）の誤りの数
  rule_<v>   規則 stratified_rule の誤りの数
  agree_<v>  Python が咎める否定の辺の集まりと、規則の誤りの (var1, var2) の集まりが等しければ 1
  other_<v>  それ以外の誤りの数（B の誤りに無いもの）
判定（事前に決める）:
  すべての版で agree = 1 かつ other = 0 で、py_V ≥ 1 なら支持。
  other がどれも 0 で、agree = 0 の版が一つでもあれば反証。
  other ≥ 1 の版があれば、手順の誤りとして開示し、状態を変えない。
範囲: definition_stratified の一つだけ。h_law_given_by_facts の状態は、この手順では変えない。
行（sys_stratified_by_rule.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_stratified_by_rule.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_stratified_by_rule.json"
SYN = "cscl/library/syntax/syntax.yaml"
CLAIMS = "cscl/design/claims.yaml"
NODE_ANCHOR = "  negated_limitation: {display: 否定の限定, extends: quality, mod: {of: [v_refer, from], with: syntax.neg}}\n"
CASES = {
    "B": "",
    "V": ("  zz_x: {display: 試しX, extends: quality, mod: {of: [v_refer, from], with: zz_y, neg: true}}\n"
          "  zz_y: {display: 試しY, extends: zz_x}\n"),
    "P": ("  zz_x: {display: 試しX, extends: quality, mod: {of: [v_refer, from], with: zz_y}}\n"
          "  zz_y: {display: 試しY, extends: zz_x}\n"),
    "W": "  zz_x: {display: 試しX, extends: quality, mod: {of: [v_refer, from], with: quality, neg: true}}\n",
}
SYN_IND_ANCHOR = "  definition_stratified: {is: law_given, display: 定義の循環は否定の限定を通らない（自分を限定するものは肯定の位置にだけ現れる）}\n"
SYN_FACTS_ANCHOR = "  - {is: v_govern, from: definition_stratified, to: concept_expression}\n"
SYN_IND = '''  r_def_edge: {is: law_relation, display: 定義の辺である}
  r_def_neg: {is: law_relation, display: 否定の定義の辺である}
  r_def_back: {is: law_relation, display: 否定の辺の始点へ戻る道にある}
  def_by_extends: {is: law_rule, display: 上位は定義の辺}
  def_by_with: {is: law_rule, display: 修飾語の限定は定義の辺}
  def_by_mod: {is: law_rule, display: 限定は定義の辺}
  def_neg_with: {is: law_rule, display: 修飾語の否定の限定は否定の定義の辺}
  def_neg_mod: {is: law_rule, display: 否定の限定は否定の定義の辺}
  def_back_start: {is: law_rule, display: 否定の辺の終点から始点へ戻る道を始める}
  def_back_step: {is: law_rule, display: 定義の辺をたどって戻る道を延ばす}
  stratified_rule: {is: law_rule, display: 否定の辺の終点から始点へ戻れない}
'''
SYN_FACTS = '''  - {is: v_assume, from: def_by_extends, to: {is: extends, from: var1, to: var2}}
  - {is: v_assume, from: def_by_extends, to: {is: exists, from: var2}}
  - {is: v_derive, from: def_by_extends, to: {is: r_def_edge, from: var1, to: var2}}
  - {is: v_assume, from: def_by_with, to: {is: with, from: var1, to: var2}}
  - {is: v_assume, from: def_by_with, to: {is: exists, from: var1}}
  - {is: v_assume, from: def_by_with, to: {is: exists, from: var2}}
  - {is: v_derive, from: def_by_with, to: {is: r_def_edge, from: var1, to: var2}}
  - {is: v_assume, from: def_by_mod, to: {is: mod, from: var1, to: var3}}
  - {is: v_assume, from: def_by_mod, to: {is: with, from: var3, to: var2}}
  - {is: v_assume, from: def_by_mod, to: {is: exists, from: var2}}
  - {is: v_derive, from: def_by_mod, to: {is: r_def_edge, from: var1, to: var2}}
  - {is: v_assume, from: def_neg_with, to: {is: with, from: var1, to: var2}}
  - {is: v_assume, from: def_neg_with, to: {is: neg, from: var1, to: 'true'}}
  - {is: v_assume, from: def_neg_with, to: {is: exists, from: var1}}
  - {is: v_assume, from: def_neg_with, to: {is: exists, from: var2}}
  - {is: v_derive, from: def_neg_with, to: {is: r_def_neg, from: var1, to: var2}}
  - {is: v_assume, from: def_neg_mod, to: {is: mod, from: var1, to: var3}}
  - {is: v_assume, from: def_neg_mod, to: {is: with, from: var3, to: var2}}
  - {is: v_assume, from: def_neg_mod, to: {is: neg, from: var3, to: 'true'}}
  - {is: v_assume, from: def_neg_mod, to: {is: exists, from: var2}}
  - {is: v_derive, from: def_neg_mod, to: {is: r_def_neg, from: var1, to: var2}}
  - {is: v_assume, from: def_back_start, to: {is: r_def_neg, from: var1, to: var2}}
  - {is: v_derive, from: def_back_start, to: {is: r_def_back, from: var2, to: var1}}
  - {is: v_assume, from: def_back_step, to: {is: r_def_back, from: var1, to: var2}}
  - {is: v_assume, from: def_back_step, to: {is: r_def_edge, from: var1, to: var3}}
  - {is: v_derive, from: def_back_step, to: {is: r_def_back, from: var3, to: var2}}
  - {is: v_assume, from: stratified_rule, to: {is: r_def_neg, from: var1, to: var2}}
  - {is: v_require, from: stratified_rule, to: {is: r_def_back, from: var1, to: var1, neg: true}}
'''

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        tc.build()
        crash = ""
    except Exception as e:
        crash = repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
print(json.dumps(errs, ensure_ascii=False))
'''


def patch(p, old, new):
    s = p.read_text()
    assert s.count(old) == 1, old
    p.write_text(s.replace(old, new))


def run(case):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")
        patch(d / SYN, SYN_IND_ANCHOR, SYN_IND_ANCHOR + SYN_IND)
        patch(d / SYN, SYN_FACTS_ANCHOR, SYN_FACTS_ANCHOR + SYN_FACTS)
        if CASES[case]:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + CASES[case])
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return ["probe failed: " + r.stderr[-300:]]


def py_edges(e):
    m = re.search(r"否定の限定 (\[.*\]) を通る", e)
    return set(re.findall(r"\('([^']+)', '([^']+)'\)", m.group(1))) if m else set()


def rule_edge(e):
    m = re.search(r"var1=([^,\s]+), var2=([^,\s]+)", e)
    return {(m.group(1), m.group(2))} if m else set()


def main():
    summary, texts = {}, {}
    base = None
    for c in CASES:
        errs = run(c)
        py = [e for e in errs if "法則 definition_stratified に反する" in e]
        rule = [e for e in errs if "法則 stratified_rule" in e]
        rest = [e for e in errs if e not in py and e not in rule]
        if base is None:
            base = set(rest)
        other = [e for e in rest if e not in base] + (sorted(base) if c == "B" else [])
        pye = set().union(*map(py_edges, py)) if py else set()
        re_ = set().union(*map(rule_edge, rule)) if rule else set()
        summary[f"py_{c}"] = len(py)
        summary[f"rule_{c}"] = len(rule)
        summary[f"agree_{c}"] = int(pye == re_)
        summary[f"other_{c}"] = len(other)
        texts[f"errors {c}"] = (py + rule + other)[:6]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
