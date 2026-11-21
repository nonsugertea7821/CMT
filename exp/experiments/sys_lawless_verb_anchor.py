"""h_formal_verbs_need_laws と h_lawless_verbs_are_real を確かめる（対）。

仮説（claims.yaml）: 登録 #615（issue #617・#618）。
  h_formal_verbs_need_laws: v_refer(h, v_refer(syntax.law_rule, V))。V は下の 6 語。
  h_lawless_verbs_are_real: v_refer(h, v_refer(syntax.domain, V))。
  出どころ: #614（法則に出ないのに複数の領域で使われる動詞が 31。そのうち ontology の語）。
  V = ontology の v_express, v_trigger, v_stage, v_involve, v_perform, v_come_after。

問い: 形式の語なら、どの領域で使っても同じ種類のものと組む（法則で書ける）。実在の語なら、領域ごとに組む相手が違う。
操作: 体系を読むだけ。
  使い: #614 と同じく、cscl.yaml の root・library・include の各ファイルで、nodes・individuals・axes の値と facts の
        一つ一つを「項」とし、項の中の文字列を T.resolve(w, 領域) で解決する。項が v を含むとき、その項は領域 d で v を使う
        （v のノード自身の定義の項は除く）。
  相手: v を使う項の中の、v 以外の解決できた語。
  錨: 相手 x について、x 自身か、T.ancestors(x) の順で最初の、T.domain が ontology のもの。なければ数えない。
  A_v,d: 領域 d で v を使う項の相手の錨の集まり。
  J(v): v を使う領域が二つ以上のとき、領域の組ごとの A の Jaccard の平均（組の両方が空なら 1）。一つ以下なら数えない。
  形式: J(v) >= 0.5。実在: J(v) < 0.5。
行（sys_lawless_verb_anchor.json）: v ごとに domains, anchors（領域ごと）, J。
  s: n_verb（J を数えた語の数）, n_formal, n_real, mean_J。

判定（事前に決める）:
  tc.build が通らないか n_verb < 4 なら外れ（状態を変えない）。
  h_formal_verbs_need_laws: n_formal >= 4 で支持、n_formal <= 2 で反証、3 で mixed。
  h_lawless_verbs_are_real: n_real >= 4 で支持、n_real <= 2 で反証、3 で mixed。
開示: 二つは補い合う読み方で、片方の支持はもう片方の反証にほぼなる（n_verb = 6 のとき）。
  錨を ontology の種類にとるので、ontology の上の層の語（continuant など）に寄るほど J は高く出る。
  走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_lawless_verb_anchor.py
"""
import contextlib
import io
import itertools
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
V = ["ontology.v_express", "ontology.v_trigger", "ontology.v_stage", "ontology.v_involve", "ontology.v_perform",
     "ontology.v_come_after"]


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k != "display":
                yield from strings(x)


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_lawless_verb_anchor.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N

    def anchor(x):
        for y in [x] + list(T.ancestors(x)):
            if T.domain(y) == "ontology":
                return y
        return None

    cfg = tc.yload((root / "cscl.yaml").read_text(encoding="utf-8"))
    files = [root / cfg["root"]]
    for pat in list(cfg.get("library") or []) + list(cfg.get("include") or []):
        files += sorted(root.glob(pat))
    A = {v: {} for v in V}
    for f in files:
        y = tc.yload(f.read_text(encoding="utf-8")) or {}
        dom = y.get("domain")
        if not isinstance(dom, str):
            continue
        items = []
        for sec in ("nodes", "individuals", "axes"):
            for k, v in (y.get(sec) or {}).items():
                items.append((f"{dom}.{k}" if sec == "nodes" else None, v))
        for v in y.get("facts") or []:
            items.append((None, v))
        for self_id, v in items:
            rs = [T.resolve(w, dom) for w in strings(v)]
            rs = [r for r in rs if r in N]
            for verb in V:
                if verb in rs and verb != self_id:
                    a = A[verb].setdefault(dom, set())
                    for r in rs:
                        if r != verb:
                            an = anchor(r)
                            if an:
                                a.add(an)
    rows, Js = {}, []
    n_formal = n_real = 0
    for verb in V:
        doms = sorted(A[verb])
        row = {"domains": doms, "anchors": {d: sorted(A[verb][d]) for d in doms}, "J": None}
        if len(doms) >= 2:
            js = []
            for a, b in itertools.combinations(doms, 2):
                u = A[verb][a] | A[verb][b]
                js.append(len(A[verb][a] & A[verb][b]) / len(u) if u else 1.0)
            J = sum(js) / len(js)
            row["J"] = J
            Js.append(J)
            n_formal += J >= 0.5
            n_real += J < 0.5
        rows[verb] = row
    s = {"n_verb": len(Js), "n_formal": n_formal, "n_real": n_real, "mean_J": sum(Js) / len(Js) if Js else 0.0}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
