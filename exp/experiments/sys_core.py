"""体系そのものを数える: syntax が意味を使う ontology の語から、定義をたどって閉じた集合（syntax の下に要る ontology の核）。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: sys_lower で、runtime は ontology の語をほとんど外せる形、syntax は 27 語のうち 22 語の意味を式で使う（other）と分かった。
  runtime をシグネチャと syntax だけで書くには、syntax が使う語を下に下ろす必要がある。その語を下ろすには、その語の定義が参照する語も
  下に要る。どれだけ要るかを、規則でたどって求める（判断で選ばない）。

数え方（規則で決める）:
  種: sys_lower.json で other が 1 の行のうち、層が syntax の語（ontology のノード）。
  たどり方: 集合の語 w について、w の式が参照する ontology のノード（sys_lower.positions と同じ範囲。上位も含む。下ろすには上位も要る）を集合に加える。
    増えなくなるまで繰り返す。シグネチャ・syntax・runtime の語には進まない（もう下にある、または上の層）。
  基礎の関係: 集合の語の holds と pre と post に出る基礎の関係を「使う」とする。
行（sys_core.json）。値はどれも 0 か 1。
  "word 語"（ontology のノードすべて）:  seed（種である）, core（閉じた集合に入る）
  "base 関係"（基礎の関係すべて）:        used（核の語の holds, pre, post に出る）
登録の前に分かっていること（会話）: 種は 22 語（s, p, o, kind, sentence, word, participant, v_express など）。ontology のノードの数は数えていない。
  見込み: sentence と word は information_entity から dependent、continuant へたどるので、核は ontology の上の方をかなり含む。

使い方:
  python exp/experiments/sys_core.py
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
    import sys_lower as sl  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def atoms(x):
    if isinstance(x, dict):
        if isinstance(x.get("is"), str):
            yield x["is"]
        for v in x.values():
            yield from atoms(v)
    elif isinstance(x, list):
        for v in x:
            yield from atoms(v)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    low = json.loads((OUT / "sys_lower.json").read_text(encoding="utf-8"))["rows"]
    onto = {n for n in T.N if T.domain(n) == "ontology"}
    seed = {n for n in onto if low.get(f"word syntax {tc.short(n)}", {}).get("other")}
    core, todo = set(seed), list(seed)
    while todo:
        w = todo.pop()
        for r, _ in sl.positions(T, w):
            if r in onto and r not in core:
                core.add(r)
                todo.append(r)
    rows = {f"word {tc.short(n)}": {"seed": int(n in seed), "core": int(n in core)} for n in sorted(onto)}
    used = {a for n in core for k in ("holds", "pre", "post") for a in atoms(T.N[n].get(k))}
    for b in sorted(T.B):
        rows[f"base {b}"] = {"used": int(b in used)}
    print("種", len(seed), "核", len(core), "ontology のノード", len(onto))
    print("核で種でない:", sorted(tc.short(n) for n in core - seed))
    print("核の外:", sorted(tc.short(n) for n in onto - core))
    print("使う基礎の関係:", sorted(b for b in T.B if b in used))
    (OUT / "sys_core.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_core.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
