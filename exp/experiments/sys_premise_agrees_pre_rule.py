"""h_premise_agrees_pre_rule を確かめる: 法則の前提（syntax.premise）と、実行器の前の状態の確かめ方
（runtime.pre_rule）は、式の上で一致するか。

仮説（claims.yaml）: v_refer(h, v_agree(syntax.premise, runtime.pre_rule))。登録 a627c49（#479）。
  v_agree の holds は refer(from, new) と refer(to, new)。よって「一致する」は、型検査が導く refer の関係で、
  両者が同じ相手を指すことである。

手順（体系のファイルは変えない。写しの上で測る）:
  変種 L: main の写しをそのまま（判定に使う）。
  変種 N: #484 の変種 N（premise と pre_rule の mod を名前のある中身 refer_from_pre で書き、型検査の役割の
    読みを RULE_ROLE にしたもの）。sys_rule_roles_by_named_mod の edit_system と edit_checker をそのまま使う。
    判定に使わない（どう直せば一致するかの参照）。
  各変種で、型検査の build の後、Facts(syntax_facts) に law_rules を評価し、関係 refer の行を集める。
    A = {y : refer(syntax.premise, y)}、B = {y : refer(runtime.pre_rule, y)}、C = A ∩ B。
    n_src(y) = |{x : refer(x, y)}|。C の y のうち n_src(y) <= 20 のものを「特定の共通の相手」とする。
  行（sys_premise_agrees_pre_rule.json）: "variant L/N": {errors, A, B, C（各 y と n_src）, n_specific}、
    "summary 要約"。

判定（事前に決める。L について）:
  支持: L の errors = 0 で、特定の共通の相手が 1 つ以上ある。
  反証: L の errors = 0 で、特定の共通の相手がない。
  L の errors が 0 でなければ外れ（判定しない）。
  閾値 20 は、体系の語の数に比べて小さい数として置いた。C の全体と n_src は報告する。

開示（結果を見る前に分かっていること）:
  - 手順を決めるために、main で premise と pre_rule が現れる関係の名前と先頭の行を、結果ファイルを書かない
    下見で見た。refer の行は premise と pre_rule で合わせて 9 あり、そのうち 4 行
    （pre_rule→pre、premise→sentence_refer_from_state_relation・law_rule・v_assume）を見た。残りは見ていない。
  - main で premise の mod は {of: [v_assume, to], with: law_rule}、pre_rule の mod は
    {of: [v_refer, from], with: pre} で、中身は違う。登録の読みは #478 の変種（premise の mod を pre にしたもの）
    で named_mod_share が落ちたことから出ており、main の式で一致するとは確かめていない。反証を予想しうる。
使い方:
  python exp/experiments/sys_premise_agrees_pre_rule.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_premise_agrees_pre_rule.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV
import sys_rule_roles_by_named_mod as NM

LIMIT = 20
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
rows = [tuple(str(v) for v in x) for x in F.by.get("refer", [])]
n_src = Counter(y for x, y in set((r[0], r[1]) for r in rows if len(r) == 2))
A = sorted({r[1] for r in rows if len(r) == 2 and r[0] == "syntax.premise"})
B = sorted({r[1] for r in rows if len(r) == 2 and r[0] == "runtime.pre_rule"})
C = {y: n_src[y] for y in sorted(set(A) & set(B))}
print(json.dumps({"errors": errs, "A": A, "B": B, "C": C}, ensure_ascii=False))
'''


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "stderr": r.stderr[-800:], "A": [], "B": [], "C": {}}
    return json.loads(out[-1])


def main():
    rows = {}
    for k in ("L", "N"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {}
            if k == "N":
                e["system"] = NM.edit_system(d)
                e["checker"] = NM.edit_checker(d)
            r = probe(d)
            r["n_specific"] = sum(1 for v in r["C"].values() if v <= LIMIT)
            r["edits"] = e
            rows[f"variant {k}"] = r
    L = rows["variant L"]
    s = {"L_errors": L["errors"], "L_n_common": len(L["C"]), "L_n_specific": L["n_specific"],
         "N_errors": rows["variant N"]["errors"], "N_n_common": len(rows["variant N"]["C"]),
         "N_n_specific": rows["variant N"]["n_specific"], "limit": LIMIT}
    s["verdict"] = "外れ" if L["errors"] != 0 else ("支持" if L["n_specific"] >= 1 else "反証")
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("L", "N"):
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:800])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
