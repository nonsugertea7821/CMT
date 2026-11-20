"""仮説 h_world_by_presume_facts（world_declared は、領域の前提と法則の領域を文にすれば規則で書ける:
v_depend(syntax.law_relation, [syntax.world, syntax.domain])）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: h_law_given_by_facts（#436）を、残りの law_given ごとに確かめる三つ目（named_mod #435、definition_stratified #439 の次）。
  world_declared（check_world_declared）は、各ファイルの v_presume を書いたまま読み、
  (1) 一つの領域が書かれていない文の扱いを二つ以上置けば咎め、
  (2) 否定を前提に使う法則の領域が閉世界を置かなければ咎める。
  syntax_facts は今、領域の前提も、法則の領域も、前提に否定があるかも文にしていない。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  検査器の写しの syntax_facts に、文を三つ足す（Python の検査はそのまま残し、比べる）:
    presume(領域, 扱い)        presumed_worlds() の各組。扱いは syntax の領域で直した識別子（qn_raw(扱い, "syntax")）
    law_domain(法則, 領域)      O["laws"] の各法則と、その個体の領域（_idom）
    assume_neg(法則, 'true')   前提に neg を持つ法則
  syntax.yaml の写しに、関係と規則を足す:
    関係: presume、law_domain、assume_neg を law_relation として置く。
    world_unique: presume(var1, var2) かつ presume(var1, var3) なら、same(var2, var3) を求める
    world_rule:   assume_neg(var1, 'true') かつ law_domain(var1, var2) なら、presume(var2, closed_world) を求める
版（std・runtime の写しを書き換える）:
  B 何も変えない
  R std の {is: v_presume, from: std, to: closed_world} を除く（std には否定を前提に使う法則がある）
  D std に {is: v_presume, from: std, to: world} を足す（std が扱いを二つ置く）
  Q runtime の {is: v_presume, from: runtime, to: closed_world} を除く（runtime には否定を前提に使う法則がない）
  版ごとに tc.build() を 1 回走らせる。
数える量（版 v ごと）:
  py_<v>     法則 world_declared（Python）の誤りの数
  rule_<v>   規則 world_unique と world_rule の誤りの数
  agree_<v>  Python が咎める法則の集まりと world_rule の var1 の集まりが等しく、
             かつ Python が咎める領域の集まりと world_unique の var1 の集まりが等しければ 1
  other_<v>  それ以外の誤りの数（B の誤りに無いもの。B では B の誤りすべて）
判定（事前に決める）:
  すべての版で agree = 1 かつ other = 0 で、py_R ≥ 1 かつ py_D ≥ 1 なら支持。
  other がどれも 0 で、agree = 0 の版が一つでもあれば反証。
  other ≥ 1 の版があれば、手順の誤りとして開示し、状態を変えない。
範囲: world_declared の一つだけ。h_law_given_by_facts の状態は、この手順では変えない。
行（sys_world_by_presume.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_world_by_presume.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_world_by_presume.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
STD = "cscl/library/std/std.yaml"
RUN = "cscl/library/runtime/runtime.yaml"
TC_ANCHOR = '        for did, d in self.O["domains"].items():\n'
TC_ADD = '''        for dom, ws in presumed_worlds().items():
            for w in ws:
                add("presume", dom, qn_raw(w, "syntax"))
        for lid, l in self.O.get("laws", {}).items():
            add("law_domain", lid, self.O["_idom"].get(lid))
            if any(isinstance(a, dict) and a.get("neg") for a in l.get("assume") or []):
                add("assume_neg", lid, "true")
'''
STD_PRESUME = "  - {is: v_presume, from: std, to: closed_world}\n"
RUN_PRESUME = "  - {is: v_presume, from: runtime, to: closed_world}\n"
CASES = {
    "B": [],
    "R": [(STD, STD_PRESUME, "")],
    "D": [(STD, STD_PRESUME, STD_PRESUME + "  - {is: v_presume, from: std, to: world}\n")],
    "Q": [(RUN, RUN_PRESUME, "")],
}
SYN_IND_ANCHOR = "  world_declared: {is: law_given, display: 否定を前提に使う法則は、その法則の領域が閉世界を前提に置くときだけ当てはめる}\n"
SYN_FACTS_ANCHOR = "  - {is: v_govern, from: world_declared, to: concept_expression}\n"
SYN_IND = '''  presume: {is: law_relation, display: 領域が前提に置く扱いである}
  law_domain: {is: law_relation, display: 法則の領域である}
  assume_neg: {is: law_relation, display: 否定を前提に使う}
  world_unique: {is: law_rule, display: 一つの領域が置く扱いは一つ}
  world_rule: {is: law_rule, display: 否定を前提に使う法則の領域は閉世界を置く}
'''
SYN_FACTS = '''  - {is: v_assume, from: world_unique, to: {is: presume, from: var1, to: var2}}
  - {is: v_assume, from: world_unique, to: {is: presume, from: var1, to: var3}}
  - {is: v_require, from: world_unique, to: {is: same, from: var2, to: var3}}
  - {is: v_assume, from: world_rule, to: {is: assume_neg, from: var1, to: 'true'}}
  - {is: v_assume, from: world_rule, to: {is: law_domain, from: var1, to: var2}}
  - {is: v_require, from: world_rule, to: {is: presume, from: var2, to: closed_world}}
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
        patch(d / TC, TC_ANCHOR, TC_ADD + TC_ANCHOR)
        patch(d / SYN, SYN_IND_ANCHOR, SYN_IND_ANCHOR + SYN_IND)
        patch(d / SYN, SYN_FACTS_ANCHOR, SYN_FACTS_ANCHOR + SYN_FACTS)
        for f, old, new in CASES[case]:
            patch(d / f, old, new)
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return ["probe failed: " + r.stderr[-300:]]


def var1(e):
    m = re.search(r"var1=([^,\s]+)", e)
    return {m.group(1)} if m else set()


def main():
    summary, texts = {}, {}
    base = None
    for c in CASES:
        errs = run(c)
        py = [e for e in errs if "法則 world_declared" in e]
        ru = [e for e in errs if "法則 world_rule" in e]
        rd = [e for e in errs if "法則 world_unique" in e]
        rest = [e for e in errs if e not in py and e not in ru and e not in rd]
        if base is None:
            base = set(rest)
        other = [e for e in rest if e not in base] + (sorted(base) if c == "B" else [])
        py_law = {m.group(1) for e in py for m in [re.search(r"法則 (\S+) は否定を前提に使うが", e)] if m}
        py_dom = {m.group(1) for e in py for m in [re.search(r"領域 (\S+) が、書かれていない文の扱いを2つ以上", e)] if m}
        rule_law = set().union(set(), *map(var1, ru))
        rule_dom = set().union(set(), *map(var1, rd))
        summary[f"py_{c}"] = len(py)
        summary[f"rule_{c}"] = len(ru) + len(rd)
        summary[f"agree_{c}"] = int(py_law == rule_law and py_dom == rule_dom)
        summary[f"other_{c}"] = len(other)
        texts[f"errors {c}"] = (py + ru + rd + other)[:6]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
