"""体系そのものを数える: 定義の薄い（未分化な）概念ほど、ほかの概念を下に集めすぎるか（過大拡張）。
結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_specific と sys_specific_depth で、法則 specific を含意で読んだときの 9 件の違反は、上の概念 y の
  定義の端が上の方（祖先 2 以下）にあるときに多かった（V 8/9、C 3/33）。ただしそれは、見てから選んだ閾値で同じ組を確かめたもの。
  利用者の直観: これは概念の分化の正体で、階層の深さが概念の発達水準を示す。言葉の発達でいう過大拡張（覚えたての語を
  一般的な特徴だけで広く使いすぎる）に当たる。ここでは、組ではなく、すべての概念について、その予測を測る。

数え方（型検査器の法則の評価で導いた文 r_concept, r_own, r_acc, r_has, r_ancestor, with を使う）:
  対象の概念 y: r_concept で、自前の式（r_own(y, ·)）があり、その with の終点が1つ以上あるもの。
  深さ(e) = e の祖先の数（T.ancestors(e) の数）。
  def_depth(y) = y の自前の式の with の終点の深さの最大（y の一番分化した特徴の深さ）。
  shallow(y)   = def_depth(y) が 2 以下（閾値は sys_specific_depth と同じ。ここで選び直さない）。
  absorbs(y)   = 概念 x の数。x ≠ y、x と y はどちらも相手の祖先でない、r_acc(y, ·) が空でなく、
                 r_acc(y, m) のすべての m に r_has(x, m) がある（x は y の定義を満たすのに、y の下にない）。
  seen(y)      = y が、sys_specific の V または C の組の上の側に出たことがある（見たことのある概念）。
訂正（登録のあと、結果を見る前）: 一度走らせたところ、with の終点に個体（例 this_design）が来る式があり、
  祖先を数えられずに止まった（結果は出ていない）。終点がノードでない（個体の）ものは、深さの計算から除く。
判定: absorbs(y) が 1 以上の概念の割合を、shallow の概念と、そうでない概念で比べる。
  shallow の割合が、そうでない概念の割合の 3 倍以上で、かつ seen でない概念だけで数えても 3 倍以上なら、
  「過大拡張の予測は当たった（法則の候補）」とする。全体では 3 倍以上で、seen を除くと届かなければ
  「見た組に頼っている（確かめにならない）」。全体で届かなければ「予測は外れた」とする。
  どちらかの群で absorbs が1以上の概念が 0 のときは、比を無限大とせず、数をそのまま書いて「数が少なく判定できない」とする。
登録の前に分かっていること: sys_specific の V と C の組と、その y の深さ。absorbs をすべての概念で数えたことはない。
  見込み: 当たる。ただし seen を除くと、absorbs が1以上の概念の数が少なく、判定できないかもしれない。

行（sys_overextension.json）:
  "concept y":   def_depth, shallow, absorbs, absorbs_any（absorbs が1以上なら 1）, seen
  "summary 要約": 群（shallow / deep、全体 / seen を除く）ごとの概念の数と absorbs_any の数と割合

使い方:
  python exp/experiments/sys_overextension.py
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
    rows = {}
    for y in sorted(concept):
        ds = [len(T.ancestors(e)) for m in own[y] for e in with_[m] if e in T.N]
        if not ds:
            continue
        ab = 0
        if acc[y]:
            ab = sum(1 for x in concept if x != y and y not in anc[x] and x not in anc[y] and acc[y] <= has[x])
        d = max(ds)
        rows[f"concept {y}"] = {"def_depth": d, "shallow": int(d <= 2), "absorbs": ab,
                                "absorbs_any": int(ab > 0), "seen": int(y in seen_y)}
    summ = {}
    for scope, keep in (("all", lambda r: True), ("unseen", lambda r: not r["seen"])):
        for g, s in (("shallow", 1), ("deep", 0)):
            rs = [r for r in rows.values() if keep(r) and r["shallow"] == s]
            summ[f"{scope}_{g}_n"] = len(rs)
            summ[f"{scope}_{g}_any"] = sum(r["absorbs_any"] for r in rs)
            summ[f"{scope}_{g}_rate"] = round(summ[f"{scope}_{g}_any"] / len(rs), 4) if rs else None
    rows["summary 要約"] = summ
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_overextension.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
