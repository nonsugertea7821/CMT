"""h_wider_verb_lower_by_ancestry を確かめる: 検査器が祖先で語を探すなら、端の広い動詞を下の層に置いた体系（#537 の M1）で、
形・端・new_kind による識別（#533 の読み）が名の is_a と食い違わなくなる。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.domain, type_checker))。登録 #541（issue #542）。
  出どころ: #540（h_checker_find_by_ancestry、支持）。anc の検査器なら M1 で tc が通る。#537 は tc で止まり、読みまで届かなかった。

操作（一時の写し。体系のファイルと検査器は書き換えない）:
  #540 のスクリプトの patch_checker（依存する を occurrent の子孫から探す）と move_m1（exp.v_rely を ontology へ移し、
  v_depend の extends を v_rely にする）を、同じ写しに両方あてる。対照は patch_checker だけの写し。
  各写しで tc を走らせ、通れば写しの exp/experiments/sys_kind_in_shape.py を走らせ、写しの結果を読む（本物の結果には触れない）。
行（sys_wider_verb_lower_by_ancestry.json）: "control"・"anc m1"・"summary 要約"

判定（事前に決める）:
  対照の tc が落ちるか、置き換え・移し替えの文字列が見つからなければ外れ（状態を変えない）。
  支持: anc m1 で tc が通り、写しの読みで n_targets_off = 0・n_refs_off = 0、行 "ref ontology.v_rely" があり、
    その missing = 0、extra が {exp.v_ground, exp.v_scope} のうちだけ。
  1 つでも外れれば反証。
  あわせて、写しの読みの outside（許した 3 対の外の extra）の数を n_outside として数える（判定には使わない）。
開示: #537 の M1 の判定と同じ条件。#533 の outside 6 のうち 4（ontology.v_depend・subj の 3 つ・syntax.v_use の < exp.v_rely）は、
  v_rely の名が ontology.v_rely に替わると、許した対の外で数え方が変わる。この数の見込みは書く前に計算していない。
使い方:
  python exp/experiments/sys_wider_verb_lower_by_ancestry.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_wider_verb_lower_by_ancestry.json"
sys.path[:0] = [str(ROOT / "exp/experiments")]
from sys_checker_find_by_ancestry import copy, tc_ok, patch_checker, move_m1

ALLOWED = {"exp.v_ground", "exp.v_scope"}
ROW = "ref ontology.v_rely"


def main():
    rows = {}
    found = 1
    tmp, dst = copy()
    try:
        found &= patch_checker(dst)
        ok, tail = tc_ok(dst)
        rows["control"] = {"tc_ok": ok, "tail": tail}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tmp, dst = copy()
    r = {}
    try:
        f = patch_checker(dst) & move_m1(dst)
        found &= f
        if f:
            t_ok, t_tail = tc_ok(dst)
            r = {"tc_ok": t_ok, "tc_tail": t_tail}
            if t_ok:
                subprocess.run([sys.executable, str(dst / "exp/experiments/sys_kind_in_shape.py")], cwd=dst, capture_output=True, text=True)
                res = json.loads((dst / "exp/experiments/results/sys_kind_in_shape.json").read_text(encoding="utf-8"))["rows"]
                s = res.get("summary 要約", {})
                w = res.get(ROW, {})
                ex = w.get("extra_names", None)
                out = s.get("outside")
                r.update({"n_targets_off": s.get("n_targets_off"), "n_refs_off": s.get("n_refs_off"), "row_found": int(bool(w)),
                          "w_missing": w.get("missing"), "w_extra": ex, "outside": out,
                          "n_outside": len(out) if isinstance(out, list) else None})
                r["pass"] = int(s.get("n_targets_off") == 0 and s.get("n_refs_off") == 0 and bool(w) and w.get("missing") == 0
                                and ex is not None and set(ex) <= ALLOWED)
            else:
                r["pass"] = 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rows["anc m1"] = r
    ok = rows["control"]["tc_ok"]
    if not ok or not found:
        verdict = "外れ"
    else:
        verdict = "支持" if r.get("pass") else "反証"
    s = {"control_tc_ok": ok, "found": found, "m1_tc_ok": r.get("tc_ok", 0), "pass": r.get("pass", 0),
         "n_outside": r.get("n_outside"), "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
