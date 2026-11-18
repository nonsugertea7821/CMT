"""体系そのものを数える: 表示名（display）は、式を日本語に訳した結果であるはず。表示名のうち、式が参照するものの表示名から
来ない部分（余り）は、式の外に取り残された意味の候補。定義の薄い概念（違反の組の上 y）ほど、余りを持つか。
結果を見る前に、この説明と手順を登録した。

背景（会話）: 概念式は、自然言語や機械語を含むほかの言語に一意に訳せるはずで、display はその訳先の語。
  money の「円」（sys_money_axis）と verb_ref の「動詞そのもの」（sys_kind_ref）は、式の外（表示名、注釈、コードの名前の読み）に
  あった区別で、式に移すと過大拡張が止まった。翻訳器はまだないので、文字の上の近似で測る。

数え方（引数: 体系の根のディレクトリ。git の worktree を渡す）:
  概念 c（r_concept）ごとに、元の文字の集まり S(c) を作る: 次のものの表示名の文字。
    c の祖先すべて、c と祖先の限定（mod）の動詞とその祖先、限定の端（with）とその祖先（個体なら個体の表示名と、その種類と祖先）、
    c と祖先の軸（axis）とその上位の軸。
  余り R(c) = c の表示名の漢字と片仮名のうち、S(c) にないもの（平仮名、記号、括弧は数えない）。
  違反の組 V（specific を含意で読んだもの。sys_unit_axis と同じ数え方）の上 y の集まりを Y とする。
  rate_y   = Y のうち R が空でないものの割合
  rate_all = 概念すべてのうち R が空でないものの割合
  V        違反の組の数（2477928 では 9 のはず。前提として確かめる）
判定（2477928 の体系。違反が 9 組あったとき）: V が 9 であることを前提とする（違えば数え方の誤りとして外れ）。
  rate_y が rate_all の 1.5 倍以上なら「定義の薄い概念は、表示名に式から来ない部分を持つ傾向がある」。そうでなければ外れ。
  今の体系（HEAD）でも同じ値を記録する（判定には使わない）。money（円）と verb_ref の R が、直す前後でどう変わったかも書く。
見込み: 分からない。表示名は語彙化した名前（売上 など）が多く、rate_all がもともと高いかもしれない。
訂正（結果を見る前。最初の実行が個体の表示名を読むところで止まり、値は出ていない）: 型検査器の I は個体から種類への対応で、
  表示名を持たない。個体の表示名は、ontology と各領域のファイルの individuals から読む。

行（sys_display_residual_<名>.json。名は before（2477928）か now（HEAD））:
  "summary 要約": V, n_y, n_all, rate_y, rate_all
  "concept c":    residual（R の文字数）, is_y（Y にあれば 1）

使い方:
  python exp/experiments/sys_display_residual.py <根> before|now
"""
import collections
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"
CONTENT = re.compile(r"[一-鿿゠-ヿー]")


def main(root, label):
    root = Path(root).resolve()
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    import os
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, D = tc.build()
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
    Y = {y for _, y in V}
    concepts = sorted(t[0] for t in rel("r_concept"))
    N, AX, I = T.N, T.AX, T.I   # I: 個体 → 種類
    ID = {i: (x or {}).get("display") or "" for i, x in (O.get("individuals") or {}).items()}
    for _, (_, X) in D.items():
        ID |= {i: (x or {}).get("display") or "" for i, x in ((X or {}).get("individuals") or {}).items()}

    def disp(x):
        if x in N:
            return N[x].get("display") or ""
        if x in I:
            return ID.get(x, "")
        return ""

    def up_nodes(x):
        return [x] + [a for a in T.ancestors(x)] if x in N else [x]

    def source(c):
        s, seen = [], set()
        for a in up_nodes(c)[1:]:
            s.append(disp(a))
        for a in up_nodes(c):
            for m in N[a].get("mod") or []:
                if not isinstance(m, dict):
                    continue
                if isinstance(m.get("of"), list) and m["of"]:
                    s += [disp(v) for v in up_nodes(m["of"][0])]
                w = m.get("with")
                if isinstance(w, str):
                    if w in I:
                        s.append(disp(w))
                        s += [disp(v) for v in up_nodes(I[w])]
                    else:
                        s += [disp(v) for v in up_nodes(w)]
            ax = N[a].get("axis")
            while isinstance(ax, str) and ax in AX and ax not in seen:
                seen.add(ax)
                s.append(AX[ax].get("display") or "")
                ax = AX[ax].get("extends")
        return set(CONTENT.findall("".join(s)))
    rows, res = {}, {}
    for c in concepts:
        R = sorted(set(CONTENT.findall(disp(c))) - source(c))
        res[c] = R
        rows[f"concept {c}"] = {"residual": len(R), "is_y": int(c in Y)}
    rate = lambda xs: round(sum(1 for c in xs if res.get(c)) / len(xs), 4) if xs else None
    ys = [y for y in sorted(Y) if y in res]
    summ = {"V": len(V), "n_y": len(ys), "n_all": len(concepts), "rate_y": rate(ys), "rate_all": rate(concepts)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_display_residual_{label}.json").write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for y in ys:
        print("y", y, disp(y), res[y])
    for c in ("subj.money", "syntax.verb_ref", "subj.age"):
        if c in res:
            print("c", c, disp(c), res[c])


if __name__ == "__main__":
    assert len(sys.argv) == 3 and sys.argv[2] in ("before", "now")
    main(sys.argv[1], sys.argv[2])
