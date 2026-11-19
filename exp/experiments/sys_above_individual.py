"""h_above_individual を確かめる: 個体→種類も上位（above）に入れれば、r_ind_kind を使う法則を above で書き直せ、分類は変わらないか。

仮説（claims.yaml）: 依存する(個体の深さ, 上位の順序)。登録（46dce5d）の読み: 今は個体→種類を r_ind_kind で別に持つ。
  個体→種類も above に入れれば r_ind_kind の法則を above で書き直せ、分類（違反の組）は変わらない。
  #147（h_above_closed、支持、#293 でマージ）で、above に法則 4 つ（above_by_fact・above_is_ancestor・above_asymmetric・
  above_transitive）が入った。このうち above_is_ancestor（上位は祖先である）は、個体には祖先（r_ancestor）がないので、
  個体の above と食い違う見込みがある。これを変種として分けて測る。

手順（体系のファイルは変えない。cscl.yaml・cscl・exp/src を一時の場所に写し、写しの syntax.yaml だけを書き換えて測る）:
  変種:
    before  書き換えない。
    A       法則 2 つを足し、deep_end_ind と shallow_ends_ind の r_ind_kind の前提を above に置き換える（at はそのまま）:
              above_by_ind: {is: law_rule, display: 個体の種類は、個体の上位である}
              above_by_ind_step: {is: law_rule, display: 個体の種類の祖先は、個体の上位である}
              - {is: v_assume, from: above_by_ind, to: {is: is, from: var1, to: var2}}
              - {is: v_derive, from: above_by_ind, to: {is: above, from: var1, to: var2}}
              - {is: v_assume, from: above_by_ind_step, to: {is: is, from: var1, to: var3}}
              - {is: v_assume, from: above_by_ind_step, to: {is: r_ancestor, from: var3, to: var2}}
              - {is: v_derive, from: above_by_ind_step, to: {is: above, from: var1, to: var2}}
            ind_kind_self・ind_kind_step（r_ind_kind を導く法則）は残す（他に使う法則がなくなるだけ）。
    B       A に加えて、above_is_ancestor に前提 {is: exists, from: var1} を足す（種類どうしの上位に限る。exists は種類と軸にだけある）。
  それぞれの写しで、型検査（tc.build）と exp の検査を走らせ、法則を閉じた事実から数える:
    errors, ec_errors           誤りの数
    law_errors_<法則>           誤りの文に「法則 <名>（」を含むものの数（名ごと。記述）
    shallow, deep               r_shallow・r_deep_end の導かれた概念の集合
    V                           違反の組（sys_individual_depth と同じ数え方: r_candidate のうち acc[y] ⊆ has[x] かつ acc[y] ⊄ acc[x]）
    rel                         関係ごとの文の数とハッシュ（above と r_ind_kind を除く）
    above_ind                   始点が個体（is を持つ）の above の文の数
  before と比べて: shallow_diff, deep_diff, V_diff（対称差の大きさ）, changed（ハッシュが違う関係の数）
判定（変種 B で決める）: errors 0、ec_errors 0、shallow_diff 0、deep_diff 0、V_diff 0、changed 0 なら支持。
  errors か ec_errors が 0 でなければ外れ（内容を書き、状態は変えない）。
  errors と ec_errors が 0 で、diff か changed が 0 でなければ反証。
  変種 A は記述: above_is_ancestor の誤りが above_ind と同じ数だけ出る見込み（個体は祖先を持たない）。
  A で誤りが出れば、h_above_closed の法則のままでは仮説の書き直しは通らず、上位を種類どうしに限る前提が要る、と読む。

開示（結果を見る前に分かっていること）:
  - 個体の終点を持つ概念は 14、終点の個体は 13（sys_individual_depth の下調べ、その時点の数）。
  - r_ind_kind の終点の集まりは、種類とその祖先の集まりに等しかった。A・B の above_by_ind/_step はその式を写したものなので、
    個体の above は r_ind_kind と同じ組になり、分類は変わらない見込みが高い。確かめるのは、書き換えが法則の層と食い違わないか。
  - has_by_depth は above の始点に exists を前提に持つので、個体の above の影響を受けない見込み。
  - 型検査を 3 回走らせる（重い作業はこれ1つ）。

使い方:
  python exp/experiments/sys_above_individual.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_above_individual.json"
SYN = "cscl/library/syntax/syntax.yaml"
NODE_ANCHOR = "  above_transitive: {is: law_rule, display: 上位の上位は上位である}\n"
NEW_NODES = ("  above_by_ind: {is: law_rule, display: 個体の種類は、個体の上位である}\n"
             "  above_by_ind_step: {is: law_rule, display: 個体の種類の祖先は、個体の上位である}\n")
FACT_ANCHOR = "  - {is: v_require, from: above_transitive, to: {is: above, from: var1, to: var3}}\n"
NEW_FACTS = ("  - {is: v_assume, from: above_by_ind, to: {is: is, from: var1, to: var2}}\n"
             "  - {is: v_derive, from: above_by_ind, to: {is: above, from: var1, to: var2}}\n"
             "  - {is: v_assume, from: above_by_ind_step, to: {is: is, from: var1, to: var3}}\n"
             "  - {is: v_assume, from: above_by_ind_step, to: {is: r_ancestor, from: var3, to: var2}}\n"
             "  - {is: v_derive, from: above_by_ind_step, to: {is: above, from: var1, to: var2}}\n")
REPL = [("  - {is: v_assume, from: deep_end_ind, to: {is: r_ind_kind, from: var3, to: var4, at: {count: {gt: 2}}}}\n",
         "  - {is: v_assume, from: deep_end_ind, to: {is: above, from: var3, to: var4, at: {count: {gt: 2}}}}\n"),
        ("  - {is: v_assume, from: shallow_ends_ind, to: {is: r_ind_kind, from: var3, to: var4}}\n",
         "  - {is: v_assume, from: shallow_ends_ind, to: {is: above, from: var3, to: var4}}\n")]
B_ANCHOR = "  - {is: v_assume, from: above_is_ancestor, to: {is: above, from: var1, to: var2}}\n"
B_ADD = "  - {is: v_assume, from: above_is_ancestor, to: {is: exists, from: var1}}\n"

PROBE = r'''
import collections, contextlib, hashlib, io, json, re, sys
sys.path[:0] = ["cscl/bootstrap/type_checker", "exp/src"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
errs = [str(e) for e in tc.errors]
with contextlib.redirect_stdout(io.StringIO()):
    import exp_check
    del tc.errors[:]
    try:
        exp_check.build()
    except SystemExit:
        pass
ec = len(tc.errors)
F = tc.Facts(T.syntax_facts())
tc.evaluate(tc.law_rules(O), F, tc.variables(O))
two = lambda r: {(t[0], t[1]) for t in F.by.get(r, ()) if len(t) == 2}
one = lambda name: sorted({t[0] for r, xs in F.by.items() if r.split(".")[-1] == name for t in xs})
acc, has = collections.defaultdict(set), collections.defaultdict(set)
for a, b in two("r_acc"):
    acc[a].add(b)
for a, b in two("r_has"):
    has[a].add(b)
V = sorted(f"{x}|{y}" for x, y in two("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
rel = {}
for r, xs in F.by.items():
    if r.split(".")[-1] in ("above", "r_ind_kind"):
        continue
    keep = sorted(str(x) for x in xs)
    if keep:
        rel[r] = [len(keep), hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]]
inds = {t[0] for t in F.by.get("is", ())}
laws = collections.Counter(m.group(1) for e in errs for m in [re.search(r"法則 (\S+?)（", e)] if m)
print(json.dumps({"errors": len(errs), "ec_errors": ec, "laws": dict(laws), "err_text": errs[:20],
                  "shallow": one("r_shallow"), "deep": one("r_deep_end"), "V": V, "rel": rel,
                  "above_ind": sum(1 for t in F.by.get("above", ()) if t[0] in inds)}, ensure_ascii=False))
'''


def variant(edits):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        f = Path(d) / SYN
        s = f.read_text(encoding="utf-8")
        for old, new in edits:
            assert s.count(old) == 1, old
            s = s.replace(old, new)
        f.write_text(s, encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    A = [(NODE_ANCHOR, NODE_ANCHOR + NEW_NODES), (FACT_ANCHOR, FACT_ANCHOR + NEW_FACTS)] + REPL
    B = A + [(B_ANCHOR, B_ANCHOR + B_ADD)]
    res = {"before": variant([]), "A": variant(A), "B": variant(B)}
    b0 = res["before"]
    rows = {}
    for k, r in res.items():
        d = lambda key: len(set(r[key]) ^ set(b0[key]))
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "above_ind": r["above_ind"],
                                "n_shallow": len(r["shallow"]), "n_deep": len(r["deep"]), "n_V": len(r["V"]),
                                "shallow_diff": d("shallow"), "deep_diff": d("deep"), "V_diff": d("V"),
                                "changed": sum(1 for x in set(r["rel"]) | set(b0["rel"]) if r["rel"].get(x) != b0["rel"].get(x))}
        rows[f"variant {k}"] |= {f"law_errors_{n}": c for n, c in sorted(r["laws"].items())}
        rows |= {f"error {k} {i}": {"text": e} for i, e in enumerate(r["err_text"])}
    B_ = rows["variant B"]
    if B_["errors"] or B_["ec_errors"]:
        verdict = "外れ"
    elif B_["shallow_diff"] or B_["deep_diff"] or B_["V_diff"] or B_["changed"]:
        verdict = "反証"
    else:
        verdict = "支持"
    rows["summary 要約"] = {"verdict_support": int(verdict == "支持"), **{f"{k}_{m}": rows[f"variant {k}"][m]
                          for k in res for m in ("errors", "ec_errors", "above_ind", "shallow_diff", "deep_diff", "V_diff", "changed")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False))
    for k, v in rows.items():
        if k.startswith("error"):
            print(k, v["text"][:200])
    print("判定:", verdict)


if __name__ == "__main__":
    main()
