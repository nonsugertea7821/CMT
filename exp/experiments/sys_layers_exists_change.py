"""仮説 h_layers_exists_change（依存する(層の置き場, 種類について在ることを述べる場所・シグネチャから定まる分類)）を確かめる:
pre・post が基礎の関係 exists だけを変える動詞を、変位でなく存在の変化（点の側）と数えると、層の法則の違反が減るか。
結果を見る前に、この説明と手順と判定を登録した。

前の実験（sys_layers_role_edges, 支持）: 外れ 33 のうち 30 が動かせた。違反の組は 2 で、どちらも否定の mod
（natural_language → v_design、halted → v_execute）。

ここで変えるのは一つだけ: 分類の change を「届いた動詞の pre・post に、exists のほかの基礎の関係がある」に狭める。
pre・post が exists だけの動詞（存在の変化。occurrent の sometime と同じ形）は、change の根拠にしない
（その動詞の holds の refer は、ほかと同じく refer の根拠になる）。
ほかは sys_layers_role_edges と同じ（form の辺をたどる、否定の辺はたどらない、最上位の always・sometime は数えない、
still→ontology・refer→syntax・change→runtime、ほかの領域は動かさない、外れを一度に動かす、層の法則は T.refs と uses）。

登録の時点で見ている動詞（pre か post を持つもの 16 のうち）:
  exists だけ: ontology.v_design, std.v_compute。std は動かさないので、効くのは v_design だけの見込み。
  runtime.v_execute は exists と after を変えるので、変位のまま。

行（sys_layers_exists_change.json）: sys_layers_role_edges と同じ列。
  "node <n>": {今の層}_{分類}, agree
  "out <n>": movable
  "summary 要約": n_nodes, n_agree, n_out, n_movable, n_violations, n_form_violations, n_neg_violations, errors

予想: v_design とその役割（designer, designed）は ontology に残り、natural_language → v_design の違反は消える。
halted → v_execute は残る。違反は 1 組。

判定（ec が通るもとで）:
  n_violations < 2 かつ movable の率が 0.9091（前の 30/33）以上なら支持（v_support）。
  外れが 0 のとき、率は 1 とする。
  n_violations ≥ 2、または率が 0.5 未満なら反証（v_contradict）。
  そのほか（違反は減ったが、率が下がった）は mixed。

開示:
  前の実験の違反の一覧と、16 の動詞の pre・post の関係を見てから、この規則を選んだ。
  exists だけを変える動詞が ontology.v_design と std.v_compute の 2 つしかないので、支持でも、規則が広く効くことは示さない。
  v_design と v_compute は基礎の関係の上で同じ形で、違いは端の種類だけ。v_compute が std にあることとの整合は、この実験の外。

使い方:
  python exp/experiments/sys_layers_exists_change.py
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
    from sys_layers_primitives import visible, TO_LAYER, LAYERS  # noqa: E402
    from sys_layers_role_edges import edges_role, via  # noqa: E402

OUT = ROOT / "exp/experiments/results"
PREV_RATE = 30 / 33


def moves(T, x):
    n = T.N[x]
    rels = {a["is"] for k in ("pre", "post") for a in n.get(k) or [] if isinstance(a, dict)}
    return bool(rels - {"exists"})


def classify(T, nid):
    seen, todo = {nid}, [nid]
    while todo:
        for b in edges_role(T, todo.pop()):
            if b not in seen:
                seen.add(b)
                todo.append(b)
    change = any(moves(T, x) for x in seen)
    rels = {a["is"] for x in seen for k in ("holds", "pre", "post") for a in T.N[x].get(k) or [] if isinstance(a, dict)}
    return "change" if change else "refer" if "refer" in rels else "still"


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
    (OUT / "sys_layers_exists_change.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_layers_exists_change.py", "_commit": commit, "rows": rows,
         "outliers": detail,
         "exists_only_verbs": sorted(x for x in T.N if ("pre" in T.N[x] or "post" in T.N[x]) and not moves(T, x)),
         "violations": sorted(f"{a} -> {b}" + (" form" if kinds[(a, b)][0] else "") + (" neg" if kinds[(a, b)][1] else "")
                              for a, b in bad)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    s = rows["summary 要約"]
    print(json.dumps(s, ensure_ascii=False))
    for n, x in detail.items():
        print(n, x["from"], "->", x["to"], "movable" if not x["violations"] else x["violations"][:3])
    rate = n_mov / len(outs) if outs else 1.0
    if s["n_violations"] < 2 and rate >= PREV_RATE:
        verdict = "支持"
    elif s["n_violations"] >= 2 or rate < 0.5:
        verdict = "反証"
    else:
        verdict = "mixed"
    print("movable の率:", round(rate, 4), "判定:", verdict)


if __name__ == "__main__":
    main()
