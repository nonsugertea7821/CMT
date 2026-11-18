"""体系そのものを数える: 未分化な概念 money の単位を、限定ではなく軸の分化（円の量 ⊂ 量）として足すと、
過大拡張（違反）が規則だけで止まり、体系の検査も通るか。結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_money_unit（f5bf2be）で、money に単位を限定として足すと、money の違反 2 組（hour, days_overdue）は
  規則だけで消えたが、法則 single（1つのノードが足せる限定は1つだけ）に反した。自前の式が2つの辺を見ると、
  2つ目は軸（axis: amount など）で、限定とは別枠だった。ontology の amount の注釈は「単位は質の種類が決める」。
  単位は軸の側の特徴で、量の分化と読み、軸に上下を書けるようにした（1f01587。今の体系の導いた文は変わらない）。
操作（この手順の登録のあと、測る前に1度だけ行う）: exp/src/subj.yaml に軸 yen（円の量、amount の下位、値は数）を足し、
  money の axis を amount から yen にする。ほかは変えない。

数え方（引数 before / after。sys_money_unit と同じ値に、money_has_amount を足す）:
  errors, V, v_money, sales_ok, absorbs_money  sys_money_unit と同じ
  money_has_amount  money が軸 amount を含意で持つ（r_has(money, amount)）なら 1
判定: after で errors 0、v_money 0、sales_ok 1、money_has_amount 1、V は before の V から money の組を除いたものと同じ。
  5つとも満たせば「軸の1歩の分化で、money の過大拡張が規則だけで止まった」とする。満たさないものは、その内容を書いて外れとする。
登録の前に分かっていること: sys_money_unit の before と after。見込み: 5つとも満たす。
訂正（after を測ったあと）: after は errors 2 で外れた。誤りは「領域のファイルに axes を書けない（grammar.domain にない）」と、
  そのため yen が軸として読まれず「axis yen は数の軸でない」。操作の前提（領域に軸を書ける）が成り立っていなかった。
  after の結果はそのまま記録する。次に、領域のファイルにも axes を書けるようにし（grammar.domain と、領域を読むコード）、
  今の体系の導いた文が変わらないことを確かめてから、同じ操作をして同じ判定で測り直す（引数 after2）。

行（sys_money_axis_before.json / sys_money_axis_after.json）:
  "summary 要約": errors, V, v_money, sales_ok, absorbs_money, money_has_amount
  "V x→y":        1（違反の組の一覧）

使い方:
  python exp/experiments/sys_money_axis.py before|after|after2
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rel = lambda r: F.by.get(r, set())

    def two(r):
        d = collections.defaultdict(set)
        for t in rel(r):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    acc, has, anc = two("r_acc"), two("r_has"), two("r_ancestor")
    concept = {t[0] for t in rel("r_concept")}
    V = sorted((x, y) for x, y in rel("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
    y = "subj.money"
    summ = {"errors": len(tc.errors), "V": len(V), "v_money": sum(1 for _, b in V if b == y),
            "sales_ok": int(acc[y] <= acc["subj.sales"]),
            "absorbs_money": sum(1 for x in concept if x != y and y not in anc[x] and x not in anc[y] and acc[y] <= has[x]),
            "money_has_amount": int("amount" in has[y])}
    rows = {"summary 要約": summ} | {f"V {a}→{b}": {"v": 1} for a, b in V}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_money_axis_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print([f"{a}→{b}" for a, b in V])


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"], ["after2"])
    main(sys.argv[1])
