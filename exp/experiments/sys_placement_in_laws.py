"""仮説 h_placement_in_laws（上位で決まる置き場は型検査器に依存しない）を確かめる: 検査器のコードが決めている
置き場の検査のうち 3 つを、上位（r_below）を使う規則の法則（v_require）に移しても、同じ書き換えの誤りを同じに見分け、
今の体系では誤りを出さないか。結果を見る前に、この説明と手順を登録した。

範囲（3 つ。どれも Ontology.check の中の検査）:
  V 動詞は生起体の下に置く      （is_verb なら is_a(top_o)）
  M 修飾語は特定依存持続体の下に置く（of を持つノードは is_a(sdc)）
  X axis を持てるのは質だけ      （axis を持つノードは is_a(quality)）
  ほかの置き場の検査（役割と定義、個数と大きさ、最上位、gloss）は対象にしない。
操作（一時の写しで行う。体系のファイルと検査器は書き換えない）:
  syntax.yaml の写しに、規則の法則を足す:
    place_verb: r_verb(x) を前提に、r_below(x, occurrent) を求める
    place_mod:  exists(x), of(x, v) を前提に、r_below(x, specifically_dependent_continuant) を求める
    place_axis: exists(x), axis(x, a) を前提に、r_below(x, quality) を求める
  版（claims.yaml の写しの nodes に試しのノードを足す。Q0 は足さない）:
    Q0 足さない
    Q1 生起体の下にない動詞:   zz_v: extends quality, holds [refer from→to]
    Q2 生起体の下の動詞:       zz_v: extends occurrent, from continuant, holds [refer from→to]
    Q3 質の下にない修飾語:     zz_m: extends continuant, of [v_refer, from], with quality
    Q4 質の下の修飾語:         zz_m: extends quality, of [v_refer, from], with continuant
    Q5 質の下にない axis:     zz_x: extends continuant, axis amount, mod {of: [v_refer, from], with: quality}
    Q6 質の下の axis:         zz_x: extends quality, axis amount, mod {of: [v_refer, from], with: continuant}
数える量（版ごと。tc の build を写しで 1 回）:
  py_<v>   検査器の置き場の誤り（「動詞は生起体の下に置く」「修飾語は特定依存持続体の下に置く」「axis を持てるのは質だけ」）の数
  law_<v>  place_verb, place_mod, place_axis の誤りの数
  other_<v> それ以外の誤りの数（記述）
  agree    py_<v> = law_<v> の版の数（7 のうち）
判定（事前に決める）:
  agree = 7 かつ law_Q0 = 0 なら支持。agree < 7 か law_Q0 > 0 なら反証。
  Q1・Q3・Q5 で py ≥ 1、Q0・Q2・Q4・Q6 で py = 0 にならない（版の作りが見込みと違う）なら mixed。
行（sys_placement_in_laws.json）:
  "summary 要約": agree と、版ごとの py_<v>, law_<v>, other_<v>
  "texts": 版ごとの誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_placement_in_laws.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_placement_in_laws.json"
SYN, CLAIMS = "cscl/library/syntax/syntax.yaml", "cscl/design/claims.yaml"

LAW_IND_ANCHOR = "  definition_stratified: {is: law_given, display: 定義の循環は否定の限定を通らない（自分を限定するものは肯定の位置にだけ現れる）}\n"
LAW_INDS = ("  place_verb: {is: law_rule, display: 動詞は生起体の下に置く（法則）}\n"
            "  place_mod: {is: law_rule, display: 修飾語は特定依存持続体の下に置く（法則）}\n"
            "  place_axis: {is: law_rule, display: 軸を持てるのは質だけ（法則）}\n")
LAW_FACT_ANCHOR = "  - {is: v_require, from: acyclic, to: {is: same, from: var1, to: var2, neg: true}}\n"
LAW_FACTS = ("  - {is: v_assume, from: place_verb, to: {is: r_verb, from: var1}}\n"
             "  - {is: v_require, from: place_verb, to: {is: r_below, from: var1, to: occurrent}}\n"
             "  - {is: v_assume, from: place_mod, to: {is: exists, from: var1}}\n"
             "  - {is: v_assume, from: place_mod, to: {is: of, from: var1, to: var2}}\n"
             "  - {is: v_require, from: place_mod, to: {is: r_below, from: var1, to: specifically_dependent_continuant}}\n"
             "  - {is: v_assume, from: place_axis, to: {is: exists, from: var1}}\n"
             "  - {is: v_assume, from: place_axis, to: {is: axis, from: var1, to: var2}}\n"
             "  - {is: v_require, from: place_axis, to: {is: r_below, from: var1, to: quality}}\n")

NODE_ANCHOR = "  negated_limitation: {display: 否定の限定, extends: quality, mod: {of: [v_refer, from], with: syntax.neg}}\n"
CASES = {
    "Q0": "",
    "Q1": "  zz_v: {display: 試しV, extends: quality, holds: [{is: refer, from: from, to: to}]}\n",
    "Q2": "  zz_v: {display: 試しV, extends: occurrent, from: continuant, holds: [{is: refer, from: from, to: to}]}\n",
    "Q3": "  zz_m: {display: 試しM, extends: continuant, of: [v_refer, from], with: quality}\n",
    "Q4": "  zz_m: {display: 試しM, extends: quality, of: [v_refer, from], with: continuant}\n",
    "Q5": "  zz_x: {display: 試しX, extends: continuant, axis: amount, mod: {of: [v_refer, from], with: quality}}\n",
    "Q6": "  zz_x: {display: 試しX, extends: quality, axis: amount, mod: {of: [v_refer, from], with: continuant}}\n",
}
PY_MSGS = ("動詞は生起体の下に置く", "修飾語は特定依存持続体の下に置く", "axis を持てるのは質だけ")
LAWS = ("place_verb", "place_mod", "place_axis")

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
PY_MSGS, LAWS = %r, %r
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        tc.build()
        crash = ""
    except Exception as e:
        crash = repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
law = [e for e in errs if any("法則 " + l + "（" in e for l in LAWS)]
py = [e for e in errs if e not in law and any(m in e for m in PY_MSGS)]
other = [e for e in errs if e not in py and e not in law]
print(json.dumps({"py": len(py), "law": len(law), "other": len(other), "texts": (py + law + other)[:6]}, ensure_ascii=False))
''' % (PY_MSGS, LAWS)


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
        p.write_text(put(put(p.read_text(), LAW_IND_ANCHOR, LAW_INDS), LAW_FACT_ANCHOR, LAW_FACTS))
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
    summary["agree"] = sum(summary[f"py_{c}"] == summary[f"law_{c}"] for c in CASES)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
