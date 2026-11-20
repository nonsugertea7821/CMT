"""h_stratified_by_rule の訂正（sys_stratified_by_rule.py の後、結果を見てから、実行の前に登録した）。

訂正の理由: 元の手順の版 V と P では、zz_y が上位（zz_x）だけを持ち、自分の限定を持たなかった。
  そのため、definition_stratified と関係のない誤りが 2 つ出た（「式がない」と、法則 monotone
  「階層を降りるたびに限定が増える」）。判定は other ≥ 1 を手順の誤りとしていた。
  なお、どの版でも agree = 1 で、py_V = rule_V = 1 だった。
訂正した操作: V と P の zz_y に、自分の限定 {of: [v_refer, to], with: zz_x} を足す
  （zz_y から zz_x への肯定の辺が一つ増えるが、循環の有無と否定の辺は変わらない）。
  ほかは元と同じ（関係・規則・版 B と W・アンカー・数える量・判定）。
行（sys_stratified_by_rule_fix.json）: 元と同じ。

使い方:
  python exp/experiments/sys_stratified_by_rule_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_stratified_by_rule as base

base.OUT = base.ROOT / "exp/experiments/results/sys_stratified_by_rule_fix.json"
OLD = "  zz_y: {display: 試しY, extends: zz_x}\n"
NEW = "  zz_y: {display: 試しY, extends: zz_x, mod: {of: [v_refer, to], with: zz_x}}\n"
for c in ("V", "P"):
    assert base.CASES[c].count(OLD) == 1
    base.CASES[c] = base.CASES[c].replace(OLD, NEW)

if __name__ == "__main__":
    base.main()
