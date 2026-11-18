"""仮説 h_layers_role_edges（依存する(層の置き場, ステップ上の量化・種類について在ることを述べる場所・変数の範囲・役割)）を
確かめる: 分類の辺に役割の形（form）を足すと、sys_layers_primitives で層の法則を壊した役割の参照が消えるか。
結果を見る前に、この説明と手順と判定を登録した（issue #195）。

前の実験（sys_layers_primitives, mixed）: 外れ 28 のうち 23 が動かせた。違反の組 7 のうち 5 組は、役割
（referrer, agreeing, agreed, designer, designed）が form で動詞を参照するのに、分類の辺が form をたどらないために出た。
残る 2 組は、否定の mod（natural_language → v_design, halted → v_execute）。

ここで変えるのは一つだけ: 分類でたどる辺に、form の先の動詞（form: [動詞, 端] の動詞）を足す。
ほかは sys_layers_primitives と同じ（否定の辺はたどらない、最上位の always・sometime は数えない、
still→ontology・refer→syntax・change→runtime、ほかの領域は動かさない、外れを一度に動かす、層の法則は T.refs と uses）。

行（sys_layers_role_edges.json）。値はどれも 0 か 1、または数。
  "node <n>":   {今の層}_{分類}, agree
  "out <n>":    movable
  "summary 要約": n_nodes, n_agree, n_out, n_movable, n_violations, n_form_violations（参照する側が form でその先を
                参照している違反の組の数）, n_neg_violations（参照する側が否定の mod でその先を参照している違反の組の数）, errors

予想（登録の時点）: 役割は動詞といっしょに動くので n_form_violations = 0。違反は否定の mod の 2 組だけが残る。

判定（ec が通るもとで）:
  n_form_violations = 0 かつ movable の率が 0.8214（前の実験の 23/28）以上なら支持（v_support）:
  役割の辺を分類に入れると、役割による違反は消え、置き場の導出は悪くならない。
  n_form_violations > 0、または movable の率が 0.5 未満なら反証（v_contradict）。
  そのほか（form の違反は消えたが、率が下がった）は mixed。

開示:
  前の実験の外れと違反の一覧を見てから、この変更を選んだ。変更は form の一つに限り、否定の辺は扱わない。
  役割が動くと、役割を mod の with で参照するノードの分類や違反が変わるかもしれない。それは数えていない。
  否定の 2 組が残っても、この判定では支持になりうる。否定の扱いは別の問いとして残す。

使い方:
  python exp/experiments/sys_layers_role_edges.py
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
    from sys_layers import edges  # noqa: E402
    from sys_layers_primitives import visible, TO_LAYER, LAYERS  # noqa: E402

OUT = ROOT / "exp/experiments/results"
PREV_RATE = 23 / 28


def edges_role(T, nid):
    out = edges(T, nid, True)
    f = T.N[nid].get("form")
    if isinstance(f, list) and f and f[0] in T.N:
        out.append(f[0])
    return out


def classify(T, nid):
    seen, todo = {nid}, [nid]
    while todo:
        for b in edges_role(T, todo.pop()):
            if b not in seen:
                seen.add(b)
                todo.append(b)
    change = any("pre" in T.N[x] or "post" in T.N[x] for x in seen)
    rels = {a["is"] for x in seen for k in ("holds", "pre", "post") for a in T.N[x].get(k) or [] if isinstance(a, dict)}
    return "change" if change else "refer" if "refer" in rels else "still"


def via(T, a, b):
    n = T.N[a]
    f = n.get("form")
    form = isinstance(f, list) and f and f[0] == b
    ms = n.get("mod") or []
    lims = ([n] if "of" in n else []) + [m for m in (ms if isinstance(ms, list) else [ms]) if isinstance(m, dict)]
    neg = any(m.get("neg") and b in ((m.get("of") or [None])[0], m.get("with")) for m in lims)
    return form, neg


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
            cls[n] = classify(T, n)
            place[n] = TO_LAYER[cls[n]]
    bad = {(a, b) for a in T.N for b in T.refs(a) if place[b] not in vis[place[a]]}
    kinds = {p: via(T, *p) for p in bad}
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
                          "n_movable": n_mov, "n_violations": len(bad),
                          "n_form_violations": sum(k[0] for k in kinds.values()),
                          "n_neg_violations": sum(k[1] for k in kinds.values()), "errors": errors}
    (OUT / "sys_layers_role_edges.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_layers_role_edges.py", "_commit": commit, "rows": rows,
         "outliers": detail,
         "violations": sorted(f"{a} -> {b}" + (" form" if kinds[(a, b)][0] else "") + (" neg" if kinds[(a, b)][1] else "")
                              for a, b in bad)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    s = rows["summary 要約"]
    print(json.dumps(s, ensure_ascii=False))
    for n, x in detail.items():
        print(n, x["from"], "->", x["to"], "movable" if not x["violations"] else x["violations"][:3])
    rate = n_mov / len(outs) if outs else 1.0
    if s["n_form_violations"] == 0 and rate >= PREV_RATE:
        verdict = "支持"
    elif s["n_form_violations"] > 0 or rate < 0.5:
        verdict = "反証"
    else:
        verdict = "mixed"
    print("movable の率:", round(rate, 4), "判定:", verdict)


if __name__ == "__main__":
    main()
