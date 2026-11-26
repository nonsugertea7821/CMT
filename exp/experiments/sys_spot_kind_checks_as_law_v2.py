"""h_spot_kind_checks_as_law の 2 版目: 法則の名を、体系に既にある関係と重ならないように直して測り直す。

1版目（sys_spot_kind_checks_as_law.py、結果 results/sys_spot_kind_checks_as_law.json）:
  足した法則の関係 r_concept・r_verb が syntax.yaml に既にあり、after の写しが「識別子 r_concept が重複している」で読み込みの段で止まった。
  A の after の 4 つはすべて終了コード 1、B は 28 件走らせたところで止めた（すべて after が壊れ）。
  測ったのは名の衝突で、限定の検査を法則で書けるかではない。

訂正（1版目からの変更。手順と判定は、ここに書いたもののほかは 1版目と同じ。材料・選び方・書き換え・覆いの数え方も同じ）:
  1. K2 は、体系に既にある r_concept(var1)（法則 concept_kind が導く: extends を持ち、of・form・holds・pre を持たず、r_verb でない）を使う。
     1版目の r_not_concept・not_concept_by_*・concept_by_extends は足さない。
  2. K3 は、既にある r_verb（holds・pre・上位から導く）とは別の関係 r_two_ends を足す
     （法則 two_ends_by_ends: r_end_from と r_end_to を持つものは r_two_ends。コードの is_verb と同じ形）。
  3. 判定に一つ足す: after の写しで type_checker.py が「検査に失敗」の行を出さずに終了コード 1 以外か、読み込みの段で止まった
     （A の after の type_checker.py の出力に「検査に失敗」も最後の数の行もない）なら、判定しない（書き方の誤りで、法則を測っていない）。

法則（足すもの）:
  mod_new_no_with: mod(var1,var2), position(var2,new), with(var2,var3) を前提に、with(var2,var3) でないことを求める（K1）。
  is_from_with_concept: mod(var1,var2), of(var2,is), position(var2,from), with(var2,var3) を前提に、r_concept(var3) を求める（K2）。
  r_two_ends と two_ends_by_ends（上の 2）。
  verb_ref_with_verb_from・_to: 限定の相手の側の端の種類が ontology.verb_ref の下なら、相手に r_two_ends(var4) を求める（K3）。

開示（結果を見る前に分かっていること）:
  - 1版目の記録（上）を見ている。B の 28 件の before は、退け 23・受け入れ 5 だった（書き換えの中身と before の誤りの文は見ていない）。
  - 既にある r_concept は「r_verb でない」も求める。コードの is_concept は求めない。extends を持ち holds も pre も持たない動詞
    （from と to だけの動詞）を相手にしたとき、before は受け入れ、after は退けるかもしれない（余分な退け）。
  - 足す名（mod_new_no_with・is_from_with_concept・r_two_ends・two_ends_by_ends・verb_ref_with_verb_from・verb_ref_with_verb_to）は、
    登録の前に体系の yaml で grep し、どれも使われていないことを確かめた。type_checker.py は、1版目の止まった理由を見るために
    1版目の after の写しで 1 度走らせただけ（読み込みで止まった）。

出力: results/sys_spot_kind_checks_as_law_v2.json
使い方:
  python exp/experiments/sys_spot_kind_checks_as_law_v2.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_spot_kind_checks_as_law as v1

v1.OUT = v1.ROOT / "exp/experiments/results/sys_spot_kind_checks_as_law_v2.json"

v1.NODES = """  mod_new_no_with: {is: law_rule, display: 位置 new で限定するものは、相手を持たない}
  is_from_with_concept: {is: law_rule, display: 属するの始点で限定する相手は、概念}
  r_two_ends: {is: law_relation, display: 始点と終点の種類を持つ}
  two_ends_by_ends: {is: law_rule, display: 始点の種類と終点の種類があるものは、始点と終点の種類を持つ}
  verb_ref_with_verb_from: {is: law_rule, display: 始点で限定する相手の位置が動詞を受け取るなら、相手は始点と終点の種類を持つ}
  verb_ref_with_verb_to: {is: law_rule, display: 終点で限定する相手の位置が動詞を受け取るなら、相手は始点と終点の種類を持つ}
"""

v1.FACTS = """  - {is: v_assume, from: mod_new_no_with, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: mod_new_no_with, to: {is: position, from: var2, to: new}}
  - {is: v_assume, from: mod_new_no_with, to: {is: with, from: var2, to: var3}}
  - {is: v_require, from: mod_new_no_with, to: {is: with, from: var2, to: var3, neg: true}}
  - {is: v_assume, from: is_from_with_concept, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: is_from_with_concept, to: {is: of, from: var2, to: is}}
  - {is: v_assume, from: is_from_with_concept, to: {is: position, from: var2, to: from}}
  - {is: v_assume, from: is_from_with_concept, to: {is: with, from: var2, to: var3}}
  - {is: v_require, from: is_from_with_concept, to: {is: r_concept, from: var3}}
  - {is: v_assume, from: two_ends_by_ends, to: {is: r_end_from, from: var1, to: var2}}
  - {is: v_assume, from: two_ends_by_ends, to: {is: r_end_to, from: var1, to: var3}}
  - {is: v_derive, from: two_ends_by_ends, to: {is: r_two_ends, from: var1}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: of, from: var2, to: var3}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: position, from: var2, to: from}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: with, from: var2, to: var4}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: r_end_to, from: var3, to: var5}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: r_below, from: var5, to: ontology.verb_ref}}
  - {is: v_require, from: verb_ref_with_verb_from, to: {is: r_two_ends, from: var4}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: of, from: var2, to: var3}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: position, from: var2, to: to}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: with, from: var2, to: var4}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: r_end_from, from: var3, to: var5}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: r_below, from: var5, to: ontology.verb_ref}}
  - {is: v_require, from: verb_ref_with_verb_to, to: {is: r_two_ends, from: var4}}
"""


def main():
    v1.main()
    d = json.loads(v1.OUT.read_text(encoding="utf-8"))
    tc = d["A"]["after"][v1.TC]
    load_broke = tc["code"] != 0 and not tc["failed_line"] and not tc["last"]
    d["summary"]["after_tc_load_broke"] = load_broke
    if load_broke:
        d["judgment"] = {"h_spot_kind_checks_as_law": "not_judged"}
    v1.OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(d["judgment"]))


if __name__ == "__main__":
    main()
