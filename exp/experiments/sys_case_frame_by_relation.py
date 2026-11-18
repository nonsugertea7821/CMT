"""仮説 h_case_frame_by_relation（依存する(動詞の格の枠, 基礎の節)）を確かめる: 動詞の格の枠は、基礎の関係の種類
（holds の項の is だけ。向き from/to と否定 neg を除く）で決まるか。結果を見る前に、この説明と手順を登録した。

背景: h_case_frame_formula の反証（#169, sys_case_frame_formula）で、holds の項を (is, from, to, neg) の組で
  まとめた署名からの予測は 0.386 で、表示語の形から（0.632）と一つの枠（0.491）を下回った。
  そのとき「の」を取る動詞が after と part の関係に集まるのに、向きと否定で署名が分かれていた（事後の気づき）。
  この仮説はその気づきから立てたもので、同じ 57 の動詞と同じ正解の表で確かめる。新しいデータではないので、
  支持でも弱い確かめにとどまる（開示）。
正解の表: sys_case_frame_formula.GOLD をそのまま使う（変えない）。
署名 R(v): v とその祖先の holds の項の is の集合。holds がなければ空集合。
予測（leave-one-out）: 式から = v を除いた、同じ R を持つ動詞の GOLD の最頻値（同数なら辞書順で最初）。
  ほかに同じ R がなければ外れ。表示語の形からと一つの枠は、sys_case_frame_formula と同じ。
数える量（要約）: n_verbs, n_sig, n_empty, singletons, acc_relation, acc_display, acc_single
  さらに holds を持つ動詞だけでの acc_relation_held と acc_display_held（記述。判定に使わない）
判定（tc が通るもとで。h_case_frame_formula と同じ基準）:
  acc_relation ≥ 0.7 かつ acc_relation > max(acc_display, acc_single) なら支持。
  acc_relation ≤ max(acc_display, acc_single) なら反証。そのほかは mixed。
見込み: holds のない 15 の動詞は変わらず空の署名に集まるので、全体では反証の見込みが高い。
  holds を持つ動詞だけでは上がる見込み（記述で見る）。

行（sys_case_frame_by_relation.json）:
  "summary 要約": 上の数
  "verb <v>": relation, display, single（予測が当たれば 1）, singleton, held（holds を持てば 1）
  "texts": 動詞ごとの表示語、GOLD、署名、予測

使い方:
  python exp/experiments/sys_case_frame_by_relation.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "exp/experiments")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
from sys_case_frame_formula import GOLD, display_frame, mode  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def relation_sig(T, v):
    return frozenset(h.get("is") for x in [v] + T.ancestors(v) for h in T.N[x].get("holds") or [])


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, _, _ = tc.build()
    errors = len(tc.errors)
    verbs = [v for v in sorted(GOLD) if v in T.N]
    sig = {v: relation_sig(T, v) for v in verbs}
    by_sig = collections.defaultdict(list)
    for v in verbs:
        by_sig[sig[v]].append(v)
    rows, texts = {}, {}
    for v in verbs:
        others = [u for u in by_sig[sig[v]] if u != v]
        p_r = mode(GOLD[u] for u in others)
        p_d = display_frame(T.N[v].get("display", v))
        p_s = mode(GOLD[u] for u in verbs if u != v)
        rows[f"verb {v}"] = {"relation": int(p_r == GOLD[v]), "display": int(p_d == GOLD[v]),
                             "single": int(p_s == GOLD[v]), "singleton": int(not others), "held": int(bool(sig[v]))}
        texts[v] = {"display": T.N[v].get("display", v), "gold": GOLD[v], "signature": sorted(sig[v]),
                    "pred_relation": p_r, "pred_display": p_d, "pred_single": p_s}
    R = list(rows.values())
    held = [r for r in R if r["held"]]
    n = len(R)
    summ = {"errors": errors, "n_verbs": n, "n_sig": len(by_sig), "n_empty": n - len(held),
            "singletons": sum(r["singleton"] for r in R),
            "acc_relation": round(sum(r["relation"] for r in R) / n, 4),
            "acc_display": round(sum(r["display"] for r in R) / n, 4),
            "acc_single": round(sum(r["single"] for r in R) / n, 4),
            "acc_relation_held": round(sum(r["relation"] for r in held) / len(held), 4),
            "acc_display_held": round(sum(r["display"] for r in held) / len(held), 4)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_case_frame_by_relation.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for v, t in texts.items():
        print(v, t["display"], t["gold"], t["pred_relation"], t["signature"])


if __name__ == "__main__":
    main()
