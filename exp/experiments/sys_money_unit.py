"""体系そのものを数える: 未分化な概念 money を、新しい特徴を1つ足して1歩分化させると、過大拡張（違反）が規則だけで止まるか。
結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_specific で、法則 specific を含意で読んだときの違反 9 件のうち 2 件は、hour→money と days_overdue→money。
  money の定義は「過程を測る大きさ」だけで、名前の「円」に当たる区別（単位）が式にない。sys_differentiation で、
  分化は1辺に式1つで進み、一番多い操作は「新しい特徴を足す」（49%）だった。ontology の注釈は「単位は質の種類が決める」。
操作（この手順の登録のあと、測る前に1度だけ行う）: exp/src/subj.yaml の money の mod を、今の式と
  {of: [v_come_after, from], with: money}（金額は、金額と大きさを比べる）の2つにする。ほかは変えない。
  新しい概念は足さない。sales は money の下にあるので、この式を受け継ぐ。

数え方（引数 before / after。before は操作の前、after は操作の後に走らせる）:
  errors   型検査器の体系の検査の誤りの数（tc.errors）
  V        sys_specific と同じ違反の組（r_candidate(x, y)、r_acc(y) ⊆ r_has(x)、r_acc(y) ⊄ r_acc(x)）
  v_money  V のうち y が subj.money の組の数
  sales_ok subj.sales が money の式をすべて持つ（r_acc(money) ⊆ r_acc(sales)）なら 1
  absorbs_money  sys_overextension と同じ absorbs（money の定義を満たすのに money の下にない概念の数）
判定: after で errors 0、v_money 0、sales_ok 1、V は before の V から money の組を除いたものと同じ（新しい違反がない）。
  4つとも満たせば「1歩の分化で、money の過大拡張が規則だけで止まった」とする。満たさないものは、その内容を書いて外れとする。
登録の前に分かっていること: sys_specific の V（9 組、money の組 2）。sys_overextension の money の absorbs 2。
  見込み: 4つとも満たす。

行（sys_money_unit_before.json / sys_money_unit_after.json）:
  "summary 要約": errors, V, v_money, sales_ok, absorbs_money
  "V x→y":        1（違反の組の一覧）

使い方:
  python exp/experiments/sys_money_unit.py before|after
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
            "absorbs_money": sum(1 for x in concept if x != y and y not in anc[x] and x not in anc[y] and acc[y] <= has[x])}
    rows = {"summary 要約": summ} | {f"V {a}→{b}": {"v": 1} for a, b in V}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_money_unit_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print([f"{a}→{b}" for a, b in V])


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"])
    main(sys.argv[1])
