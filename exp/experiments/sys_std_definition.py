"""h_std_by_law と h_std_by_shared_use を確かめる: std の層に入る語は、法則で決まるか、領域の共用で決まるか。

仮説（claims.yaml。登録 #596）:
  h_std_by_law（#597）: v_refer(h, v_depend(std_layer, syntax.law_rule))。std の法則が推論に使う語が std。
  h_std_by_shared_use（#598）: v_refer(h, v_depend(std_layer, syntax.domain))。二つ以上の領域が共に使う語が std。
体系: 日本語の基礎語彙（ja_basic）と空の en_basic が入った main（#605 のあと）。体系を読むだけ（書き換えない）。

語の集まり:
  公理の層 = signature・ontology・syntax の領域のノード（std が依存する層。d_cscl_std_on_axiom）。
  候補 = tc.build のノードのうち、公理の層でないもの。
  A = 候補のうち、std の領域で定義されたノード（いまの std）。
  使う: 各ファイル（cscl.yaml の root・library・include）の各項目（nodes・individuals・facts・axes）の値を、
    display を除いてたどり、文字列を T.resolve(語, そのファイルの領域) で解決する。解決したノード n について、
    その項目の領域を「n を使う領域」に入れる。ノード n 自身の定義の項目は数えない。
  U = 候補のうち、使う領域が二つ以上のもの。
  L = std の個体のうち is が law_rule のものを from に持つ std の事実（v_assume・v_derive・v_require など）の
    to の式に現れ、解決して候補に入るノード。
行（sys_std_definition.json）: 候補のノードごとに domain, uses（領域の並び）, in_A, in_L, in_U。
  s: n_cand, n_A, n_L, n_U, n_AL, n_AU, jac_law（|A∩L|/|A∪L|）, jac_use（|A∩U|/|A∪U|）,
     n_U_by_domain（U の定義の領域ごとの数）, n_L_by_domain。

判定（事前に決める。二つの仮説に同じ線）:
  tc.build が通らなければ外れ（状態を変えない）。
  jac >= 0.8 なら支持、jac < 0.5 なら反証、そのあいだは mixed。jac_law は h_std_by_law に、jac_use は h_std_by_shared_use に。
開示:
  T.resolve は、その領域、signature、全体でただ一つ、の順に探す。v_use で使うと宣言した領域に限らない。
  走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_std_definition.py
"""
import contextlib
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
AXIOM = {"signature", "ontology", "syntax"}


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
    out = root / "exp/experiments/results/sys_std_definition.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    cfg = tc.yload((root / "cscl.yaml").read_text(encoding="utf-8"))
    files = [root / cfg["root"]]
    for pat in list(cfg.get("library") or []) + list(cfg.get("include") or []):
        files += sorted(root.glob(pat))
    cand = sorted(n for n in N if T.domain(n) not in AXIOM)
    uses = {n: set() for n in cand}
    L = set()
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
        laws = {k for k, v in (y.get("individuals") or {}).items() if isinstance(v, dict) and v.get("is") == "law_rule"}
        for self_id, v in items:
            for w in strings(v):
                r = T.resolve(w, dom)
                if r in uses and r != self_id:
                    uses[r].add(dom)
        if dom == "std":
            for v in y.get("facts") or []:
                if isinstance(v, dict) and v.get("from") in laws:
                    for w in strings(v.get("to")):
                        r = T.resolve(w, dom)
                        if r in uses:
                            L.add(r)
    A = {n for n in cand if T.domain(n) == "std"}
    U = {n for n in cand if len(uses[n]) >= 2}
    rows = {n: {"domain": T.domain(n), "uses": sorted(uses[n]), "in_A": n in A, "in_L": n in L, "in_U": n in U}
            for n in cand}
    jac = lambda X, Y: len(X & Y) / len(X | Y) if X | Y else 0.0
    by = lambda X: dict(sorted({d: sum(T.domain(n) == d for n in X) for d in {T.domain(n) for n in X}}.items()))
    s = {"n_cand": len(cand), "n_A": len(A), "n_L": len(L), "n_U": len(U), "n_AL": len(A & L), "n_AU": len(A & U),
         "jac_law": jac(A, L), "jac_use": jac(A, U), "n_U_by_domain": by(U), "n_L_by_domain": by(L)}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
