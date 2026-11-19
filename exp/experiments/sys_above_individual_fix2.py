"""sys_above_individual の2度目の訂正（開示）: 1度目の訂正（sys_above_individual_fix.json）で、ec は before・B とも 0 になり、
分類（浅い・深い端）と違反の組の差は 0、changed は B で 3（domain・is・r_written がどれも 2 文ずつ増えた）で、規則どおりなら反証。
この 3 つは、足した法則 2 つ（above_by_ind・above_by_ind_step）の宣言そのもの（法則は個体なので is・domain・r_written を持つ）
と読める。#147（sys_above_closed_fix）と同じく、ハッシュの比べから新しい法則の名を含む文を除いていなかった測りの欠けである。

訂正: 関係ごとのハッシュを、新しい法則の名（above_by_ind・above_by_ind_step、領域の接頭辞つきも）を含む文を除いて取り直す。
  他の手順・判定・変種は sys_above_individual.py・_fix.py のまま。判定は、この取り直した changed で、規則（B で errors 0、
  ec 0、diff 0、changed 0 なら支持）をそのまま当てる。元の 2 つの結果ファイルは上書きしない。出力は sys_above_individual_fix2.json。

結果を見て分かっていること（開示）: 1度目の訂正の数（上）。この訂正で changed が 0 になれば支持、残れば反証。

使い方:
  python exp/experiments/sys_above_individual_fix2.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_above_individual as m  # noqa: E402
import sys_above_individual_fix as f1  # noqa: E402

NEW = ("above_by_ind",)
f1.PROBE = f1.PROBE.replace("    keep = sorted(str(x) for x in xs)\n",
                            "    keep = sorted(str(x) for x in xs if not any(%r in str(a) for a in x))\n" % NEW[0])
assert "above_by_ind" in f1.PROBE
f1.OUT = m.ROOT / "exp/experiments/results/sys_above_individual_fix2.json"

if __name__ == "__main__":
    f1.main()
