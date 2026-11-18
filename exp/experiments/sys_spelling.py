"""体系そのものを数える: 同じ領域で同じ綴りの語が、書かれた位置によって別のものに解決されていないか（綴りの一意）。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 端の any は、型検査のコードの中で特別に扱われ、限定の with では syntax.any（存在の数量化）に、
  動詞の端ではどのノードでもない語 any のままに解決される。説明（type_checker.py の syntax_facts）は同じものだとしている。
  同じ綴りが2つのものを指すのは、名前の水準の混同（同じなら区別できない、の向き）。法則で見えるように、書かれた語と解決先を記録する。

数え方:
  型検査が体系を読むとき、語を解決する所（qn、qw、限定の with の any）で、(領域, 書かれた語) → 解決した先 を記録する（type_checker.WRITTEN）。
  領域を書いた語（領域.名前）は記録しない。規則の変数は解決しないので記録されない。
  型検査が後で別の所（Ontology.resolve など）で直す語は、ここには入らない（数え漏れになりうる）。

行（sys_spelling.json）。値はどれも 0 か 1。
  "word 領域 語":  multi   解決した先が2つ以上ある
登録の前に分かっていること（会話）: any が with と端で別の先に解決されることは、コードを読んで知っている（数えてはいない）。
  ほかに別の先に解決される語があるかは見ていない。見込み: any の行で multi が 1。qw は自分の領域で解決しない語を syntax で読むので、
  同じ語が qn ではそのまま、qw では syntax の語になる組が出るかもしれない。

使い方:
  python exp/experiments/sys_spelling.py
"""
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
        tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = {}
    for (dom, w), rs in sorted(tc.WRITTEN.items(), key=lambda x: (str(x[0][0]), x[0][1])):
        rows[f"word {dom} {w}"] = {"multi": int(len(rs) > 1)}
        if len(rs) > 1:
            print(dom, w, "→", sorted(map(str, rs)))
    x = [r["multi"] for r in rows.values()]
    print("multi", f"{sum(x)}/{len(x)}")
    (OUT / "sys_spelling.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_spelling.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
