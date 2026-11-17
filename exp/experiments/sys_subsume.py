"""体系そのものを数える: 動詞の親子を「端が内側にあり、式が相手の式を含む」で決めたとき、今の extends とどれだけずれるか。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 動詞が表す関係は「端の種類の組のうち、式が成り立つもの」の集まり。端を狭めるか式に原子を足すと集まりは小さくなる。
  だから any→any で式 F を持つ動詞は、F を含む式を持つ動詞すべての親になる（式が最も弱い ontology.p は、全ての関係の親）。
  法則 nested_ends（式が同じで端が入れ子）は、その特別な場合。一般の親子が今の extends とずれているかを数える。

数え方:
  語根: 動詞（is_verb）のうち、自分で holds・pre・post を持つもの。
  A(v): 語根 v の原子の集まり（節、読み方、関係、位置）。sys_differentia の formula と同じ（節は区別する。法則を通した含みは見ない）。
  b が a を包む（b は a の親になれる）: a ≠ b、A(b) ⊆ A(a)、from と to で a の端が b の端の内側（Ontology.is_a）、
    b が new_kind を持つなら a も持ち、その内側にある（b が持たず a が持つのは許す）。
  ずれ: a を包む b が、a の上位（ancestors）にない。
  層: a の領域が b の領域を使える（同じ領域か、uses をたどって届く）なら、a を b の下位に書ける。

行（sys_subsume.json）。値はどれも 0 か 1。
  "root 動詞":  has_subsumer       a を包む別の語根がある
                strict             a を包む語根のうち、A が真に小さいものがある（式が同じでない）
                any_end            a を包む語根のうち、端に any を持つものがある
  （has_subsumer が 1 のときだけ）
                all_ancestors      a を包む語根がすべて a の上位にある（ずれがない）
                some_usable        上位にない包む語根のうち、a の領域から使えるものがある（ずれがなければ数えない）
登録の前に分かっていること（会話）: 端に any を持つ動詞の一覧と式を見た。そこから v_trigger・v_cause・v_raise・v_lower が v_transfer に、
  v_measure・v_begin・v_end が v_rely に、v_measure が v_refer に包まれると見込んだ（数えてはいない）。
  式が同じで端が入れ子の組は、v_depend⊂v_rely、v_design⊂v_compute の2つが残る（法則 nested_ends のパッチで確かめた）。

使い方:
  python exp/experiments/sys_subsume.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import sys_differentia  # noqa: E402

OUT = ROOT / "exp/experiments/results"
SECTIONS = sys_differentia.SECTIONS


def reach(O, d):
    out, todo = set(), [d]
    while todo:
        x = todo.pop()
        if x not in out:
            out.add(x)
            todo += (O["domains"].get(x) or {}).get("uses") or []
    return out


def subsumes(T, A, b, a):
    if a == b or not A[b] <= A[a]:
        return False
    if not all(T.is_a(T.end(a, p), T.end(b, p)) for p in ("from", "to")):
        return False
    kb, ka = T.end(b, "new_kind"), T.end(a, "new_kind")
    return kb is None or (ka is not None and T.is_a(ka, kb))


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    roots = sorted(v for v in T.N if T.is_verb(v) and any(k in T.N[v] for k in SECTIONS))
    A = {v: sys_differentia.formula(T, v) for v in roots}
    rows, shifted = {}, []
    for a in roots:
        subs = [b for b in roots if subsumes(T, A, b, a)]
        r = {"has_subsumer": int(bool(subs)), "strict": int(any(A[b] < A[a] for b in subs)),
             "any_end": int(any("any" in (T.end(b, "from"), T.end(b, "to")) for b in subs))}
        if subs:
            anc = set(T.ancestors(a))
            off = [b for b in subs if b not in anc]
            r["all_ancestors"] = int(not off)
            if off:
                usable = reach(O, T.domain(a))
                r["some_usable"] = int(any(T.domain(b) in usable for b in off))
                shifted.append((a, off))
        rows[f"root {a}"] = r
    for c in ("has_subsumer", "strict", "any_end", "all_ancestors", "some_usable"):
        x = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(x)}/{len(x)}")
    print("上位にない包む語根:")
    for a, off in shifted:
        print(" ", a, "←", off)
    (OUT / "sys_subsume.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_subsume.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
