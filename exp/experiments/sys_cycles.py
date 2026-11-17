"""体系そのものを数える: 定義の循環（自分を限定するものについて述べている定義）。

定義の辺と循環は、型検査器の法則 definition_stratified と同じもの（type_checker.definition_edges, definition_cycles）を使う。
辺は、上位（extends）、名前を付けた修飾語、限定の with。

sys_cycles.json  循環ごとに 1 行。行の値はどれも 0 か 1。
  neg            循環の中の辺に、否定の限定がある
  same_relation  循環の中の限定の辺（extends でない辺）の動詞が、どれも同じ基礎の関係を持つ（1つの関係を両端から書いている）
  in_syntax      循環のノードがすべて syntax にある

使い方:
  python exp/experiments/sys_cycles.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cscl/bootstrap/type_checker"))
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def base_relations(T, verb):
    """動詞の holds に書かれた基礎の関係の集まり（holds を持つ上位までたどる）。"""
    x = verb
    while x in T.N and "holds" not in T.N[x]:
        x = T.up(x)
    return frozenset(a["is"] for a in (T.N.get(x) or {}).get("holds") or [])


def mod_verbs(T, a, b):
    """ノード a の定義のうち、b を with に持つ限定の動詞。"""
    n, out = T.N[a], []
    if "of" in n and n.get("with") == b:
        out.append(n["of"][0])
    ms = n.get("mod") or []
    for m in ms if isinstance(ms, list) else [ms]:
        if isinstance(m, str) and m == b and "of" in T.N[b]:
            out.append(T.N[b]["of"][0])
        elif isinstance(m, dict) and m.get("with") == b:
            out.append(m["of"][0])
    return out


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    edges = tc.definition_edges(T)
    rows = {}
    for c in sorted(tc.definition_cycles(edges), key=lambda c: sorted(c)):
        inner = [(a, b, neg) for a, b, neg in edges if a in c and b in c]
        rels = {base_relations(T, v) for a, b, _ in inner for v in mod_verbs(T, a, b)}
        rows[" ".join(sorted(c))] = {"neg": int(any(neg for _, _, neg in inner)),
                                     "same_relation": int(len(rels) == 1),
                                     "in_syntax": int(all(x.startswith("syntax.") for x in c))}
        print(sorted(c), rows[" ".join(sorted(c))], sorted(sorted(r) for r in rels))
    (OUT / "sys_cycles.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_cycles.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(rows), "循環", {k: sum(r[k] for r in rows.values()) for k in ("neg", "same_relation", "in_syntax")})


if __name__ == "__main__":
    main()
