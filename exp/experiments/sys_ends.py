"""体系そのものを数える。言語の設計の主張（cscl/design/claims.yaml）の観察のもとになる結果ファイルを書く。

  sys_depend_to.json   動詞「依存する」（とその下位の動詞）の終点に来るものを、1件1行で並べる。
                       行の値: ic（独立持続体の下位）、gdc（汎用依存持続体の下位）、sdc（特定依存持続体の下位）、
                       also_depends（それ自身か上位が、限定で「依存する」の始点に来る）。どれも 0 か 1。
                       数えるのは、否定でない限定（of と with）と、ノードに書かれた事実。否定の限定は何も示さないので数えない。
  sys_state_atoms.json  holds・pre・post に書かれた原子の文を、1件1行で並べる。
                       行の値: in_base（原子の動詞が、基礎の節に並ぶ関係である）。0 か 1。

sys_depend_to.json は、独立持続体を体系から除く前に測った記録。_commit がその時の体系の版。
独立持続体のない体系では測り直せないので、このスクリプトは sys_depend_to.json を書かずに止まる。

使い方:
  python exp/experiments/sys_ends.py      結果ファイルを exp/experiments/results に書く
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cscl/bootstrap/type_checker"))
import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
DEPEND = "ontology.v_depend"
CLASSES = {"ic": "ontology.independent_continuant", "gdc": "ontology.generically_dependent_continuant",
           "sdc": "ontology.specifically_dependent_continuant"}
OTHER = {"from": "to", "to": "from"}


def positive_mods(T, nid):
    for m in T.N[nid].get("mod") or []:
        if isinstance(m, dict) and not m.get("neg") and isinstance(m.get("of"), list) and len(m["of"]) == 2:
            yield m


def depend_ends(T):
    """（どこに書かれたか, 動詞, 位置, 来るもの）を並べる。"""
    out = []
    for nid, n in T.N.items():
        if T.is_verb(nid) or "of" in n:
            continue
        for m in positive_mods(T, nid):
            v, p = m["of"]
            if p not in OTHER or not T.is_a(v, DEPEND):
                continue
            out.append((nid, v, p, nid))
            if m.get("with") in T.N:
                out.append((nid, v, OTHER[p], m["with"]))
    for v, x in T.KF:
        if T.is_a(v, DEPEND):
            for p in OTHER:
                if x.get(p) in T.N:
                    out.append((f"fact:{v}", v, p, x[p]))
    return out


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    missing = [c for c in CLASSES.values() if c not in T.N]
    if missing:
        raise SystemExit(f"体系に {missing} がない。sys_depend_to.json は、それを除く前に測った記録なので測り直さない")
    ends = depend_ends(T)
    depends = {w for _, _, p, w in ends if p == "from"}
    rows = {}
    for i, (src, v, p, w) in enumerate(e for e in ends if e[2] == "to"):
        rows[f"{i:03d} {src} {v}.{p} {w}"] = {k: int(T.is_a(w, c)) for k, c in CLASSES.items()} | {
            "also_depends": int(any(a in depends for a in [w] + T.ancestors(w)))}
    (OUT / "sys_depend_to.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_ends.py", "_commit": commit, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    atoms = {}
    for nid, n in T.N.items():
        for key in ("holds", "pre", "post"):
            for j, a in enumerate(n.get(key) or []):
                if isinstance(a, dict) and "is" in a:
                    atoms[f"{nid}.{key}.{j}"] = {"in_base": int(a["is"] in O["base"])}
    (OUT / "sys_state_atoms.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_ends.py", "_commit": commit, "rows": atoms}, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(rows)
    print(f"sys_depend_to: {n} 行", {k: sum(r[k] for r in rows.values()) for k in [*CLASSES, "also_depends"]})
    print(f"sys_state_atoms: {len(atoms)} 行, in_base {sum(r['in_base'] for r in atoms.values())}")


if __name__ == "__main__":
    main()
