"""仮説 h_layers_neg_dual（依存する(層の置き場, ステップ上の量化・シグネチャから定まる分類)）を確かめる:
動詞の端への否定の限定を、肯定の限定と同じステップ上の量化（¬◇ = □¬ と ◇ の双対）と読み、変位の根拠に数えると、
残る違反が消えるか。結果を見る前に、この説明と手順と判定を登録した（issue #202）。

前の実験（sys_layers_exists_change, 支持）: 外れ 30 のうち 29 が動かせた。残る違反は 1 組で、否定の mod
（runtime.halted: mod {of: [v_execute, to], neg: true} → runtime.v_execute）。

双対の読み:
  肯定の限定 of: [v, 端]       あるステップで、v のその端に立つ（◇）
  否定の限定 of: [v, 端], neg   どのステップでも、v のその端に立たない（¬◇ = □¬）
  どちらもステップの上の量化で、量化する軸は同じ。符号（否定か肯定か）は軸を変えない。
  だから、v が変位（exists のほかの基礎の関係を変える動詞）なら、否定の限定も、そのノードを変位の側に置く根拠になる。

ここで変えるのは一つだけ: 分類の change に、「届いたノードが、変位の動詞を of の動詞とする否定の限定を持つ」を足す。
否定の辺の先をたどることはしない（その先のノードの holds・pre・post や、その先の辺は数えない）。見るのは、
否定の限定の of の動詞そのものが変位かどうかだけ。
ほかは sys_layers_exists_change と同じ（form の辺をたどる、exists だけの動詞は変位に数えない、最上位の always・sometime
は数えない、still→ontology・refer→syntax・change→runtime、ほかの領域は動かさない、外れを一度に動かす、層の法則は
T.refs と uses）。

行（sys_layers_neg_dual.json）: sys_layers_exists_change と同じ列。
  "summary 要約" に n_neg_moving（否定の限定で変位の動詞を指すノードの数。数えるだけ）を足す。

予想: halted は runtime に残り、違反は 0 組。ほかに否定の限定で変位の動詞を指すノードがあれば、それも runtime 寄りに
なり、外れが増えるかもしれない（数えていない）。

判定（ec が通るもとで）:
  n_violations = 0 かつ movable の率が 0.9667（前の 29/30）以上なら支持（v_support）。外れが 0 のとき、率は 1 とする。
  n_violations ≥ 1、または率が 0.5 未満なら反証（v_contradict）。
  そのほか（違反は 0 だが、率が下がった）は mixed。

開示:
  前の実験の違反の一覧を見てから、この規則を選んだ。sys_layers（否定の辺をたどった版）では syntax の多くが change に
  寄ったので、ここでは否定の辺をたどらず、一段だけ見る。
  「符号は軸を変えない」は、always・sometime を足したときの読み（□ と ◇ は同じステップの列の上の量化）から来ている。
  halted を □¬ の式（always の原子）で書き直すことは、この実験ではしない。今の always の原子は項に self しか使えず、
  「self の後に来る状態がない」は存在量化の変数が要るので書けない（足りない形として記録する）。

使い方:
  python exp/experiments/sys_layers_neg_dual.py
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
    from sys_layers_exists_change import moves  # noqa: E402

OUT = ROOT / "exp/experiments/results"
PREV_RATE = 29 / 30


def neg_moving(T, x):
    n = T.N[x]
    ms = n.get("mod") or []
    lims = ([n] if "of" in n else []) + [m for m in (ms if isinstance(ms, list) else [ms]) if isinstance(m, dict)]
    return any(m.get("neg") and m.get("of") and m["of"][0] in T.N and moves(T, m["of"][0]) for m in lims)


def classify(T, nid):
    seen, todo = {nid}, [nid]
    while todo:
        for b in edges_role(T, todo.pop()):
            if b not in seen:
                seen.add(b)
                todo.append(b)
    change = any(moves(T, x) or neg_moving(T, x) for x in seen)
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
    negs = sorted(x for x in T.N if neg_moving(T, x))
    rows["summary 要約"] = {"n_nodes": len(cls), "n_agree": len(cls) - len(outs), "n_out": len(outs),
                          "n_movable": n_mov, "n_violations": len(bad),
                          "n_form_violations": sum(k[0] for k in kinds.values()),
                          "n_neg_violations": sum(k[1] for k in kinds.values()),
                          "n_neg_moving": len(negs), "errors": errors}
    (OUT / "sys_layers_neg_dual.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_layers_neg_dual.py", "_commit": commit, "rows": rows,
         "outliers": detail, "neg_moving": negs,
         "violations": sorted(f"{a} -> {b}" + (" form" if kinds[(a, b)][0] else "") + (" neg" if kinds[(a, b)][1] else "")
                              for a, b in bad)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    s = rows["summary 要約"]
    print(json.dumps(s, ensure_ascii=False))
    print("neg_moving:", negs)
    for n, x in detail.items():
        print(n, x["from"], "->", x["to"], "movable" if not x["violations"] else x["violations"][:3])
    rate = n_mov / len(outs) if outs else 1.0
    if s["n_violations"] == 0 and rate >= PREV_RATE:
        verdict = "支持"
    elif s["n_violations"] >= 1 or rate < 0.5:
        verdict = "反証"
    else:
        verdict = "mixed"
    print("movable の率:", round(rate, 4), "判定:", verdict)


if __name__ == "__main__":
    main()
