"""h_rule_frame_redundant を確かめる: 枠の中身を、すでに導かれている文にすれば、導いた関係は変わらないか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.pre, syntax.post, syntax.holds, syntax.law_relation])。
  登録（d57c16d）の読み: 枠の中身を、すでに導かれている文（冗長な文）にすれば、役割を枠から読んでも関係は変わらない。
  h_frame_enters_relations（#343）で、#339 の関係の差は足した枠そのものから来ると分かった。

手順（体系のファイルは変えない。写しの上で変える。#339 のスクリプトの copy_tree・edit_checker・PROBE を使う）:
  変種:
    L   そのまま。
    F   #339・#343 と同じ枠（v_assume に pre、v_derive に post、v_require に holds。中身は {is: v_refer, from: from, to: to}）。
    R   枠の位置は F と同じ。中身を {is: refer, from: from, to: to} にする。これは v_refer の holds と同じ文で、
        v_assume・v_derive・v_require が v_refer を上位に持つことで、すでに成り立つとされている文。
    RU  R に、#339 の型検査の置き換え（役割を枠から読む）を重ねる。
  測るもの（各変種）: #339 の PROBE と同じ（errors, ec_errors, laws_hash, rel_hash, n_rel, n_role）。
    加えて n_concept_verb: 導いた関係で、r_concept と r_verb の両方に入る項の数。
  行（sys_rule_frame_redundant.json）: "variant L/F/R/RU": {...}, "summary 要約": {...}
    summary: R_rel_eq_L, RU_rel_eq_L, RU_laws_eq_L, RU_errors, RU_ec_errors, RU_n_role,
             n_concept_verb_L, n_concept_verb_R, F_rel_eq_R
判定（事前に決める）:
  RU_errors = 0、RU_ec_errors = 0、RU_laws_eq_L = 1、RU_n_role = 3 で、RU_rel_eq_L = 1 なら支持。RU_rel_eq_L = 0 なら反証。
  （n_role が 3 でなければ、役割を枠から読めていないので外れ。状態は変えない。）

開示（結果を見る前に分かっていること。手順を決めるために、L と F の導いた関係の差を写しの上で調べた）:
  - 消えた 355 件は、r_concept(syntax.v_assume)・r_concept(syntax.v_require) と、それを前提にした
    r_pair・r_near・r_candidate・r_lacks・r_differ・r_missing だった。増えたのは holds(syntax.v_require, 0) の 1 件。
  - 法則 concept_kind は、自分の holds・pre を持たない（上位から受け継いだものは見ない）ことを r_concept の前提にしている。
    枠の中身ではなく、鍵 pre・holds があることで r_concept が外れる。post は concept_kind の前提にないので、
    v_derive は r_concept に残る。
  - そのため、中身を変えても R の関係は L と違う、と予想している（反証の予想）。
  - L では、v_assume・v_derive・v_require が、r_verb（v_refer から受け継ぐ）と r_concept の両方に入っている。
  - 型検査は 4 回走る。
使い方:
  python exp/experiments/sys_rule_frame_redundant.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_frame_redundant.json"
XR = "{is: refer, from: from, to: to}"

EXTRA = r'''
try:
    _c = [k for k in F.by if k.split(".")[-1] == "r_concept"]
    _v = [k for k in F.by if k.split(".")[-1] == "r_verb"]
    _sc = set().union(*[set(map(str, F.by[k])) for k in _c]) if _c else set()
    _sv = set().union(*[set(map(str, F.by[k])) for k in _v]) if _v else set()
    n_cv = len(_sc & _sv)
except Exception as e:
    n_cv = -1
'''


def base():
    spec = importlib.util.spec_from_file_location("unhardcode", ROOT / "exp/experiments/sys_rule_verbs_unhardcode.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def edit_syntax(B, dst, content):
    p = dst / "cscl/library/syntax/syntax.yaml"
    lines = p.read_text(encoding="utf-8").split("\n")
    done = 0
    for i, l in enumerate(lines):
        for v, k in B.EDITS.items():
            if l.startswith(f"  {v}: {{") and l.endswith("}"):
                lines[i] = l[:-1] + f", {k}: [{content}]}}"
                done += 1
    p.write_text("\n".join(lines), encoding="utf-8")
    return done


def probe(B, d):
    head, tail = B.PROBE.split("print(json.dumps({\"errors\": len(errs)")
    code = head + EXTRA + "print(json.dumps({\"n_concept_verb\": n_cv, \"errors\": len(errs)" + tail
    r = subprocess.run([sys.executable, "-c", code], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "ec_errors": -1, "stderr": r.stderr[-800:]}
    return json.loads(out[-1])


def main():
    B = base()
    res, edits = {}, {}
    for k in ("L", "F", "R", "RU"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            B.copy_tree(d)
            e = {}
            if k == "F":
                e["syntax"] = edit_syntax(B, d, B.X)
            if k in ("R", "RU"):
                e["syntax"] = edit_syntax(B, d, XR)
            if k == "RU":
                e["checker"] = B.edit_checker(d)
            edits[k] = e
            res[k] = probe(B, d)
    L, F, R, RU = (res[k] for k in ("L", "F", "R", "RU"))
    s = {"R_rel_eq_L": int(R.get("rel_hash") == L.get("rel_hash")),
         "RU_rel_eq_L": int(RU.get("rel_hash") == L.get("rel_hash")),
         "RU_laws_eq_L": int(RU.get("laws_hash") == L.get("laws_hash")),
         "RU_errors": RU.get("errors"), "RU_ec_errors": RU.get("ec_errors"), "RU_n_role": RU.get("n_role"),
         "n_concept_verb_L": L.get("n_concept_verb"), "n_concept_verb_R": R.get("n_concept_verb"),
         "F_rel_eq_R": int(F.get("rel_hash") == R.get("rel_hash")),
         "n_rel_L": L.get("n_rel"), "n_rel_F": F.get("n_rel"), "n_rel_R": R.get("n_rel"), "n_rel_RU": RU.get("n_rel")}
    valid = s["RU_n_role"] == 3
    sup = valid and s["RU_errors"] == 0 and s["RU_ec_errors"] == 0 and s["RU_laws_eq_L"] == 1 and s["RU_rel_eq_L"] == 1
    rows = {f"variant {k}": {**res[k], "edits": edits[k]} for k in res}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:400])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "外れ（役割を読めていない）" if not valid else ("支持" if sup else "反証"))


if __name__ == "__main__":
    main()
