"""h_family_refers_laws を確かめる: 測定の族は、変種で変えた法則を、体系の中で参照（v_refer）できるか。

仮説（exp.yaml）: 述べる(測定の族, 法則)。登録（96d686f、#311）の読み: #147・#296・#298 で、法則や文法を足した変種の事実を
  before と比べるとき、足したものの宣言の文を除き忘れた。どの法則を変えたかはスクリプトの中にしかなく、ec から見えない。
  族が変えた法則を参照できれば、比べの範囲を体系から導く道が開ける。ここでは、その前提の「参照できるか」を測る。

手順（体系のファイルは変えない。cscl.yaml・cscl・exp/src を一時の場所に写し、写しの exp/src/exp.yaml だけを書き換えて測る）:
  族は sys_above_individual_fix2（#296。変種 B は、法則 above_is_ancestor に前提を足し、法則 above_by_ind・above_by_ind_step を
  足した）。事実の並びの、この族の v_metric_of の行の後に 1 行足す:
    before  書き換えない。
    R       - {is: v_refer, from: sys_above_individual_fix2, to: syntax.above_is_ancestor}   （体系にある法則）
    U       - {is: v_refer, from: sys_above_individual_fix2, to: syntax.above_by_ind}        （変種だけにある法則。体系にない）
  それぞれの写しで、型検査（tc.build）と exp の検査（exp_check.build）を走らせ、法則を閉じた事実から数える:
    errors, ec_errors   誤りの数（err_text は先頭 20）
    rel                 関係ごとの文の数とハッシュ。ただし、族の名と、参照した法則の名（短い名）を両方含む文は除く
                        （足した文と、それから導かれた文）。
  before と比べて: changed（ハッシュが違う関係の数）、changed_rel（その関係の名）
判定（変種 R で決める）: errors 0、ec_errors 0、changed 0 なら支持。どれかが 0 でなければ反証。
  変種 U は記述: 体系にない法則を参照したとき、検査が端の解けなさとして拒むか（errors か ec_errors が 1 以上か）を見る。

開示（結果を見る前に分かっていること）:
  - 族の式は mod {of: [v_refer, from], with: measured_value, at: {count: {gt: 1}}}。法則への v_refer がこの with と食い違うと
    検査が言うかは、見ていない。v_refer の from は continuant、族は information_entity の下。
  - 除く文の基準は「族と法則の両方の名を含む」。#298 の訂正（before にない項を含む文を除く）とは違う。R では新しい項は
    足さないので、その基準では足した文そのものを除けない。
  - U が拒まれても、それは仮説（参照できるか）の判定に使わない。変種だけにある法則は体系に宣言されていないので、
    参照するには宣言が要り、宣言すれば法則として働く。その食い違いを U で見る。
  - 型検査を 3 回走らせる（重い作業はこれ1つ）。

使い方:
  python exp/experiments/sys_family_refers_laws.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_family_refers_laws.json"
EXP = "exp/src/exp.yaml"
FAM = "sys_above_individual_fix2"
ANCHOR = f"  - {{is: v_metric_of, from: {FAM}, to: mean_value}}\n"
LAWS = {"R": "above_is_ancestor", "U": "above_by_ind"}

PROBE = r'''
import contextlib, hashlib, io, json, sys
FAM, LAW = sys.argv[1], sys.argv[2]
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
ecs = [str(e) for e in tc.errors]
F = tc.Facts(T.syntax_facts())
tc.evaluate(tc.law_rules(O), F, tc.variables(O))
short = lambda a: str(a).split(".")[-1]
rel = {}
for r, xs in F.by.items():
    keep = sorted(str(x) for x in xs if not (any(short(a) == FAM for a in x) and any(short(a) == LAW for a in x)))
    if keep:
        rel[r] = [len(keep), hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]]
print(json.dumps({"errors": len(errs), "ec_errors": len(ecs), "err_text": (errs + ecs)[:20], "rel": rel}, ensure_ascii=False))
'''


def variant(law, add):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        f = Path(d) / EXP
        s = f.read_text(encoding="utf-8")
        assert s.count(ANCHOR) == 1, ANCHOR
        if add:
            s = s.replace(ANCHOR, ANCHOR + f"  - {{is: v_refer, from: {FAM}, to: syntax.{law}}}\n")
        f.write_text(s, encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE, FAM, law], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    rows = {}
    for k, law in LAWS.items():
        b0, r = variant(law, False), variant(law, True)
        ch = sorted(x for x in set(r["rel"]) | set(b0["rel"]) if r["rel"].get(x) != b0["rel"].get(x))
        if k == "R":
            rows["variant before"] = {"errors": b0["errors"], "ec_errors": b0["ec_errors"], "err_text": b0["err_text"]}
        rows[f"variant {k}"] = {"law": law, "errors": r["errors"], "ec_errors": r["ec_errors"], "changed": len(ch),
                                "changed_rel": ch, "err_text": r["err_text"]}
        print(k, json.dumps({x: rows[f"variant {k}"][x] for x in ("errors", "ec_errors", "changed")}), flush=True)
    R, U = rows["variant R"], rows["variant U"]
    rows["summary 要約"] = {"before_errors": rows["variant before"]["errors"], "before_ec_errors": rows["variant before"]["ec_errors"],
                          "R_errors": R["errors"], "R_ec_errors": R["ec_errors"], "R_changed": R["changed"],
                          "U_errors": U["errors"], "U_ec_errors": U["ec_errors"], "U_changed": U["changed"]}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_family_refers_laws.py", "_commit": commit, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    ok = R["errors"] == 0 and R["ec_errors"] == 0 and R["changed"] == 0
    print("判定:", "支持" if ok else "反証")


if __name__ == "__main__":
    main()
