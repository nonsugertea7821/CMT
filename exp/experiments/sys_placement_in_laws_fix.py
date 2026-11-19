"""sys_placement_in_laws の訂正。結果を見た後に、二つの誤りを直す手順を、走らせる前に登録した。

訂正の理由（sys_placement_in_laws.json で見たこと）:
  1. 法則の前提 exists(x) は、ノードでないもの（subj.yaml の軸 sai, cm, yen など。axis の文を、軸の上下として持つ）
     にも当たった。syntax の文 axis は「ノードが持つ数の軸」と「軸の上位」の二つに使われていて、exists では分けられない。
     検査器の検査はノード（T.N）だけを見る。ノードだけが持つ文 domain(x, d) を前提にする。
  2. 版 Q1・Q2 の試しの動詞に from・to がなく、検査器が KeyError('from') で止まった（版の作りの誤り）。
     Q1 は from: continuant, to: any を、Q2 は to: any を足す。
ほかは元の手順と同じ（版、数える量、判定）。判定も同じ:
  agree = 7 かつ law_Q0 = 0 なら支持。agree < 7 か law_Q0 > 0 なら反証。
  Q1・Q3・Q5 で py ≥ 1、Q0・Q2・Q4・Q6 で py = 0 にならないなら mixed。
行は sys_placement_in_laws_fix.json に書く（元の結果は上書きしない）。

使い方:
  python exp/experiments/sys_placement_in_laws_fix.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_placement_in_laws as base

base.OUT = base.ROOT / "exp/experiments/results/sys_placement_in_laws_fix.json"
base.LAW_FACTS = base.LAW_FACTS.replace("{is: exists, from: var1}", "{is: domain, from: var1, to: var3}")
assert base.LAW_FACTS.count("{is: domain, from: var1, to: var3}") == 2
base.CASES["Q1"] = "  zz_v: {display: 試しV, extends: quality, from: continuant, to: any, holds: [{is: refer, from: from, to: to}]}\n"
base.CASES["Q2"] = "  zz_v: {display: 試しV, extends: occurrent, from: continuant, to: any, holds: [{is: refer, from: from, to: to}]}\n"

if __name__ == "__main__":
    base.main()
