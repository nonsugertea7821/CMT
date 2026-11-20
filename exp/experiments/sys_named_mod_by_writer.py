"""仮説 h_named_mod_by_writer（導いた関係が、どの識別子がどの修飾を書いたかを持てば、named_mod は規則で書ける:
v_depend(syntax.law_relation, [syntax.mod, syntax.identifier])）を確かめる。結果を見る前に、この説明と手順を登録した（#421）。

背景: #418 で、今の syntax_facts の上では、ノードが名前で書いたかその場に書いたかが区別できず、named_mod は規則で書けなかった。
  #425 で、名前は綴りで、意味の文には入らないことを確かめた。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  P1 検査器の写しの syntax_facts に、二つの文を足す。
     mod_by_name(x, t)    ノード x が、中身 t の修飾を名前で書いた（mod_name にある）
     mod_content(m, t)    名前を付けた修飾語 m（of を持ち、動詞でないノード）の中身が t
     t は、mod の文と同じ書き方（yaml の dump）にする。
  P2 syntax.yaml の写しに、関係と規則を足す。
     関係: mod_by_name、mod_content、r_named_content（中身 t に名前がある）を law_relation として置く。
     named_content:   mod_content(var1, var2) から r_named_content(var2) を導く。
     named_mod_use:   mod(var1, var2) かつ mod_content(var3, var2) なら、mod_by_name(var1, var2) を求める
                      （名前のある中身は、名前で書く）。
     named_mod_share: mod(var1, var2) かつ mod(var3, var2) かつ var1 と var3 が同じでないなら、r_named_content(var2) を求める
                      （二つのノードが同じ中身を足すなら、その中身には名前がある）。
     どちらも v_govern で concept_expression に結ぶ（named_mod と同じ）。
  版（#418 の訂正と同じ作り。zz_a は symmetry_break の下、zz_b は implementation_break の下）:
     B 何も足さない
     N 両方が zz_m を名前で使う
     M zz_a は名前で、zz_b はその場に書く
     I 両方がその場に書く
     S zz_m を置かず、両方が同じ中身をその場に書く（named_mod の二つ目の場合）
  版ごとに tc.build() を 1 回走らせる。
数える量（版 v ごと）:
  py_<v>     法則 named_mod（Python）の誤りの数
  rule_<v>   規則 named_mod_use・named_mod_share の誤りの数
  agree_<v>  Python の誤りが咎めるノードの集まりと、規則の誤りの var1 の集まりが等しければ 1
  other_<v>  それ以外の誤りの数
判定（事前に決める）:
  すべての版で agree = 1 かつ other = 0 で、py_M ≥ 1、py_I ≥ 1、py_S ≥ 1 なら支持
    （足した二つの文の上の規則が、named_mod と同じノードを咎める）。
  other がどれも 0 で、agree = 0 の版が一つでもあれば反証。
  other ≥ 1 の版があれば、手順の誤りとして開示し、状態を変えない。
範囲: この手順が示すのは「この二つの文を足せば書ける」まで。検査器そのものへの変更は、この PR では行わない。
行（sys_named_mod_by_writer.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_named_mod_by_writer.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_named_mod_by_writer.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
CLAIMS = "cscl/design/claims.yaml"
NODE_ANCHOR = "  negated_limitation: {display: 否定の限定, extends: quality, mod: {of: [v_refer, from], with: syntax.neg}}\n"
ZM = "  zz_m: {display: 試しの修飾語, extends: quality, of: [v_refer, from], with: quality}\n"
INL = "{of: [v_refer, from], with: quality}"
A = lambda mod: f"  zz_a: {{display: 試しA, extends: symmetry_break, mod: {mod}}}\n"
B = lambda mod: f"  zz_b: {{display: 試しB, extends: implementation_break, mod: {mod}}}\n"
CASES = {
    "B": "",
    "N": ZM + A("zz_m") + B("zz_m"),
    "M": ZM + A("zz_m") + B(INL),
    "I": ZM + A(INL) + B(INL),
    "S": A(INL) + B(INL),
}

TC_OLD_LOOP = '''            for m in n.get("mod") or []:
                t = dump(m) if isinstance(m, dict) else m
                add("mod", nid, t)
'''
TC_NEW_LOOP = '''            for i_m, m in enumerate(n.get("mod") or []):
                t = dump(m) if isinstance(m, dict) else m
                add("mod", nid, t)
                if (nid, i_m) in self.mod_name:
                    add("mod_by_name", nid, t)
'''
TC_OLD_EXISTS = '''            add("exists", nid)
'''
TC_NEW_EXISTS = '''            add("exists", nid)
            if "of" in n and not self.is_verb(nid):
                add("mod_content", nid, dump({k: n[k] for k in ("of", "with", "neg", "at") if k in n}))
'''
SYN_IND = '''  mod_by_name: {is: law_relation, display: 修飾を名前で書いた}
  mod_content: {is: law_relation, display: 名前を付けた修飾語の中身である}
  r_named_content: {is: law_relation, display: 名前のある中身である}
  named_content: {is: law_rule, display: 名前を付けた修飾語の中身には名前がある}
  named_mod_use: {is: law_rule, display: 名前のある中身は名前で書く}
  named_mod_share: {is: law_rule, display: 二つのノードが同じ中身を足すなら、その中身には名前がある}
'''
SYN_FACTS = '''  - {is: v_assume, from: named_content, to: {is: mod_content, from: var1, to: var2}}
  - {is: v_derive, from: named_content, to: {is: r_named_content, from: var2}}
  - {is: v_assume, from: named_mod_use, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: named_mod_use, to: {is: mod_content, from: var3, to: var2}}
  - {is: v_require, from: named_mod_use, to: {is: mod_by_name, from: var1, to: var2}}
  - {is: v_assume, from: named_mod_share, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: named_mod_share, to: {is: mod, from: var3, to: var2}}
  - {is: v_assume, from: named_mod_share, to: {is: same, from: var1, to: var3, neg: true}}
  - {is: v_require, from: named_mod_share, to: {is: r_named_content, from: var2}}
  - {is: v_govern, from: named_mod_use, to: concept_expression}
  - {is: v_govern, from: named_mod_share, to: concept_expression}
'''
SYN_IND_ANCHOR = "  named_mod: {is: law_given, display: 2つ以上の概念が同じ限定を足すなら、その限定は名前を付けた修飾語で書く}\n"
SYN_FACTS_ANCHOR = "  - {is: v_govern, from: named_mod, to: concept_expression}\n"

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
        patch(d / TC, TC_OLD_LOOP, TC_NEW_LOOP)
        patch(d / TC, TC_OLD_EXISTS, TC_NEW_EXISTS)
        patch(d / SYN, SYN_IND_ANCHOR, SYN_IND_ANCHOR + SYN_IND)
        patch(d / SYN, SYN_FACTS_ANCHOR, SYN_FACTS_ANCHOR + SYN_FACTS)
        if CASES[case]:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + CASES[case])
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return ["probe failed: " + r.stderr[-300:]]


def py_nodes(e):
    m = re.search(r"named_mod に反する: (.*?) (の限定は|が同じ限定)", e)
    return set(m.group(1).split(", ")) if m else set()


def rule_node(e):
    m = re.search(r"var1=([^,\s]+)", e)
    return {m.group(1)} if m else set()


def main():
    summary, texts = {}, {}
    for c in CASES:
        errs = run(c)
        py = [e for e in errs if "法則 named_mod に反する" in e]
        rule = [e for e in errs if "法則 named_mod_use" in e or "法則 named_mod_share" in e]
        other = [e for e in errs if e not in py and e not in rule]
        pyn = set().union(*map(py_nodes, py)) if py else set()
        rn = set().union(*map(rule_node, rule)) if rule else set()
        summary[f"py_{c}"] = len(py)
        summary[f"rule_{c}"] = len(rule)
        summary[f"agree_{c}"] = int(pyn == rn)
        summary[f"other_{c}"] = len(other)
        texts[f"errors {c}"] = (py + rule + other)[:6]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
