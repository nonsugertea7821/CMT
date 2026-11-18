"""土台のコードを数える: 型検査と実行器が、どの語に意味を与えているか（特別扱い）。結果を見る前に、この説明と手順を登録した。
仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 法則は、書き方を事実にしたものの上でしか働かない。コードが語を特別に扱うと、その語の混同は法則から見えない
  （any は、そうして見えなかった）。そこで「特別扱いはシグネチャの語だけに許す」とし、ほかは事実と規則に移す。その出発点の一覧を取る。

数え方（規則で決める。個々に選ばない）:
  対象のファイル: cscl/bootstrap/type_checker/type_checker.py と cscl/bootstrap/runtime/runtime.py。
  各行の # より前にある、二重引用符の文字列 "..."（英字か _ で始まり、英数字・_・. からなるもの）を拾う。
  拾った文字列が、体系のノードの識別子か、その領域を除いた名前か、基礎の関係か、個体の名前なら、その語を「コードが名を挙げた語」とする。
  分類:
    signature  シグネチャの語（シグネチャのノード・基礎の関係・個体。今は any, same, self, signature）
    grammar    文法の語（grammar の節の名と、各節に並ぶ語）。書き方を読むための語
    outside    どちらでもない（シグネチャの外の語に、コードが意味を与えている）
  一字の語（a, b, o, p, s など）は、コードの変数名や辞書の鍵と偶然一致することが多い。行に short を付けて分けられるようにする。
  文字列を組み立てて作る名前（f"..."）は拾えない（数え漏れになりうる）。

行（sys_special.json）。値はどれも 0 か 1。
  "word 語":  signature, grammar, outside, short（一字）
登録の前に分かっていること（会話）: 同じ拾い方を一度した（分類はしていない）。そのとき、ontology の語（continuant, occurrent, role,
  definition, quality, magnitude, specifically_dependent_continuant, v_depend, v_refer）、syntax の語（any, verb_ref, v_collect,
  closed_world）、exp の語（v_spell）、基礎の関係（exists, refer, after, part）が出た。any はその後シグネチャに移した。

使い方:
  python exp/experiments/sys_special.py
"""
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
FILES = ["cscl/bootstrap/type_checker/type_checker.py", "cscl/bootstrap/runtime/runtime.py"]


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    inds = set(O.get("individuals") or {}) | set(T.I)
    names = set(T.N) | {tc.short(k) for k in T.N} | set(O["base"]) | inds
    sig = {k for k in T.N if T.domain(k) == "signature"} | set(O["base"]) - {b for b in O["base"] if b != "same"}
    sig |= {i for i, d in (O.get("_idom") or {}).items() if d == "signature"}
    gram = set(O["grammar"]) | {w for ws in O["grammar"].values() for w in (ws or [])}
    found = {}
    for f in FILES:
        for i, line in enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1):
            for s in re.findall(r'"([A-Za-z_][\w.]*)"', line.split("#")[0]):
                if s in names:
                    found.setdefault(s, []).append(f"{Path(f).stem}:{i}")
    rows = {}
    for s in sorted(found):
        short_name = tc.short(s)
        r = {"signature": int(s in sig or short_name in sig), "grammar": int(s in gram or short_name in gram)}
        r["outside"] = int(not r["signature"] and not r["grammar"])
        r["short"] = int(len(short_name) == 1)
        rows[f"word {s}"] = r
    for c in ("signature", "grammar", "outside", "short"):
        print(c, sum(r[c] for r in rows.values()), "/", len(rows))
    print("outside（一字を除く）:")
    for s in sorted(found):
        r = rows[f"word {s}"]
        if r["outside"] and not r["short"]:
            print(" ", s, found[s][:6])
    (OUT / "sys_special.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_special.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
