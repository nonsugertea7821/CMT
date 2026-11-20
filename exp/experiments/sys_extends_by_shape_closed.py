"""h_extends_by_shape_closed を確かめる: 祖先で探す検査器のもとで M1 と M2 を同じ写しにあてれば、
形・端・new_kind による識別（#533 の読み）と名の is_a が全部揃う。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.extends, [syntax.holds, syntax.new_kind]))。登録 #544（issue #545）。
  出どころ: #543（h_wider_verb_lower_by_ancestry、支持）。anc + M1 で outside は 6 → 1。残りは ontology.v_design < std.v_compute。

操作（一時の写し。体系のファイルと検査器は書き換えない）:
  #540 の patch_checker（依存する を occurrent の子孫から探す）と move_m1、#537 の M2
  （std.yaml の v_compute の行を ontology.yaml の v_design の行の前へ移し、v_design の extends を v_compute にする）を、同じ写しにあてる。
  写しの tc を走らせ、通れば写しの exp/experiments/sys_kind_in_shape.py を走らせ、写しの要約を読む。対照は patch_checker だけの写しの tc。
行（sys_extends_by_shape_closed.json）: "control"・"anc m1 m2"・"summary 要約"

判定（事前に決める）:
  対照の tc が落ちるか、置き換え・移し替えの文字列が見つからなければ外れ（状態を変えない）。
  支持: anc m1 m2 で tc が通り、写しの要約で n_targets_off = 0・n_refs_off = 0・n_extra_outside = 0。
  1 つでも外れれば反証。
開示: #537 で M2 だけは tc が通り、#543 で anc + M1 の outside が ontology.v_design < std.v_compute の 1 つと知っている。
  M2 の移し替えでこの対が名の is_a になる見込みで書いた。M1 と M2 を重ねたときの tc は試していない。
使い方:
  python exp/experiments/sys_extends_by_shape_closed.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_extends_by_shape_closed.json"
sys.path[:0] = [str(ROOT / "exp/experiments")]
from sys_checker_find_by_ancestry import copy, tc_ok, patch_checker, move_m1, line_of, ONT

STD = "cscl/library/std/std.yaml"


def move_m2(dst):
    src = (dst / STD).read_text(encoding="utf-8")
    ont = (dst / ONT).read_text(encoding="utf-8")
    a, s2 = line_of(src, "v_compute"), line_of(ont, "v_design")
    if not (a and s2) or "extends: occurrent" not in s2.group(0):
        return 0
    moved = a.group(0)
    (dst / STD).write_text(src[:a.start()] + src[a.end():], encoding="utf-8")
    ont = ont.replace(s2.group(0), s2.group(0).replace("extends: occurrent", "extends: v_compute", 1), 1)
    b = line_of(ont, "v_design")
    ont = ont[:b.start()] + moved + ont[b.start():]
    (dst / ONT).write_text(ont, encoding="utf-8")
    return 1


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
        f = patch_checker(dst) & move_m1(dst) & move_m2(dst)
        found &= f
        if f:
            t_ok, t_tail = tc_ok(dst)
            r = {"tc_ok": t_ok, "tc_tail": t_tail}
            if t_ok:
                subprocess.run([sys.executable, str(dst / "exp/experiments/sys_kind_in_shape.py")], cwd=dst, capture_output=True, text=True)
                s = json.loads((dst / "exp/experiments/results/sys_kind_in_shape.json").read_text(encoding="utf-8"))["rows"].get("summary 要約", {})
                r.update({k: s.get(k) for k in ("n_targets", "n_targets_off", "n_refs", "n_refs_off", "n_extra", "n_extra_outside", "outside")})
                r["pass"] = int(s.get("n_targets_off") == 0 and s.get("n_refs_off") == 0 and s.get("n_extra_outside") == 0)
            else:
                r["pass"] = 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rows["anc m1 m2"] = r
    ok = rows["control"]["tc_ok"]
    if not ok or not found:
        verdict = "外れ"
    else:
        verdict = "支持" if r.get("pass") else "反証"
    s = {"control_tc_ok": ok, "found": found, "m12_tc_ok": r.get("tc_ok", 0), "pass": r.get("pass", 0),
         "n_extra": r.get("n_extra"), "n_extra_outside": r.get("n_extra_outside"), "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
