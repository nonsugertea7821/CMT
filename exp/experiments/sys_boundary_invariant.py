"""h_boundary_invariant を確かめる: 型検査器の結論は、変化を前の側（pre）で読むか後の側（post）で読むかに依存しないか。

仮説（claims.yaml）: v_not_depend(type_checker, boundary_choice)。
  変化の境目では、値は左の極限（pre）と右の極限（post）の二つがあり、境目そのものの値は決まらない。
  どちらの取り方でも成り立たなければ、取り方への依存は誤りの合図、という利用者の読み。
  今の検査器は、syntax_facts で holds と pre の番号だけを事実にし（post は事実にしない）、
  法則 3 つ（concept_kind・root_kind・verb_by_pre）が pre の事実を前提に使う。これは「前の側で読む」取り方にあたる。
  h_appear_root（#322、支持）は、出現の分類が pre で決まることを示した。ここではその読みが取り方によらないかを見る。

手順（体系のファイルは変えない。cscl.yaml・cscl・exp/src を一時の場所に写し、exp/experiments/results は写しから辿れるように繋ぐ）:
  変種:
    L  書き換えない（前の側で読む）。
    R  写しの type_checker.py で、事実にする鍵 ("holds", "pre") を ("holds", "post") に替え、
       写しの syntax.yaml で、法則の前提の {is: pre, ...} 3 つを {is: post, ...} に替える（後の側で読む）。
    B  写しの type_checker.py で、鍵を ("holds", "pre", "post") にする（両方を事実にする。法則はそのまま）。記述。
  それぞれの写しで、tc.build と exp の検査を走らせ、法則を閉じた事実を数える:
    errors, ec_errors     誤りの数
    rel                   関係ごとの文の数とハッシュ（pre と post の関係は除く）
    side                  pre（L・B）か post（R）の事実を持つノードの集まり
  L と比べて: changed（ハッシュが違う関係の数）, side_diff（L の side と、その変種の side の対称差の大きさ）
  記述: pre だけを持つ動詞の数、post だけを持つ動詞の数（体系のノードを数える）。
判定（変種 R で決める）:
  R の errors・ec_errors が L と同じで、changed 0、side_diff 0 なら支持。
  R の errors か ec_errors が L と違えば、内容を見る: 書き換えの不備（名前が解決しない等）なら外れ（状態は変えない）。
  そうでなく、errors・ec_errors・changed・side_diff のどれかが 0 でなければ反証。

開示（結果を見る前に分かっていること）:
  - syntax.yaml の pre と post の定義は鏡の形（どちらも holds の下で、互いに前・後に置かれる）。
  - h_appear_root の結果では、出現の形を持つ 20 の動詞は、どれも pre と post の両方を持っていた。
    pre だけ・post だけを持つ動詞があるかは数えていない。
  - 事実は番号（何番目の原子か）を持つ。pre と post で原子の数が違う動詞では、R で番号の集まりが変わる。
    法則が番号を使うかは見ていない。
  - 型検査を 3 回走らせる（重い作業はこれ 1 つ）。
使い方:
  python exp/experiments/sys_boundary_invariant.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_boundary_invariant.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
KEY = '            for k in ("holds", "pre"):\n'
R_TC = [(KEY, '            for k in ("holds", "post"):\n')]
B_TC = [(KEY, '            for k in ("holds", "pre", "post"):\n')]
R_SYN = [("to: {is: pre, from: var1, to: var3, neg: true}}", "to: {is: post, from: var1, to: var3, neg: true}}"),
         ("to: {is: pre, from: var1, to: var2, neg: true}}", "to: {is: post, from: var1, to: var2, neg: true}}"),
         ("to: {is: pre, from: var1, to: var2}}", "to: {is: post, from: var1, to: var2}}")]

PROBE = r'''
import contextlib, hashlib, io, json, sys
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
rel, side = {}, set()
for r, xs in F.by.items():
    if r.split(".")[-1] in ("pre", "post"):
        side |= {t[0] for t in xs}
        continue
    keep = sorted(str(x) for x in xs)
    if keep:
        rel[r] = [len(keep), hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]]
pre_only = sum(1 for n in T.N.values() if "pre" in n and "post" not in n)
post_only = sum(1 for n in T.N.values() if "post" in n and "pre" not in n)
print(json.dumps({"errors": len(errs), "ec_errors": ec, "err_text": errs[:10], "rel": rel, "side": sorted(side),
                  "pre_only": pre_only, "post_only": post_only}, ensure_ascii=False))
'''


def edit(path, pairs):
    s = path.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, old
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


def variant(tc_edits, syn_edits):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        (Path(d) / "exp/experiments").mkdir(parents=True, exist_ok=True)
        os.symlink(ROOT / "exp/experiments/results", Path(d) / "exp/experiments/results")
        edit(Path(d) / TC, tc_edits)
        edit(Path(d) / SYN, syn_edits)
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    res = {"L": variant([], []), "R": variant(R_TC, R_SYN), "B": variant(B_TC, [])}
    L = res["L"]
    rows = {}
    for k, r in res.items():
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "n_side": len(r["side"]),
                                "side_diff": len(set(r["side"]) ^ set(L["side"])),
                                "changed": sum(1 for x in set(r["rel"]) | set(L["rel"]) if r["rel"].get(x) != L["rel"].get(x)),
                                "changed_rel": sorted(x for x in set(r["rel"]) | set(L["rel"]) if r["rel"].get(x) != L["rel"].get(x))[:20],
                                "err_text": r["err_text"]}
    R = rows["variant R"]
    support = R["errors"] == L["errors"] and R["ec_errors"] == L["ec_errors"] and not R["changed"] and not R["side_diff"]
    rows["summary 要約"] = {"verdict_support": int(support), "pre_only": L["pre_only"], "post_only": L["post_only"],
                          **{f"{k}_{m}": rows[f"variant {k}"][m] for k in res for m in ("errors", "ec_errors", "changed", "side_diff")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps({m: v for m, v in rows[f"variant {k}"].items() if m != "err_text"}, ensure_ascii=False))
        for e in rows[f"variant {k}"]["err_text"]:
            print("  ", e[:200])
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if support else "反証か外れ（誤りの内容を見る）")


if __name__ == "__main__":
    main()
