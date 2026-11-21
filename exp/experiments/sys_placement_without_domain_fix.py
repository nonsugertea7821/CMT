"""sys_placement_without_domain の訂正。結果を見た後に、一つの誤りを直す手順を、走らせる前に登録した。

訂正の理由（sys_placement_without_domain.json で見たこと）:
  写しの中で分けた文 axis_up が、基礎の関係・文法の語・導いた関係のどれにもなく、
  法則 entail_by_axis と entail_by_axis_step の前提が「関係と項で書かれていない」誤りになった（other_Q0 = 2、外れ）。
  写しの syntax.yaml の個体に、axis_up: {is: law_relation, display: 軸の上位である} を足して、関係として宣言する。
  ほかは元の手順と同じ（前提は exists のまま、版、数える量）。判定も同じ:
  other_Q0 > 0 か、どれかの版が例外で止まれば外れ。支持: agree = 7 かつ law_Q0 = 0。反証: agree < 7 か law_Q0 > 0。
開示:
  - 元の実行で、axis_up の誤りを除けば agree = 7、law_Q0 = 0 だったことを見ている。この訂正で新しく効くのは、
    entail_by_axis の二つの法則が評価されることで、その評価が置き場の法則やほかの誤りを動かすかどうか。
  - axis_up は syntax_facts が直接書く文で、法則が導く関係ではない。導いた関係（law_relation）として宣言するのは、
    検査器が関係として受け入れる最小の書き方を選んだため。文法の語（ノード）として置くほうが筋はよく、それは手で見る変更になる。
行は sys_placement_without_domain_fix.json に書く（元の結果は上書きしない）。
使い方:
  python exp/experiments/sys_placement_without_domain_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_placement_without_domain as m

base = m.base
base.OUT = base.ROOT / "exp/experiments/results/sys_placement_without_domain_fix.json"
base.LAW_INDS = base.LAW_INDS + "  axis_up: {is: law_relation, display: 軸の上位である}\n"

if __name__ == "__main__":
    base.main()
