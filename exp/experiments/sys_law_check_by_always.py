"""h_law_check_by_always を確かめる: 法則を確かめる時点（runtime.law_check）の中身を、どのステップでも
成り立つ状態の指定（always）で書くと、法則が求める文（required）と一致し、ほかは変わらないか。

仮説（claims.yaml）: v_refer(h, v_depend(runtime.law_check, syntax.always))。登録 #489。
  出どころ #488（h_rule_nouns_agree_runtime、反証）: 名前のある中身の変種 N で、required は always を、
  law_check は laws を指し、共通の相手がなかった。対の仮説 h_required_by_laws（#491）は別の PR で確かめる。

手順（体系のファイルは変えない。写しの上で変える）:
  変種 N: #484 の変種 N（sys_rule_roles_by_named_mod の edit_system と edit_checker）。基準。
  変種 A: N に加えて、runtime.yaml の law_check の mod を refer_from_laws から refer_from_always に変える。
  測るもの（各変種）: #478 の PROBE（errors、ec_errors、laws_hash、rel）。rel の refer の行から
    R(x) = {y : refer(x, y)}、n_src(y) を作り、#488 と同じく 9 つの対
    （[premise, derived, required] × [pre_rule, post_rule, law_check]）の特定の共通の相手（n_src <= 20）を数える。
  行（sys_law_check_by_always.json）: "variant N/A": {errors, ec_errors, laws_hash, R, pairs}、"summary 要約"。

判定（事前に決める。A について）:
  支持: A の errors = 0、ec_errors = 0、laws_hash が N と同じ、対角の一致が 3、対角でない一致が 0、
    always が R(law_check) にある。
  1 つでも外れれば反証。N の errors が 0 でなければ外れ（判定しない）。

開示: #488 で N の R と対の値を見ている（対角 2、対角でない 0、required → always、law_check → laws）。
使い方:
  python exp/experiments/sys_law_check_by_always.py
"""
import ast
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_law_check_by_always.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV
import sys_rule_roles_by_named_mod as NM

LIMIT = 20
NOUNS = ["syntax.premise", "syntax.derived", "syntax.required"]
RUNS = ["runtime.pre_rule", "runtime.post_rule", "runtime.law_check"]
EDIT_A = ("  law_check: {display: 法則を確かめる時点, extends: strategy, mod: refer_from_laws}",
          "  law_check: {display: 法則を確かめる時点, extends: strategy, mod: refer_from_always}")


def edit_runtime(d, edit):
    p = d / "cscl/library/runtime/runtime.yaml"
    t = p.read_text(encoding="utf-8")
    n = t.count(edit[0])
    p.write_text(t.replace(edit[0], edit[1]), encoding="utf-8")
    return n


def measure(r):
    rows = set()
    for x in r.get("rel") or []:
        if x.startswith("refer:"):
            v = ast.literal_eval(x[len("refer:"):])
            if isinstance(v, tuple) and len(v) == 2:
                rows.add(v)
    n_src = Counter(y for _, y in rows)
    R = {w: sorted({y for x, y in rows if x == w}) for w in NOUNS + RUNS}
    pairs = {}
    for i, a in enumerate(NOUNS):
        for j, b in enumerate(RUNS):
            C = {y: n_src[y] for y in sorted(set(R[a]) & set(R[b]))}
            pairs[f"{a}|{b}"] = {"diag": int(i == j), "C": C, "n_specific": sum(1 for v in C.values() if v <= LIMIT)}
    diag = sum(1 for p in pairs.values() if p["diag"] and p["n_specific"] >= 1)
    off = sum(1 for p in pairs.values() if not p["diag"] and p["n_specific"] >= 1)
    return {"errors": r.get("errors"), "ec_errors": r.get("ec_errors"), "err_text": r.get("err_text"),
            "laws_hash": r.get("laws_hash"), "R": R, "pairs": pairs, "diag_agree": diag, "off_agree": off}


def run(extra, out):
    res = {}
    for k in ("N", "X"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {"system": NM.edit_system(d), "checker": NM.edit_checker(d)}
            if k == "X":
                e["extra"] = extra(d)
            res[k] = {**measure(PREV.probe(d)), "edits": e}
    N, X = res["N"], res["X"]
    s = {"N_errors": N["errors"], "X_errors": X["errors"], "X_ec_errors": X["ec_errors"],
         "X_laws_same": int(X["laws_hash"] == N["laws_hash"]), "N_diag_agree": N["diag_agree"],
         "X_diag_agree": X["diag_agree"], "X_off_agree": X["off_agree"], "X_extra_edits": X["edits"].get("extra")}
    return res, s


def write(out, res, s, names):
    rows = {f"variant {names[k]}": v for k, v in res.items()}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(names[k], json.dumps({m: v[m] for m in ("errors", "ec_errors", "err_text", "laws_hash", "R", "diag_agree", "off_agree")}, ensure_ascii=False)[:900])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


def main():
    res, s = run(lambda d: edit_runtime(d, EDIT_A), OUT)
    s["X_always_in_R"] = int("syntax.always" in res["X"]["R"]["runtime.law_check"])
    s["verdict"] = ("外れ" if s["N_errors"] != 0 else
                    "支持" if (s["X_errors"] == 0 and s["X_ec_errors"] == 0 and s["X_laws_same"] == 1 and s["X_diag_agree"] == 3
                              and s["X_off_agree"] == 0 and s["X_always_in_R"] == 1) else "反証")
    write(OUT, res, s, {"N": "N", "X": "A"})


if __name__ == "__main__":
    main()
