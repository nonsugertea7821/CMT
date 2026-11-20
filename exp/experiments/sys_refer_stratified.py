"""仮説 h_refer_stratified（依存する(型検査器, [文に述べられる文, 領域])）を確かめる。
結果を見る前に、この説明と手順を登録した。

系列: 登録（6ebedff, e37b452）の読みは「同じ領域の中では文を述べる文を書けず、述べるには別の領域を立てる」。
  利用者の判断「名付け（refer）を同じ層の中で書けなくし、層（領域）の多様さで吸収する」と、
  指摘「層は規則から導かれるもの、領域は上書きの単位で、別のもの」から。
  ロードマップでは「領域をまたぐ basis の未解決」もここに置いた（決定から仮説への v_ground が同じ領域の中にある）。
確かめ方: 型検査器がこの区別に依存できるかを、今の体系がその法則（同じ領域の中で、文を述べる文を置かない）を
  すでに満たしているかで見る。法則を足した写しで型検査を走らせるのと、反する事実を数えるのは同じ数になるので、
  数えるだけにする（体系のファイルは書き換えない。tc.build() を 1 回）。
定義:
  領域 dom(x): 名前 x の点より前（exp.h_a なら exp）。
  述べる動詞: 動詞 v とその祖先に syntax.v_refer があるもの。
  文 sentence(x): x が個体で、その種類（is）とその祖先に syntax.sentence があるもの。
  R:        述べる動詞の事実のうち、to が名前で、sentence(to) のもの。
  R_same:   R のうち dom(from) = dom(to)。
  R_cross:  R のうち dom(from) ≠ dom(to)。
  R_inline: 述べる動詞の事実のうち、to が式（辞書）のもの（記述。式は領域を持たないので判定に使わない）。
  S_same:   どの動詞の事実でも、from と to がどちらも文で、同じ領域のもの（記述。basis の未解決の大きさ）。
  verbs_same: R_same に出る動詞ごとの数（記述）。
判定（事前に決める）:
  R_same = 0 かつ R_cross > 0 なら支持（今の体系は、文を述べる文を領域をまたいで書いており、型検査器がこの区別で
    分けても壊れない）。
  R_same > 0 なら反証（同じ領域の中で文を述べる文がすでにあり、今のままでは、型検査器がこの区別に依存すると壊れる）。
  R = 0 なら mixed（確かめる対象がない）。
見込み: claims の観察から仮説への v_support や、exp の文どうしの関係が同じ領域の中にあるので、
  v_support などが v_refer の下にあれば R_same > 0 で反証の見込み。下になければ R_same は小さい。

行（sys_refer_stratified.json）:
  "summary 要約": R, R_same, R_cross, R_inline, S_same
  "verb <v>": same（R_same のうちその動詞の数）, cross
  "texts": R_same の事実の例（先頭 20）
使い方:
  python exp/experiments/sys_refer_stratified.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_refer_stratified.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    I = O.get("individuals") or {}
    up = lambda x: [x] + (T.ancestors(x) if x in T.N else [])
    refer = lambda v: isinstance(v, str) and "syntax.v_refer" in up(v)
    sentence = lambda x: isinstance(x, str) and x in I and isinstance(I[x], dict) and "syntax.sentence" in up(I[x].get("is"))
    dom = lambda x: x.split(".")[0]
    R = R_same = R_cross = R_inline = S_same = 0
    per = collections.defaultdict(lambda: {"same": 0, "cross": 0})
    ex = []
    for f in O.get("facts") or []:
        if not isinstance(f, dict):
            continue
        v, a, b = f.get("is"), f.get("from"), f.get("to")
        if isinstance(a, str) and sentence(a) and sentence(b) and dom(a) == dom(b):
            S_same += 1
        if not refer(v):
            continue
        if isinstance(b, dict):
            R_inline += 1
            continue
        if not (isinstance(a, str) and sentence(b)):
            continue
        R += 1
        if dom(a) == dom(b):
            R_same += 1
            per[v]["same"] += 1
            if len(ex) < 20:
                ex.append(f"{v} {a} → {b}")
        else:
            R_cross += 1
            per[v]["cross"] += 1
    summ = {"errors": len(tc.errors), "R": R, "R_same": R_same, "R_cross": R_cross, "R_inline": R_inline, "S_same": S_same}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = {"summary 要約": summ} | {f"verb {v}": c for v, c in sorted(per.items())}
    OUT.write_text(json.dumps({"rev": rev, "rows": rows, "texts": ex}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for v, c in sorted(per.items()):
        print(v, c)
    for e in ex:
        print(e)


if __name__ == "__main__":
    main()
