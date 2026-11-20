"""仮説 h_law_given_as_rule（意味を検査が与える法則は、検査器に依存しない: v_not_depend(syntax.law_given, type_checker)）を、
law_given の一つ named_mod で確かめる。結果を見る前に、この説明と手順を登録した。

問い: 規則で書いた法則（law_rule）が読めるのは、検査器が作る文（syntax_facts）だけ。named_mod の判定は、
  「名前を付けた修飾語を名前で使ったか、同じ中身をその場に書いたか」で分かれる。syntax_facts は名前を付けた修飾語を
  中身に展開して書く（type_checker.py の syntax_facts、mod の節）。だから二つの書き方が同じ文になるなら、
  その文の上のどの規則も、二つに違う判定を出せない。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  claims.yaml の写しの nodes に、次の版を足す（アンカーは negated_limitation の行の後）:
    C 名前を付けた修飾語だけ:  zz_m: {display: 試しの修飾語, extends: quality, of: [v_refer, from], with: quality}
    N C に足して、二つのノードが名前で使う:
       zz_a: {display: 試しA, extends: quality, mod: zz_m}、zz_b: {display: 試しB, extends: quality, mod: zz_m}
    I C に足して、二つのノードが同じ中身をその場に書く:
       zz_a: {display: 試しA, extends: quality, mod: {of: [v_refer, from], with: quality}}、zz_b も同じ
  写しで tc.build() を 1 回走らせ、誤りと syntax_facts を読む。
数える量（版ごと）:
  py_<v>     法則 named_mod の誤りの数
  other_<v>  それ以外の誤りの数
  n_facts_<v> syntax_facts の文の数（重なりを除く）
  facts_equal_NI  N と I の syntax_facts が文の集まりとして等しければ 1
判定（事前に決める）:
  facts_equal_NI = 1 かつ py_N = 0 かつ py_I ≥ 1 かつ other_C = other_N = other_I = 0 なら反証
    （named_mod は、今の syntax_facts の上の規則では書けない。検査器が与える区別に依存する）。
  facts_equal_NI = 0 なら、この手順では妨げを示せない。状態を変えず、未検証のまま残す。
  ほかの組み合わせ（版の作りが見込みと違う）は、手順の誤りとして開示し、状態を変えない。
範囲: 残りの law_given（world_declared、part_fact_direction、part_display_explicit）はこの実験では見ない。
  definition_stratified は h_negation_formula（#408）で規則に移せた。反証は「law_given のどれも規則に移せる」の否定まで。
行（sys_law_given_as_rule.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 4）と、N と I で違う文（最大 10）

使い方:
  python exp/experiments/sys_law_given_as_rule.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_law_given_as_rule.json"
CLAIMS = "cscl/design/claims.yaml"
NODE_ANCHOR = "  negated_limitation: {display: 否定の限定, extends: quality, mod: {of: [v_refer, from], with: syntax.neg}}\n"
ZM = "  zz_m: {display: 試しの修飾語, extends: quality, of: [v_refer, from], with: quality}\n"
INL = "{of: [v_refer, from], with: quality}"
CASES = {
    "C": ZM,
    "N": ZM + "  zz_a: {display: 試しA, extends: quality, mod: zz_m}\n  zz_b: {display: 試しB, extends: quality, mod: zz_m}\n",
    "I": ZM + f"  zz_a: {{display: 試しA, extends: quality, mod: {INL}}}\n  zz_b: {{display: 試しB, extends: quality, mod: {INL}}}\n",
}

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T, O, _ = tc.build()
        facts = sorted({json.dumps([r, [str(a) for a in xs]], ensure_ascii=False) for r, xs in T.syntax_facts()})
        crash = ""
    except Exception as e:
        facts, crash = [], repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
py = [e for e in errs if "named_mod" in e]
other = [e for e in errs if e not in py]
print(json.dumps({"py": len(py), "other": len(other), "facts": facts, "texts": (py + other)[:4]}, ensure_ascii=False))
'''


def run(case):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        p = d / CLAIMS
        s = p.read_text()
        assert s.count(NODE_ANCHOR) == 1, NODE_ANCHOR
        p.write_text(s.replace(NODE_ANCHOR, NODE_ANCHOR + CASES[case]))
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        return json.loads(r.stdout.strip().splitlines()[-1])


def main():
    R = {c: run(c) for c in CASES}
    fN, fI = set(R["N"]["facts"]), set(R["I"]["facts"])
    summary = {}
    for c, r in R.items():
        summary[f"py_{c}"] = r["py"]
        summary[f"other_{c}"] = r["other"]
        summary[f"n_facts_{c}"] = len(set(r["facts"]))
    summary["facts_equal_NI"] = int(fN == fI)
    texts = {f"errors {c}": r["texts"] for c, r in R.items()}
    texts["only_N"] = sorted(fN - fI)[:10]
    texts["only_I"] = sorted(fI - fN)[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
