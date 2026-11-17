"""体系そのものを数える: 下の層（syntax, runtime）が ontology の語を、式のどの位置で参照しているか。そこから、その参照の外し方を規則で分ける。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 変数は runtime の割り当て（binding）が意味を与えるものではないか。runtime がシグネチャと syntax だけを知って書けるなら、
  土台のコードはシグネチャ・syntax・runtime だけを翻訳し、法則の評価も runtime の実行になる（bootstrap）。
  そのために、syntax と runtime が使う ontology の語を、外し方で分けた表を作る。表は判断で作らず、観察から規則で導く（利用者の指示）。

数え方（規則で決める。個々に選ばない）:
  対象: 領域が syntax か runtime のノード n と、n の式が参照する ontology のノード w の組（Ontology.refs と同じ範囲）。
  参照の位置（n の式のどこに w が出るか）:
    extends   n の上位（Ontology.parents。extends と、is の始点の限定）
    end       n の from, to, new_kind
    verb      n の of, form の動詞、限定（mod）の of の動詞
    with      限定の with
    other     それ以外（cmp の端、名前で書いた限定のノード）
  w の性質:
    base_verb  w が動詞で、holds がちょうど1つの文で、その文が基礎の関係の肯定で、始点 from・終点 to の順に端を取る（v_refer の refer など）
  行の値（組（層, w）ごとに、その層のノード全体での参照をまとめる）:
    extends_only  参照がすべて extends の位置（分類のためだけに使う。上の層の側から分類する形に移せる候補）
    reducible     参照がすべて verb の位置で、w が base_verb（基礎の関係で書き直せる候補）
    other         どちらでもない（その層の式が w の意味を使っている。w を下に下ろすか、層の組み替えが要る）
  これとは別に、基礎の関係そのものの置き場所を行にする:
    "base 関係"  in_ontology  基礎の関係が ontology に置かれている（syntax・runtime の式の holds, pre, post や規則で使われうる）
登録の前に分かっていること（会話）: syntax は ontology の語 27、runtime は 11 を参照する（Ontology.refs で手早く数えた。位置は分けていない）。
  基礎の関係 exists, refer, depend, part, after, involve は ontology にあり、シグネチャには same だけがある。
  見込み: v_refer, v_compose, v_come_after, v_depend は base_verb。continuant, information_entity などは extends_only が多い。

行（sys_lower.json）。値はどれも 0 か 1。
  "word 層 語":  extends_only, reducible, other
  "base 関係":   in_ontology

使い方:
  python exp/experiments/sys_lower.py
"""
import contextlib
import io
import json
import subprocess
import sys

import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
LOWER = ("syntax", "runtime")


def positions(T, nid):
    """ノードの式が参照するノードと、その位置。"""
    n, out = T.N[nid], []
    out += [(p, "extends") for p in T.parents(nid)]
    for k in ("from", "to", "new_kind"):
        out.append((n.get(k), "end"))
    for k in ("of", "form"):
        if k in n:
            out.append((n[k][0], "verb"))
    for m in n.get("mod") or []:
        if isinstance(m, dict):
            out += [(m["of"][0], "verb"), (m.get("with"), "with")]
        else:
            out.append((m, "other"))
    for x in n.get("cmp") or []:
        out += [(x.get("a"), "other"), (x.get("b"), "other")]
    return [(r, p) for r, p in out if r in T.N]


def base_verb(T, w):
    h = T.N[w].get("holds") or []
    return int(T.is_verb(w) and len(h) == 1 and isinstance(h[0], dict) and h[0].get("is") in T.B
               and not h[0].get("neg") and h[0].get("from") == "from" and h[0].get("to") == "to")


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    pos = {}
    for nid in T.N:
        if T.domain(nid) not in LOWER:
            continue
        for r, p in positions(T, nid):
            if T.domain(r) == "ontology":
                pos.setdefault((T.domain(nid), r), set()).add(p)
    rows = {}
    for (layer, w), ps in sorted(pos.items()):
        ext = int(ps == {"extends"})
        red = int(ps == {"verb"} and base_verb(T, w))
        rows[f"word {layer} {tc.short(w)}"] = {"extends_only": ext, "reducible": red, "other": int(not ext and not red)}
        print(layer, tc.short(w), sorted(ps), "extends_only" if ext else "reducible" if red else "other")
    bdom = {}
    for f in sorted((ROOT / "cscl/library").glob("**/*.yaml")):
        D = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for b in D.get("base") or {}:
            bdom[b] = D.get("domain")
    for b in sorted(T.B):
        rows[f"base {b}"] = {"in_ontology": int(bdom.get(b) == "ontology")}
        print("base", b, bdom.get(b))
    for layer in LOWER:
        rs = [r for k, r in rows.items() if k.startswith(f"word {layer} ")]
        print(layer, {c: f"{sum(r[c] for r in rs)}/{len(rs)}" for c in ("extends_only", "reducible", "other")})
    (OUT / "sys_lower.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_lower.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
