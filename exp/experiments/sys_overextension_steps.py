"""体系そのものを数える: 発達水準を「根から何歩分化したか（持つ式の数）」で測ると、発達水準の低い概念ほど、
ほかの概念を下に集めすぎるか（過大拡張）。結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_overextension（1122b96）は、発達水準を定義の端の深さで測り、予測は外れた（比 2.2、登録した 3 倍に届かず）。
  sys_differentiation（49fba98）で、分化は1辺に式1つ（95%）で進むと分かった。それなら、発達水準は根から何歩分化したか、
  つまり受け継いだ分を含めて概念が持つ式の数（r_acc の数）で測れるはず、と考えた（実行の後の読みから出た考え）。
  sys_specific の V の上の概念は、持つ式が 3〜5 だった（見たことのある数）。
注意（登録の前に書く）: absorbs は「y の式をすべて満たす x」を数えるので、y の式が少ないほど、作りの上で満たされやすい。
  この予測は、その作りの効果を含む。だから、当たっても「発達水準の低い概念は、定義が少ないので広く当てはまる」以上のことは
  言えない。外れたら、式の数は発達水準の物差しとして働いていない、と読む。

数え方（sys_overextension と同じ。違うのは発達水準の物差しだけ）:
  対象の概念 y: r_concept で、自前の式があるもの（sys_overextension と同じ集まり）。
  level(y)  = r_acc(y, ·) の数。
  low(y)    = level(y) が、対象の概念すべての level の中央値以下（中央値は、absorbs を見ずに決まる）。
  absorbs(y), seen(y) は sys_overextension と同じ。
判定: absorbs が 1 以上の概念の割合を、low の概念とそうでない概念で比べる。sys_overextension と同じく、
  全体で 3 倍以上、かつ seen を除いても 3 倍以上なら「当たった」。全体だけなら「見た組に頼っている」。全体で届かなければ「外れた」。
  あわせて、level ごとの割合と、sys_overextension の深さの物差しでの比（全体）を並べて書く（判定には使わない）。
登録の前に分かっていること: sys_overextension の結果（深さの物差し）。level の分布と、level ごとの absorbs は見ていない。
  見込み: 当たる（作りの効果があるので）。

行（sys_overextension_steps.json）:
  "concept y":   level, low, absorbs, absorbs_any, seen
  "summary 要約": median_level と、群（low / high、全体 / seen を除く）ごとの概念の数と absorbs_any の数と割合

使い方:
  python exp/experiments/sys_overextension_steps.py
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


def main():
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
    acc, own, has, with_, anc = two("r_acc"), two("r_own"), two("r_has"), two("with"), two("r_ancestor")
    concept = {t[0] for t in rel("r_concept")}
    seen_y = set()
    for f in ("sys_specific.json",):
        for k in json.loads((OUT / f).read_text(encoding="utf-8"))["rows"]:
            if k[0] in "VC" and "→" in k:
                seen_y.add(k[2:].split("→")[1])
    import statistics
    ys = [y for y in sorted(concept) if [e for m in own[y] for e in with_[m] if e in T.N]]
    med = statistics.median(len(acc[y]) for y in ys)
    rows = {}
    for y in ys:
        ab = sum(1 for x in concept if x != y and y not in anc[x] and x not in anc[y] and acc[y] <= has[x]) if acc[y] else 0
        rows[f"concept {y}"] = {"level": len(acc[y]), "low": int(len(acc[y]) <= med), "absorbs": ab,
                                "absorbs_any": int(ab > 0), "seen": int(y in seen_y)}
    summ = {"median_level": med}
    for scope, keep in (("all", lambda r: True), ("unseen", lambda r: not r["seen"])):
        for g, s in (("low", 1), ("high", 0)):
            rs = [r for r in rows.values() if keep(r) and r["low"] == s]
            summ[f"{scope}_{g}_n"] = len(rs)
            summ[f"{scope}_{g}_any"] = sum(r["absorbs_any"] for r in rs)
            summ[f"{scope}_{g}_rate"] = round(summ[f"{scope}_{g}_any"] / len(rs), 4) if rs else None
    by = collections.defaultdict(lambda: [0, 0])
    for r in rows.values():
        by[r["level"]][0] += 1
        by[r["level"]][1] += r["absorbs_any"]
    summ["by_level"] = {str(k): v for k, v in sorted(by.items())}
    rows["summary 要約"] = summ
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_overextension_steps.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
