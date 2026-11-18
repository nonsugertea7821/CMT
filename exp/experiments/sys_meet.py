"""体系そのものを数える: specific を含意で読んだときに残る違反の組（x→y）は、x が2つの概念の「交わり（meet）」で、
上位を1つしか書けない（extends が1つ）ために片方を選ばされたものか。結果を見る前に、この説明と手順を登録した。

背景（会話）: 概念を、持つ式の集まりを包含と含意で並べた束（lattice）として読む。束では、2つの概念の両方の下にある
  最も一般の概念（交わり）が普通にあるが、上位を1つしか書けない木では書けない。sys_unit_axis の after_all で残った違反は 6 組。
  違反の組 x→y は「x は y の積み上がった式を含意によってすべて持つが、y の下にない」もの。
読み: x の上位を p とする。x が p と y の交わりそのものなら、x の持つ式（含意の閉包）は、p と y の積み上がった式を合わせたものの
  閉包と等しい（x は、p と y が言うことのほかに何も足さない）。

数え方（今の体系。引数なし）:
  閉包 cl(S): 式の集まり S に、r_entail を辿って届く式をすべて足したもの。
  組ごとに: p = x の上位（r_parent）。M = cl(acc[p] ∪ acc[y])、X = cl(acc[x])。
    meet   X == M なら 1
    extra  |X − M|（x が p と y のほかに足す式の数）
    lack   |M − X|（0 のはず。x は p の式を積み上げ、y の式を含意で持つ）
  要約: pairs（組の数）、meets（meet が 1 の組の数）、lack_any（lack > 0 の組の数）
判定: lack_any 0 を前提として確かめる（0 でなければ、数え方の誤りとして外れ）。
  meets が pairs の過半（6 組なら 4 以上）なら「残る違反の多くは交わりで、木の制約（上位が1つ）が見えている」。
  そうでなければ外れとし、extra の中身（x が p と y のほかに足す式）を書く。
見込み: 分からない。extra が 1 の組（x が自分の式を1つ足しており、それが y の式を含意する）が多いかもしれない。

行（sys_meet.json）:
  "summary 要約": pairs, meets, lack_any
  "pair x→y":     meet, extra, lack

使い方:
  python exp/experiments/sys_meet.py
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
    acc, has, ent, par = two("r_acc"), two("r_has"), two("r_entail"), two("r_parent")

    def cl(S):
        out, todo = set(S), list(S)
        while todo:
            for g in ent[todo.pop()]:
                if g not in out:
                    out.add(g)
                    todo.append(g)
        return out
    V = sorted((x, y) for x, y in rel("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
    rows, detail = {}, {}
    for x, y in V:
        ps = sorted(par[x])
        p = ps[0] if len(ps) == 1 else None
        M, X = cl(acc[p] | acc[y]) if p else set(), cl(acc[x])
        rows[f"pair {x}→{y}"] = {"meet": int(X == M), "extra": len(X - M), "lack": len(M - X)}
        detail[f"{x}→{y}"] = {"parent": ps, "extra": sorted(X - M), "lack": sorted(M - X)}
    summ = {"pairs": len(V), "meets": sum(r["meet"] for r in rows.values()), "lack_any": sum(1 for r in rows.values() if r["lack"])}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_meet.json").write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, v in detail.items():
        print(k, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
