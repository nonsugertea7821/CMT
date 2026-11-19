"""h_decision_link_by_role を確かめる: 決定どうしのつながりは、many の役割を終点に持つ動詞にすれば、いくつでも出せるか。

仮説（exp.yaml）: v_depend(decision, syntax.role)。
  読み: 決定から決定へのつながりを、一般の v_depend ではなく、basis と同じ形の役割（終点の種類に many: true）を
  終点に持つ動詞で書けば、一つの決定から二つ以上のつながりを出せる。
  h_fact_slot_by_end（#383、支持）で、個体の事実の欄は、もう一方の端の種類と many で決まることが分かった。
  v_ground が二つ出せるのは終点の basis が many だから。同じ形の役割を決定どうしに作る。

操作の定義（basis と v_ground を写す）:
  役割 prior_decision: {display: 前提となる決定, extends: decision, mod: {of: [v_depend, to], with: decision}, many: true}
  動詞 v_presuppose:   {display: 前提にする, extends: v_depend, from: decision, to: prior_decision}
  syntax.role（役割、実現できるもの）そのものではなく、「終点の種類を many にした、v_depend の終点で定まる概念」を役割として扱う。
  basis（根拠となる仮説）がこの形で、v_ground が二つ出せる。

手順（sys_fact_slot_by_end の訂正後の手順と同じ形。そのスクリプトは読み込まず、同じ処理をここに書く）:
  体系を一時ディレクトリに写し（.git を除く）、写しの exp/src/exp.yaml の nodes に上の 2 つを足す。
  individuals に d_probe（design_dec_tentative）、facts に d_probe の中身の文と見本の事実を足して、写しの型検査器を走らせる。
見本（始点はどれも d_probe）:
  base   中身の文だけ
  ctrl   v_depend → d_metric、v_depend → d_road_region            （対照。#383 の c2 と同じ。落ちるはず）
  r1     v_presuppose → d_metric、v_presuppose → d_road_region    （同じ動詞で 2 つ）
  r2     v_presuppose → d_metric、v_raise → d_road_region         （役割と、continuant を終点に持つ動詞）
  r4     v_presuppose → d_metric、v_ground → h_ambiguity_is_region_choice
  r3     v_presuppose → d_metric、v_presuppose → lang.d_cscl_display_derived（領域をまたぐ。記録だけ。判定に使わない）
見込み（事前に決める）: ctrl だけが「関係 continuant の事実が2つ以上ある」で落ちる。base・r1・r2・r4 は通る。
数える: 見本ごとに exit、n_err、slot_err（d_probe についての「関係 … の事実が2つ以上ある」）、other_err、fails、match。
判定（事前に決める）:
  base が落ちたら、役割の足し方が壊れているので外れとし、状態を変えない。
  ctrl・r1・r2・r4 の 4 つで match = 1、かつ ctrl の誤りが slot_err の 1 件だけなら支持。
  r1・r2・r4 のどれかが落ちたら反証。
開示（結果を見る前に分かっていること）:
  - 見込みは、type_checker.py の gather（欄 = もう一方の端の種類、many なら複数）と #383 の結果から立てた。
    v_ground（basis）が二つ出せることは #383 の c5 で分かっている。予想が立たないのは、新しく足した役割を
    決定が占められるか（T.occupies）と、足した概念が他の検査（名前だけの区別など）に掛からないか。
  - r3 は、領域をまたぐ basis が解決されない件（h_refer_stratified の範囲）と重なるので、判定に使わない。
  - この実験は体系のファイルを変えない。支持なら、役割を体系に足す PR を別に出す（概念を足すので手で見る）。

行（sys_decision_link_by_role.json）: "case <名前>": {...}, "summary 要約": {n_case, n_match, base_ok, clean, cross_ok, verdict_support}
使い方:
  python exp/experiments/sys_decision_link_by_role.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_decision_link_by_role.json"
PROBE = "d_probe"
NODES = ["  prior_decision: {display: 前提となる決定, extends: decision, mod: {of: [v_depend, to], with: decision}, many: true}",
         "  v_presuppose: {display: 前提にする, extends: v_depend, from: decision, to: prior_decision}"]
CONTENT = f"  - {{is: v_refer, from: {PROBE}, to: {{is: v_depend, from: decision, to: basis}}}}"
CASES = {
    "base": ([], False, True),
    "ctrl": ([("v_depend", "d_metric"), ("v_depend", "d_road_region")], True, True),
    "r1": ([("v_presuppose", "d_metric"), ("v_presuppose", "d_road_region")], False, True),
    "r2": ([("v_presuppose", "d_metric"), ("v_raise", "d_road_region")], False, True),
    "r4": ([("v_presuppose", "d_metric"), ("v_ground", "h_ambiguity_is_region_choice")], False, True),
    "r3": ([("v_presuppose", "d_metric"), ("v_presuppose", "lang.d_cscl_display_derived")], False, False),
}


def patched(src, facts):
    lines = src.split("\n")
    lines.insert(lines.index("nodes:") + 1, "\n".join(NODES))
    lines.insert(lines.index("individuals:") + 1, f"  {PROBE}: {{is: design_dec_tentative}}")
    while lines and lines[-1] == "":
        lines.pop()
    lines += [CONTENT] + [f"  - {{is: {v}, from: {PROBE}, to: {t}}}" for v, t in facts]
    return "\n".join(lines) + "\n"


def run_case(work, src, facts):
    (work / "exp/src/exp.yaml").write_text(patched(src, facts), encoding="utf-8")
    p = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=work,
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"検査に失敗: (\d+) 件", out)
    lines = [ln for ln in out.split("\n") if ln.startswith(" -")]
    slot = [ln for ln in lines if PROBE in ln and re.search(r"関係 \S+ の事実が2つ以上ある", ln)]
    other = [ln for ln in lines if ln not in slot]
    return {"exit": p.returncode, "n_err": int(m.group(1)) if m else 0, "slot_err": 1 if slot else 0,
            "other_err": len(other), "lines": lines[:5], "tail": out.strip().split("\n")[-1][:200]}


def main():
    src = (ROOT / "exp/src/exp.yaml").read_text(encoding="utf-8")
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        for name, (facts, expect, judged) in CASES.items():
            r = run_case(work, src, facts)
            fails = 1 if r["exit"] != 0 else 0
            rows[f"case {name}"] = {"facts": [f"{v} {t}" for v, t in facts], "judged": 1 if judged else 0,
                                    "expect_fail": 1 if expect else 0, **r, "fails": fails,
                                    "match": 1 if fails == (1 if expect else 0) else 0}
            print(name, json.dumps(rows[f"case {name}"], ensure_ascii=False), flush=True)
    judged = [r for k, r in rows.items() if r["judged"] and k != "case base"]
    ctrl = rows["case ctrl"]
    s = {"n_case": len(judged), "n_match": sum(r["match"] for r in judged),
         "base_ok": 1 if rows["case base"]["exit"] == 0 else 0,
         "clean": 1 if ctrl["slot_err"] == 1 and ctrl["other_err"] == 0 and ctrl["n_err"] == 1 else 0,
         "cross_ok": 1 if rows["case r3"]["exit"] == 0 else 0}
    s["verdict_support"] = 1 if s["base_ok"] and s["n_match"] == s["n_case"] and s["clean"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
