"""仮説 h_above_sound（依存する(上位の偽, 修飾の欠け)）を確かめる: 名前の上位（extends から導く above）の偽に、
座標の証人（上位の側にあって下位の側にない式）がいつもあるか。結果を見る前に、この説明と手順を登録した。

背景（会話）: 概念を座標で読む。修飾の次元（動詞と位置の組）の上の点で、self が原点、any がゼロ、same が符号。
  幾何的には、y が x の上位であるとは、y の座標がすべて x にあること（式の包含: acc[y] ⊆ has[x]。
  sys_kind_ref の違反の組と同じ acc と has）。順序を錐（cone）で定める幾何の順序に当たる。
  名前の上位 above の真には、extends の鎖という証人がある。偽は閉世界で「書いていない」から来るので、
  証人を持つとは限らない。偽にも座標の証人があれば、above の真偽は座標で対称に決まる（健全）。
  証人のない偽は、座標では下にあるのに名前では下にない組で、名前だけが区別している。
操作: 体系を変えない。測るだけ。

数え方（引数 after。体系は変えないので before はない）:
  C            比べる概念: T.is_concept のノードと、最上位（tc.TOPS）
  pairs        C の中の、x ≠ y の組の数
  above        above(x, y) の組の数（C の中）
  unsound_true above の組のうち、acc[y] ⊆ has[x] でないものの数（真の側の健全性。下調べのとおり構成から 0 の見込み）
  false        above でない組の数
  gap          false のうち、acc[y] ⊆ has[x] の組（証人のない偽）の数
  gap_zero     gap のうち、acc[y] が空のもの（y が座標を持たない）
  gap_equal    gap のうち gap_zero でなく、acc[x] ⊆ has[y] も成り立つもの（座標が等しく、名前だけが違う）
  gap_rest     gap の残り（座標では x が y の下に入るが、名前では入らない）
  rest_cand    gap_rest のうち r_candidate の組の数（違反の組の候補の内にあるもの）
判定: errors 0、ec_errors 0 のもとで、gap が 0 なら支持（v_support）、0 でなければ反証（v_contradict）。
  unsound_true が 0 でなければ、内容を書いて外れとし、状態は変えない（真の側が崩れていれば、偽の側を問う前提がない）。
  errors か ec_errors が出たら外れとする。分け方（gap_zero, gap_equal, gap_rest）は記述で、判定に使わない。
登録の前に分かっていること（下調べ。測っていない）:
  - r_acc は自前の式（acc_own）と祖先の自前の式（acc_ancestor）から導く。r_has は r_acc を含む（has_by_acc）。
    なので above(x, y)（= 祖先）なら acc[y] ⊆ acc[x] ⊆ has[x] で、unsound_true は構成から 0 になるはず。
  - 最上位の continuant と occurrent は式を持たない（ontology.yaml）。acc が空なら、どの x も座標ではその下に入る。
    なので、continuant の下の x と occurrent の組は gap_zero に入るはず（h_tops_derivable の反証と同じ根）。
  - sys_hierarchy_object の before で、違反の組 V は 3、候補の外で上位の式を持つ組の下書きが 495 あった（記録済み）。
見込み: errors 0、ec_errors 0、unsound_true 0。gap は 0 でなく（反証）、gap_zero が多くを占める。gap_equal と gap_rest は
  0 でないかもしれない。

行（sys_above_sound_after.json）:
  "summary 要約": 上の数
  "gap x→y":      kind（zero / equal / rest）, cand（0 か 1）。gap_zero は数だけ（行にしない）

使い方:
  python exp/experiments/sys_above_sound.py after
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "exp/src")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    n_err = len(tc.errors)
    errs = list(tc.errors)
    with contextlib.redirect_stdout(io.StringIO()):
        import exp_check
        del tc.errors[:]
        try:
            exp_check.build()
        except SystemExit:
            pass
    ec_err = len(tc.errors)
    errs += list(tc.errors)
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))

    def two(r):
        d = collections.defaultdict(set)
        for t in F.by.get(r, ()):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    acc, has = two("r_acc"), two("r_has")
    above = {(t[0], t[1]) for t in F.by.get("above", ()) if len(t) == 2}
    cand = {(t[0], t[1]) for t in F.by.get("r_candidate", ()) if len(t) == 2}
    C = sorted(n for n in T.N if T.is_concept(n) or n in tc.TOPS)
    geo = lambda x, y: acc[y] <= has[x]
    pairs = [(x, y) for x in C for y in C if x != y]
    ab = [p for p in pairs if p in above]
    unsound = [p for p in ab if not geo(*p)]
    false = [p for p in pairs if p not in above]
    gap = [p for p in false if geo(*p)]
    kind = {}
    for x, y in gap:
        kind[(x, y)] = "zero" if not acc[y] else "equal" if geo(y, x) else "rest"
    cnt = collections.Counter(kind.values())
    rest = [p for p in gap if kind[p] == "rest"]
    summ = {"errors": n_err, "ec_errors": ec_err, "C": len(C), "pairs": len(pairs), "above": len(ab),
            "unsound_true": len(unsound), "false": len(false), "gap": len(gap), "gap_zero": cnt["zero"],
            "gap_equal": cnt["equal"], "gap_rest": cnt["rest"], "rest_cand": sum(1 for p in rest if p in cand)}
    rows = {"summary 要約": summ} | {f"gap {x}→{y}": {"kind": kind[(x, y)], "cand": int((x, y) in cand)}
                                    for x, y in gap if kind[(x, y)] != "zero"}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_above_sound_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print("zero の y:", collections.Counter(y for (x, y), k in kind.items() if k == "zero").most_common(10))
    for p in [p for p in gap if kind[p] == "equal"][:20]:
        print("equal", p)
    for p in rest[:20]:
        print("rest", p, int(p in cand))
    for p in unsound[:10]:
        print("unsound", p)
    for e in errs[:10]:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] == ["after"]
    main(sys.argv[1])
