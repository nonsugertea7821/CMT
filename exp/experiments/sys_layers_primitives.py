"""仮説 h_layers_from_primitives（依存する(層の置き場, ステップ上の量化・種類について在ることを述べる場所・変数の範囲)）を
確かめる: 層 ontology・syntax・runtime の置き場は、幾何の読みで導く分類と、層の法則（layered）のもとで合わせられるか。
結果を見る前に、この説明と手順と判定を登録した（issue #190）。

幾何の読み（利用者との会話で決めた対応）:
  ontology  点（在ること）。種類について在ることを述べる場所。ステップをまたいで変わらない。
  runtime   変位（ステップ）。ステップの前（pre）と後（post）を持つ。
  syntax    点と変位のあいだの関係。述べる（refer）。
  signature 変数の範囲（any）。どの層の下にもある土台。この実験では動かさない。

分類（sys_layers の否定の辺をたどらない版と同じ規則。規則は変えない）:
  各ノードから、否定でない定義の辺（sys_layers.edges, pos_only=True）をたどって届くノードを集める。
    change  届いたノードに pre か post を持つ動詞がある      → runtime
    refer   change でなく、届いた holds・pre・post の原子に基礎の関係 refer がある → syntax
    still   どちらでもない                                  → ontology
  最上位の always・sometime は数えない。どのノードも extends で最上位に届くので、数えるとすべてが change か still に
  寄り、分類にならない。三つの形は、分類の名前（点・変位・範囲）の読みを与えるもので、届き方の規則には入れない。

導いた置き場: ontology・syntax・runtime のノードを、分類が示す層に置く。ほかの領域（signature・std・lang・exp・subj）の
ノードは今の領域のまま。
層の法則: ノード a が b を参照する（T.refs）なら、a の層から b の層が見える（自分か、uses を推移的にたどった先）。

行（sys_layers_primitives.json）。値はどれも 0 か 1。
  "node <n>":   ontology・syntax・runtime のノードごとに、{今の層}_{分類}（その組に 1）, agree（分類が今の層と合う）
  "out <n>":    外れたノード（agree = 0）ごとに、movable（導いた置き場で、n が参照するもの・n を参照するもの、のどの組も
                層の法則を満たす）
  "summary 要約": n_nodes, n_agree, n_out, n_movable, n_violations（導いた置き場での法則違反の組の数）, errors

判定（ec が通るもとで）:
  n_out = 0、または外れたノードがすべて movable なら支持（v_support）: 置き場は、点・変位・関係の分類から、
  層の法則を壊さずに導ける。
  movable の率が 0.5 未満なら反証（v_contradict）。
  そのほかは mixed。

登録の前に分かっていること（開示）:
  sys_layers（commit f33d9e8、そのあと main は大きく動いた）で、否定の辺をたどらない版の外れは 25 だった
  （ontology の refer 14・change 1、syntax の still 4、runtime の refer 6）。今の main での数は、まだ数えていない。
  ontology の refer の多く（concept, word, sentence, v_refer など）は、syntax から参照されているので、syntax に動かすと
  syntax の参照は保てるが、ontology のほかのノードが参照していれば違反になる。どちらになるかは数えていない。
  動かすのは一度に全部（導いた置き場）で、一つずつ動かす探索はしない。
  この実験は、三つの形が置き場を「決める」ことは示さない。示すのは、三つの形の読み（点・変位・関係）に沿った分類と
  今の層の法則が両立するかどうか。

使い方:
  python exp/experiments/sys_layers_primitives.py
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
    from sys_layers import classify  # noqa: E402

OUT = ROOT / "exp/experiments/results"
TO_LAYER = {"still": "ontology", "refer": "syntax", "change": "runtime"}
LAYERS = ("ontology", "syntax", "runtime")


def visible(O):
    vis = {}
    for d in O["domains"]:
        seen, todo = {d}, [d]
        while todo:
            for u in O["domains"][todo.pop()]["uses"]:
                if u not in seen:
                    seen.add(u)
                    todo.append(u)
        vis[d] = seen
    return vis


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    errors = len(tc.errors)
    if errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    vis = visible(O)
    place, cls = {}, {}
    for n in T.N:
        d = T.domain(n)
        place[n] = d
        if d in LAYERS:
            cls[n] = classify(T, n, True)
            place[n] = TO_LAYER[cls[n]]
    refs = {n: T.refs(n) for n in T.N}
    bad = {(a, b) for a in T.N for b in refs[a] if place[b] not in vis[place[a]]}
    rows, outs = {}, []
    for n in sorted(cls):
        d = T.domain(n)
        ag = int(place[n] == d)
        rows[f"node {n}"] = {f"{d}_{cls[n]}": 1, "agree": ag}
        if not ag:
            outs.append(n)
    detail = {}
    for n in outs:
        v = sorted(f"{a} -> {b}" for a, b in bad if n in (a, b))
        rows[f"out {n}"] = {"movable": int(not v)}
        detail[n] = {"from": T.domain(n), "to": place[n], "violations": v[:20]}
    n_mov = sum(rows[f"out {n}"]["movable"] for n in outs)
    rows["summary 要約"] = {"n_nodes": len(cls), "n_agree": len(cls) - len(outs), "n_out": len(outs),
                          "n_movable": n_mov, "n_violations": len(bad), "errors": errors}
    (OUT / "sys_layers_primitives.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_layers_primitives.py", "_commit": commit, "rows": rows,
         "outliers": detail, "violations": sorted(f"{a} -> {b}" for a, b in bad)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    for n, x in detail.items():
        print(n, x["from"], "->", x["to"], "movable" if not x["violations"] else x["violations"][:3])
    rate = n_mov / len(outs) if outs else 1.0
    print("判定:", "支持" if rate == 1.0 else "反証" if rate < 0.5 else "mixed")


if __name__ == "__main__":
    main()
