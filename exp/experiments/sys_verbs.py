"""体系そのものを数える: 動的な動詞（フレームを変える）と静的な動詞（holds だけ）の違い。

最上位の分類を演繹する型検査（利用者の求め）の材料を、観察として取る。仮説の確かめではない（判定の基準を置かない）。
この表の多くは、会話の中で一度数えたものを、手順に固定して記録し直したもの（記録の前に値を見ている）。

動的・静的の分け方は sys_tops.is_dynamic と同じ（自分か上位が pre か post を持てば動的）。
端の種類は、自分になければ上位の動詞から受け継ぐ（Ontology.end）。持続体の下にあるかを Ontology.is_a で見る（any は持続体の下にない）。

sys_verbs.json  動詞1つが1行（"verb 動詞"）。値はどれも 0 か 1。
  動的な動詞の行は dyn_*、静的な動詞の行は st_* を持つ（族の平均が、それぞれの側の割合になる）。
    *_has_mod        自分で mod を持つ（限定される）
    *_from_con       from の種類が持続体の下にある
    *_to_con         to の種類が持続体の下にある
    *_ends_con       from と to の両方が持続体の下にある
    *_ends_occ       from か to の種類が生起体の下にある
    *_exists         自分か上位の holds・pre・post に、基礎の関係 exists がある
    *_after_involve  同じく、after か involve がある
    *_opposite       opposite を持つ
  dyn_root           動的な動詞のときだけ: 自分で pre か post を持つ（上位から受け継ぐのでない）

使い方:
  python exp/experiments/sys_verbs.py
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
    import sys_tops  # noqa: E402

OUT = ROOT / "exp/experiments/results"
CON, OCC = "ontology.continuant", "ontology.occurrent"


def relations(T, v):
    """自分か、いちばん近い上位で、holds・pre・post を持つものの基礎の関係。"""
    x = v
    while x in T.N:
        n = T.N[x]
        if any(k in n for k in ("holds", "pre", "post")):
            return {a["is"] for k in ("holds", "pre", "post") for a in n.get(k) or [] if isinstance(a, dict)}
        x = n.get("extends")
    return set()


def under(T, k, top):
    return int(isinstance(k, str) and k in T.N and T.is_a(k, top))


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = {}
    for v in sorted(T.N):
        if not T.is_verb(v):
            continue
        n, d = T.N[v], sys_tops.is_dynamic(T, v)
        p = "dyn_" if d else "st_"
        f, t = T.end(v, "from"), T.end(v, "to")
        rels = relations(T, v)
        row = {"has_mod": int(bool(n.get("mod"))), "from_con": under(T, f, CON), "to_con": under(T, t, CON),
               "ends_con": under(T, f, CON) * under(T, t, CON), "ends_occ": max(under(T, f, OCC), under(T, t, OCC)),
               "exists": int("exists" in rels), "after_involve": int(bool(rels & {"after", "involve"})),
               "opposite": int("opposite" in n)}
        row = {p + k: x for k, x in row.items()}
        if d:
            row["dyn_root"] = int("pre" in n or "post" in n)
        rows[f"verb {v}"] = row
    cols = sorted({c for r in rows.values() for c in r})
    for c in cols:
        x = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(x)}/{len(x)}")
    print("端が両方は持続体でない動的な動詞:", [k for k, r in rows.items() if r.get("dyn_ends_con") == 0])
    print("mod を持つ動的な動詞:", [k for k, r in rows.items() if r.get("dyn_has_mod") == 1])
    (OUT / "sys_verbs.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_verbs.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
