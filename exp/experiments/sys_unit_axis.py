"""体系そのものを数える: 量の単位を軸の分化として書く操作（sys_money_axis で money に効いた）を、ほかの量にも当てると、
過大拡張が規則だけで止まり、新しい違反を生まないか。結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_money_axis で、money の単位（円）を軸 yen（円の量 ⊂ 量）として書くと、money の過大拡張が止まった。
  残る違反 7 組の1つ height→age は、年齢（歳）と身長（センチ）が同じ軸 amount にあり、単位は表示名の中にしかない。
  法則 at_axis（45aed87）で、限定が値を指定する軸は、比べる概念の値の軸かその上位であることを確かめるようにした。
操作（この手順の登録のあと、測る前に行う。どちらも exp/src/subj.yaml の軸と量の axis だけを変える）:
  after:     軸 sai（歳の量）と cm（センチの量）を、どちらも amount の下位として足し、age の axis を sai、height の axis を cm にする。
  after_all: after に加えて、表示名に単位を書いた残りの量も、その単位の軸に置く（規則: 表示名が単位を書く量は、その単位の軸に置く）。
             monthly_fee, profit_gap（円）は yen に。population（人）は軸 people（人の量）、days_overdue, days_since（日数）は
             軸 days（日の量）、hour（時）は軸 hours（時の量）を、どれも amount の下位として足して置く。
  限定の at（amount）は書き換えない（法則 at_axis では、上位の軸 amount で比べてよい）。

数え方（引数 before / after / after_all）:
  errors    型検査の誤りの数
  V         specific を含意で読んだときの違反の組の数（sys_money_axis と同じ数え方）
  v_height_age  height→age が違反に残れば 1
  new_V     before にない違反の組の数
  v_money   money が上の違反の組の数
  sales_ok  sales が money の積み上がった式をすべて持てば 1
判定: after で errors 0、v_height_age 0、new_V 0 の3つを満たせば「歳とセンチの分化で、height→age の過大拡張が規則だけで止まった」。
  after_all で errors 0、v_height_age 0、new_V 0、v_money 0、sales_ok 1 の5つを満たせば「単位の規則を一律に当てても、
  新しい過大拡張を生まない」。満たさないものは、その内容を書いて外れとする。
登録の前に分かっていること: sys_money_axis の after3（V 7、そのうち height→age）。
見込み: after は3つとも満たす。after_all は、円の量どうし（monthly_fee, profit_gap と money）が近くなって new_V が出るかもしれない（分からない）。

行（sys_unit_axis_<引数>.json）:
  "summary 要約": errors, V, v_height_age, new_V, v_money, sales_ok
  "V x→y":        1（違反の組の一覧）

使い方:
  python exp/experiments/sys_unit_axis.py before|after|after_all
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
    acc, has = two("r_acc"), two("r_has")
    V = sorted((x, y) for x, y in rel("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
    before = set()
    if label != "before":
        rows = json.loads((OUT / "sys_unit_axis_before.json").read_text(encoding="utf-8"))["rows"]
        before = {tuple(k[2:].split("→")) for k in rows if k.startswith("V ")}
    summ = {"errors": len(tc.errors), "V": len(V), "v_height_age": int(("subj.height", "subj.age") in V),
            "new_V": sum(1 for p in V if p not in before) if label != "before" else 0,
            "v_money": sum(1 for _, b in V if b == "subj.money"),
            "sales_ok": int(acc["subj.money"] <= acc["subj.sales"])}
    rows = {"summary 要約": summ} | {f"V {a}→{b}": {"v": 1} for a, b in V}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_unit_axis_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print([f"{a}→{b}" for a, b in V])
    for e in tc.errors:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"], ["after_all"])
    main(sys.argv[1])
