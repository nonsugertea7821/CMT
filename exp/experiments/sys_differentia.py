"""体系そのものを数える: 動詞が、ほかの動詞と状態の関係で分かれているか（固有の関係を持つか）。結果を見る前に、この説明と手順を登録した。
仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 計算する・設計する・発話するは、どれも「産物が在るようになる」ことしか書かれておらず、
  それぞれに固有の関係（入力への依存、内容への refer、聞き手）が書かれていなかった。そのため式が同じになるか、端の種類（to: any）だけで分かれていた。
  これを抽象化する: 動詞の式は、類（共有する部分）と種差（その動詞に固有の部分）からなるはず。種差が状態の関係になく、端の種類だけにあるものを数える。

数え方:
  動詞（is_verb）ごとに、自分か、いちばん近い上位で holds・pre・post を持つものの原子の集まり A（節、読み方、関係、位置）を取る。
  root      自分で holds・pre・post を持つ（式の語根）。持たないものは上位の式を受け継ぎ、端の種類だけで上位と分かれる（下位の動詞）
  語根どうしで A が同じものの組を「状態で分かれない」とする（端の種類まで同じなら型検査が誤りにするので、ここに残るのは端の種類だけで分かれるもの）。
  在るようにする位置（pre で ¬exists、post で exists）を持つ動的な語根では、その位置について exists 以外の原子があるかも見る（産物に固有の関係）。

行（sys_differentia.json）。値はどれも 0 か 1。
  "verb 動詞":  root
                dyn_unique / st_unique   語根のときだけ（動的・静的）: A がほかのどの語根とも違う
                creation_specific        在るようにする位置を持つ動的な語根のときだけ: その位置について exists 以外の原子がある
登録の前に分かっていること: 設計する・計算する（今の版）は A が同じ（会話）。発話するは depend を持つ。語根 56（型検査の出力）。
  静的な語根どうしで A が同じになるものがあるかは数えていない。

使い方:
  python exp/experiments/sys_differentia.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/runtime"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import runtime as rt  # noqa: E402
    import open_runtime  # noqa: E402

OUT = ROOT / "exp/experiments/results"
SECTIONS = ("holds", "pre", "post")


def formula(T, v):
    x = v
    while x in T.N and not any(k in T.N[x] for k in SECTIONS):
        x = T.N[x].get("extends")
    n = T.N.get(x, {})
    return frozenset((k, rt.reading(a), a["is"], tuple(a.get(p) for p in ("from", "to"))) for k in SECTIONS for a in n.get(k, []))


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    verbs = sorted(v for v in T.N if T.is_verb(v))
    roots = [v for v in verbs if any(k in T.N[v] for k in SECTIONS)]
    groups = collections.defaultdict(list)
    for v in roots:
        groups[formula(T, v)].append(v)
    rows = {}
    for v in verbs:
        r = {"root": int(v in roots)}
        if v in roots:
            dyn = "pre" in T.N[v] or "post" in T.N[v]
            r["dyn_unique" if dyn else "st_unique"] = int(len(groups[formula(T, v)]) == 1)
            cps = open_runtime.creation_positions(T, v) if dyn else set()
            if cps:
                r["creation_specific"] = int(any(rel != "exists" and p in args for p in cps for _, _, rel, args in formula(T, v)))
        rows[f"verb {v}"] = r
    for c in ("root", "dyn_unique", "st_unique", "creation_specific"):
        x = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(x)}/{len(x)}")
    print("状態で分かれない語根の組:", [g for g in groups.values() if len(g) > 1])
    print("産物に固有の関係がない在るようにする動詞:", [k for k, r in rows.items() if r.get("creation_specific") == 0])
    (OUT / "sys_differentia.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_differentia.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
