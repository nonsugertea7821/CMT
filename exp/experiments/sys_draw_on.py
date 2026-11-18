"""体系そのものを数える: 実行の後の「読み」（解釈）を、コメントでなく式で書けるか。仮説の確かめではない（観察）。
結果を見る前に、この説明と手順を登録した。

背景（会話）: 体系のファイルにコメントを足さない取り決めにした。claims.yaml のコメントの多くは「実行の後の読み（登録していない）」
  で、解釈を書く場所がコメントしかなかった。体系には仮説の形（仮説の個体、v_refer の中身、状態の種類、v_support / v_contradict）が
  ある。ただし hyp_untested は「支持する観察も反する観察もない仮説」と式で定義されている（exp.yaml）ので、見た観察から作った読みを
  v_support で結ぶと未検証でなくなる。データを見て作った読みを同じデータで支持されたとしないのは正しい。足りないのは「観察から
  着想した（支持ではない）」という関係。
操作（この手順の登録のあと、測る前に行う）:
  1. exp/src/exp.yaml に、basis と v_ground の形にならって次の2つを足す（ほかは変えない）:
       inspiration: {display: 着想のもとの観察, extends: observation, mod: {of: [v_depend, to], with: hypothesis}, many: true}
       v_draw_on: {display: から着想する, extends: v_depend, from: hypothesis, to: inspiration}
  2. cscl/design/claims.yaml に、次の3つの読みを、未検証の仮説（is: exp.hyp_untested）として書く。中身は v_refer で書き、
     着想のもとの観察を v_draw_on で結ぶ。中身に要る語は、今ある語を先に使い、なければ式を持つノードとして claims に足す。
     コメントは書かない。元のコメントは消さない（消すのは別の手順）。
       R1（sys_after の読み）: 一つの after が、時間・値の大小・並びに使われていて、端の種類だけでは時間の順序を見分けられない。
          着想のもと: o_sys_after_time_rare, o_sys_after_mostly_used
       R2（sys_specific_depth の読み）: 浅い端だけで定義された概念は、正しい下位も、違反の下位も集める。
          着想のもと: o_sys_specific_depth_v_mostly_shallow, o_sys_specific_depth_c_rarely_shallow
       R3（sys_lower の読み）: syntax は ontology の意味を式で使っている（組み替えの本体は syntax の側）。
          着想のもと: o_sys_lower_syntax_uses_ontology, o_sys_lower_base_in_ontology
     中身の書き方は私が決める（判断が入る）。書いた式は結果の commit にそのまま残す。

数え方（引数 before / after）:
  errors       型検査の誤りの数
  V            違反の組の数（sys_kind_ref と同じ数え方: r_candidate のうち acc[y] ⊆ has[x] かつ acc[y] ⊄ acc[x]）
  new_V        before にない違反の組の数
  new_nodes    before にないノードの数（exp と lang の領域）
  thin         new_nodes のうち、自前の式（r_own）が 1 個以下のもの
  drawn        claims.yaml の v_draw_on の事実の数（領域の事実は導いた事実に入らないので、ファイルから数える）
判定: after で errors 0 かつ new_V 0 なら「読みは、v_draw_on を足すだけで、式として書ける」。満たさないものは内容を書いて外れとする。
  new_nodes と thin は、中身の語がどれだけ足りないか、足した語がどれだけ display に頼るかの記述で、判定には使わない。
登録の前に分かっていること:
  - 型検査は、個体の状態の種類（hyp_untested など）を、支持・反証の事実と照らしていない。未検証の仮説に v_support を足しても
    誤りは 0 のまま（下調べで確かめた）。今のデータでは、仮説 70 個の状態と支持・反証の事実は、すべて合っている（手で数えた）。
    なので、この実験の判定は、着想を支持として書いても通ってしまう。それを分けるのは式（v_draw_on が v_agree の下にないこと）だけ。
  - 読みの中身に使える語は、claims と exp にほとんどない（過大拡張、端の深さ、時間の読みに当たるノードはない）。
見込み: errors 0、new_V 0。new_nodes は 3 から 6、そのうち半分以上が thin（中身の語は display に頼る）。

行（sys_draw_on_<引数>.json）:
  "summary 要約": errors, V, new_V, new_nodes, thin, drawn
  "V x→y":        1
  "node n":       own（自前の式の数。before にないノードだけ）

使い方:
  python exp/experiments/sys_draw_on.py before|after
"""
import collections
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


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rel = lambda r: F.by.get(r, set())

    def two(r):
        d = collections.defaultdict(set)
        for t in rel(r):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    acc, has, own = two("r_acc"), two("r_has"), two("r_own")
    V = sorted((x, y) for x, y in rel("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
    nodes = sorted(n for n in T.N if n.split(".")[0] in ("exp", "lang"))
    import yaml
    claims = yaml.safe_load((ROOT / "cscl/design/claims.yaml").read_text(encoding="utf-8"))
    drawn = sum(1 for f in claims.get("facts") or [] if isinstance(f, dict) and str(f.get("is", "")).split(".")[-1] == "v_draw_on")
    if label == "before":
        old_V, old_nodes = set(), set(nodes)
        new = []
    else:
        prev = json.loads((OUT / "sys_draw_on_before.json").read_text(encoding="utf-8"))
        old_V = {tuple(k[2:].split("→")) for k in prev["rows"] if k.startswith("V ")}
        old_nodes = set(prev["nodes"])
        new = [n for n in nodes if n not in old_nodes]
    summ = {"errors": len(tc.errors), "V": len(V), "new_V": sum(1 for p in V if p not in old_V) if label != "before" else 0,
            "new_nodes": len(new), "thin": sum(1 for n in new if len(own[n]) <= 1), "drawn": drawn}
    rows = {"summary 要約": summ} | {f"V {a}→{b}": {"v": 1} for a, b in V} | {f"node {n}": {"own": len(own[n])} for n in new}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"rev": rev, "rows": rows} | ({"nodes": nodes} if label == "before" else {})
    (OUT / f"sys_draw_on_{label}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print([f"{a}→{b}" for a, b in V])
    for n in new:
        print(n, sorted(own[n]))
    for e in tc.errors:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"])
    main(sys.argv[1])
