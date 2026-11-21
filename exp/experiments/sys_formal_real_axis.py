"""h_formal_real_by_law と h_real_axis_by_domain を確かめる: 軸（動詞）の形式・実在の別は法則で決まり、実在の軸は一つの領域に属するか。

仮説（claims.yaml。登録 #611）:
  h_formal_real_by_law: v_refer(h, v_depend(syntax.axis, syntax.law_rule))。軸が形式的か実在的かは法則で決まる。
  h_real_axis_by_domain: v_refer(h, v_depend(syntax.axis, syntax.domain))。実在的な軸は領域に属し、形式的な軸はどの領域も使える。
体系を読むだけ（書き換えない）。

いまの体系に置いた代理（開示）:
  軸 = 動詞（top_o の下で、holds・pre・post のどれかを祖先まで含めて持つノード。#561 と同じ集まり）。
  法則で決まっている（形式）= どこかの領域で is が law_rule の個体を from に持つ事実の to の式に、その動詞が現れる。
  実在 = 法則の式に現れない動詞。
  使う領域: sys_std_definition.py と同じ数え方（各ファイルの項目の値を display を除いてたどり、T.resolve で解決。
    自分の定義の項目は数えない）。共用 = 使う領域が二つ以上。
行（sys_formal_real_axis.json）: 動詞ごとに domain, uses, law（法則に現れるか）, shared。
  s: n_verb, n_law, n_real, n_shared, n_law_shared, n_real_single（実在で、使う領域が一つ以下）,
     tpr（法則のうち共用の割合）, tnr（実在のうち共用でない割合）, bal_acc（(tpr + tnr) / 2）, share_real_single（= tnr）。

判定（事前に決める）:
  tc.build が通らなければ外れ（状態を変えない）。
  h_formal_real_by_law（法則で分けた形式・実在が、共用か否かを言い当てる）:
    bal_acc >= 0.8 なら支持、bal_acc <= 0.6 なら反証、そのあいだは mixed。
  h_real_axis_by_domain（実在の軸は一つの領域に属する）:
    share_real_single >= 0.8 なら支持、< 0.5 なら反証、そのあいだは mixed。
開示:
  いまの体系には、空間・用途・感覚などの実在的な軸がほとんどない（#605）。ここでの「実在」は「法則の式に現れない動詞」
  という代理で、仮説の言う実在的な軸と同じとは限らない。体系の規模も小さい（h_observation_by_scale、未検証）。
  走らせる前に数は計算していない。
訂正 1（走らせて落ちたあと、数を見る前）: from が並び（list）の事実で TypeError になった。
  法則の事実は from が一つの個体なので、from が文字列の事実だけを見る。判定は変えない。
使い方:
  python exp/experiments/sys_formal_real_axis.py
"""
import contextlib
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
KEYS = ("holds", "pre", "post")


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
    out = root / "exp/experiments/results/sys_formal_real_axis.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    top_o = T.top_o

    def has_any(x):
        return any(N.get(y, {}).get(k) for y in [x] + T.ancestors(x) for k in KEYS)

    verbs = sorted(x for x in N if x != top_o and T.is_a(x, top_o) and has_any(x))
    vs = set(verbs)
    cfg = tc.yload((root / "cscl.yaml").read_text(encoding="utf-8"))
    files = [root / cfg["root"]]
    for pat in list(cfg.get("library") or []) + list(cfg.get("include") or []):
        files += sorted(root.glob(pat))
    uses = {v: set() for v in verbs}
    law = set()
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
                if r in vs and r != self_id:
                    uses[r].add(dom)
        for v in y.get("facts") or []:
            if isinstance(v, dict) and isinstance(v.get("from"), str) and v["from"] in laws:
                for w in strings(v.get("to")):
                    r = T.resolve(w, dom)
                    if r in vs:
                        law.add(r)
    shared = {v for v in verbs if len(uses[v]) >= 2}
    real = vs - law
    rows = {v: {"domain": T.domain(v), "uses": sorted(uses[v]), "law": v in law, "shared": v in shared} for v in verbs}
    tpr = len(law & shared) / len(law) if law else 0.0
    tnr = len(real - shared) / len(real) if real else 0.0
    s = {"n_verb": len(verbs), "n_law": len(law), "n_real": len(real), "n_shared": len(shared),
         "n_law_shared": len(law & shared), "n_real_single": len(real - shared),
         "tpr": tpr, "tnr": tnr, "bal_acc": (tpr + tnr) / 2, "share_real_single": tnr}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
