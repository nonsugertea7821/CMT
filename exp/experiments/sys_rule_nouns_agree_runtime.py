"""h_rule_nouns_agree_runtime を確かめる: 法則の役割の名詞を中身（名前のある中身）で書くと、
premise↔pre_rule、derived↔post_rule、required↔law_check が対で一致するか。

仮説（claims.yaml）: 登録 b59003b（#486）。
訂正（結果を見る前、この commit で）: 登録の式は v_agree(from: [premise, derived, required],
  to: [pre_rule, post_rule, law_check]) だった。体系は from と to の並びを直積で読む（sync_issues の題が
  9 つの対を並べた）ので、式は 9 つの対の一致を述べていた。登録の commit のメッセージが述べる読みは
  対応する 3 つの対である。式を 3 つの v_refer（一つの対ずつ）に書き直す。h_layers_unhardcode が
  一つの仮説から v_refer を二つ出しており、型検査が通すことは分かっている。
  訂正があるので、この PR は手で見てもらう。

手順（体系のファイルは変えない。写しの上で測る）:
  変種 N: #484 の変種 N（sys_rule_roles_by_named_mod の edit_system と edit_checker）。判定に使う。
  変種 L: main の写し。参照として報告する。
  各変種で、#485（sys_premise_agrees_pre_rule）と同じく、build の後に law_rules を評価し、関係 refer を集める。
    R(x) = {y : refer(x, y)}、n_src(y) = |{x : refer(x, y)}|。
    対 (a, b) の共通の相手 C = R(a) ∩ R(b)。n_src(y) <= 20 の y を「特定の共通の相手」とする（#485 と同じ閾値）。
  対: 対角 3 つ（premise・pre_rule、derived・post_rule、required・law_check）と、直積の残り 6 つ（報告だけ）。
  行（sys_rule_nouns_agree_runtime.json）: "variant N/L": {errors, R, pairs: {a|b: {C, n_specific}}}、"summary 要約"。

判定（事前に決める。N について）:
  N の errors が 0 でなければ外れ（判定しない）。
  支持: 対角 3 つの対すべてで、特定の共通の相手が 1 つ以上ある。
  反証: 対角のうち、特定の共通の相手がない対が 1 つ以上ある。

開示（結果を見る前に分かっていること）:
  - #485 で、N の premise・pre_rule の対は特定の共通の相手 pre（n_src 5）を持つと見ている。
  - runtime.yaml で post_rule の mod は refer_from_post、law_check の mod は refer_from_laws。N では derived の mod は
    refer_from_post、required の mod は refer_from_always。よって 3 つ目の対は外れると予想しており、
    登録の PR の本文にもそう書いた。
使い方:
  python exp/experiments/sys_rule_nouns_agree_runtime.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_nouns_agree_runtime.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV
import sys_rule_roles_by_named_mod as NM

LIMIT = 20
NOUNS = ["syntax.premise", "syntax.derived", "syntax.required"]
RUNS = ["runtime.pre_rule", "runtime.post_rule", "runtime.law_check"]
PROBE = r'''
import contextlib, io, json, sys
from collections import Counter
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
errs = len(tc.errors)
F = tc.Facts(T.syntax_facts())
tc.evaluate(tc.law_rules(O), F, tc.variables(O))
rows = set(tuple(str(v) for v in x) for x in F.by.get("refer", []) if len(x) == 2)
n_src = Counter(y for x, y in rows)
W = %r
R = {w: sorted({y for x, y in rows if x == w}) for w in W}
print(json.dumps({"errors": errs, "R": R, "n_src": {y: n_src[y] for w in W for y in R[w]}}, ensure_ascii=False))
''' % (NOUNS + RUNS,)


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "stderr": r.stderr[-800:], "R": {}, "n_src": {}}
    return json.loads(out[-1])


def pairs(r):
    out = {}
    for i, a in enumerate(NOUNS):
        for j, b in enumerate(RUNS):
            C = {y: r["n_src"][y] for y in sorted(set(r["R"].get(a, [])) & set(r["R"].get(b, [])))}
            out[f"{a}|{b}"] = {"diag": int(i == j), "C": C, "n_specific": sum(1 for v in C.values() if v <= LIMIT)}
    return out


def main():
    rows = {}
    for k in ("N", "L"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {}
            if k == "N":
                e["system"] = NM.edit_system(d)
                e["checker"] = NM.edit_checker(d)
            r = probe(d)
            rows[f"variant {k}"] = {"errors": r["errors"], "R": r["R"], "pairs": pairs(r) if r["R"] else {}, "edits": e}
    s = {"limit": LIMIT}
    for k in ("N", "L"):
        v = rows[f"variant {k}"]
        s[f"{k}_errors"] = v["errors"]
        dg = [p for p in v["pairs"].values() if p["diag"]]
        od = [p for p in v["pairs"].values() if not p["diag"]]
        s[f"{k}_diag_agree"] = sum(1 for p in dg if p["n_specific"] >= 1)
        s[f"{k}_off_agree"] = sum(1 for p in od if p["n_specific"] >= 1)
        for n, r_ in zip(("pre", "post", "law"), RUNS):
            a = NOUNS[RUNS.index(r_)]
            s[f"{k}_{n}_specific"] = v["pairs"].get(f"{a}|{r_}", {}).get("n_specific", -1)
    s["verdict"] = "外れ" if s["N_errors"] != 0 else ("支持" if s["N_diag_agree"] == 3 else "反証")
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("N", "L"):
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:1500])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
