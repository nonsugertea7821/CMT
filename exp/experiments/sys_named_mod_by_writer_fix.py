"""h_named_mod_by_writer の訂正（sys_named_mod_by_writer.py の後、結果を見てから、実行の前に登録した）。

訂正の理由: 元の手順は、規則 named_mod_use・named_mod_share を v_govern で concept_expression に結んだ。
  検査器は、規則で書いた法則が掛かる節を持つことを咎める（「規則で書いた法則は、前提と、導く文か求める文を持ち、
  掛かる節を持たない」と、v_govern の from が law_given でない誤り）。このため、どの版でも other = 2 になった。
  規則の誤りと Python の誤りは、どの版でも同じノードを咎めていた（agree = 1）が、判定は other ≥ 1 を手順の誤りとしていた。
訂正した操作: 足す文から、二つの v_govern を除く。ほかは元と同じ（関係・規則・版・アンカー・数える量・判定）。
行（sys_named_mod_by_writer_fix.json）: 元と同じ。

使い方:
  python exp/experiments/sys_named_mod_by_writer_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_named_mod_by_writer as base

base.OUT = base.ROOT / "exp/experiments/results/sys_named_mod_by_writer_fix.json"
DROP = ("  - {is: v_govern, from: named_mod_use, to: concept_expression}\n"
        "  - {is: v_govern, from: named_mod_share, to: concept_expression}\n")
assert base.SYN_FACTS.count(DROP) == 1
base.SYN_FACTS = base.SYN_FACTS.replace(DROP, "")

if __name__ == "__main__":
    base.main()
