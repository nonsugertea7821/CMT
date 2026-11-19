"""仮説 h_case_frame_by_signature（依存する(動詞の格の枠, シグネチャから定まる分類)）を確かめる:
動詞の格の枠は、動詞の式をシグネチャの語まで落とした分類で決まるか。結果を見る前に、この説明と手順を登録した。

系列: h_case_frame_formula（holds の (is, from, to, neg) の組、0.386）と h_case_frame_by_relation
  （holds の is の集合、0.4912）はどちらも反証。どちらも holds だけを見ていて、15 の動詞が空の署名に集まった。
  h_case_frame_by_role は、指すものが違っていたので取り下げ、この仮説に置き換えた（2de6fc6）。
  同じ 57 の動詞と同じ正解の表（sys_case_frame_formula.GOLD、一人が表示語から付けた判断）で確かめる。
  新しいデータではないので、支持でも弱い確かめにとどまる（開示）。
シグネチャから定まる分類 C(v):
  鍵 from, to, new_kind, holds, pre, post のそれぞれについて、v とその祖先を近い順にたどり、最初に値を持つものを取る。
  from, to, new_kind の値（種類の名前）は、その種類の最上位の祖先（祖先がなければその種類）に置き換える。
  holds, pre, post の項は (is, from, to, neg) の組にする（from と to は位置の語 from/to/new のまま）。
  extends は使わない（名前で読まない。祖先をたどるのに使うだけ）。display と gloss は使わない。
  C(v) は、この 6 つの鍵の値を正規の形（並びは並べ替える）にした組。
予測（leave-one-out）: v を除いた、同じ C を持つ動詞の GOLD の最頻値（同数なら辞書順で最初）。ほかになければ外れ。
  表示語の形からと一つの枠は、sys_case_frame_formula と同じ。
記述（判定に使わない）: 端の種類を落とした分類 C0(v)（holds, pre, post の組だけ）での acc_coarse。
数える量（要約）: errors, n_verbs, n_class, singletons, acc_signature, acc_display, acc_single, acc_coarse, n_class_coarse
判定（tc が通るもとで。前の二つと同じ基準）:
  acc_signature ≥ 0.7 かつ acc_signature > max(acc_display, acc_single) なら支持。
  acc_signature ≤ max(acc_display, acc_single) なら反証。そのほかは mixed。
開示: 手順を書く前に、いくつかの動詞のノードの形（from, to, new_kind, pre, post, holds）を見た。GOLD と予測の対は見ていない。
見込み: 端の種類を最上位に落とすと、多くの動詞が continuant→continuant に集まり、holds/pre/post を持たない動詞は
  一つの類に寄る。前の二つと同じく反証の見込みが高い。

行（sys_case_frame_by_signature.json）:
  "summary 要約": 上の数
  "verb <v>": signature, display, single, coarse（予測が当たれば 1）, singleton
  "texts": 動詞ごとの表示語、GOLD、分類、予測

使い方:
  python exp/experiments/sys_case_frame_by_signature.py
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
KINDS = ("from", "to", "new_kind")
FORMS = ("holds", "pre", "post")


def nearest(T, v, k):
    for x in [v] + T.ancestors(v):
        if k in T.N[x]:
            return T.N[x][k]
    return None


def top(T, k):
    if not isinstance(k, str) or k not in T.N:
        return str(k)
    a = T.ancestors(k)
    return a[-1] if a else k


def forms(T, v):
    out = []
    for k in FORMS:
        fs = nearest(T, v, k) or []
        out.append((k, tuple(sorted((str(f.get("is")), str(f.get("from")), str(f.get("to")), bool(f.get("neg")))
                                    for f in fs if isinstance(f, dict)))))
    return tuple(out)


def sig_class(T, v):
    return tuple((k, top(T, nearest(T, v, k))) for k in KINDS) + forms(T, v)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, _, _ = tc.build()
    errors = len(tc.errors)
    verbs = [v for v in sorted(GOLD) if v in T.N]
    C = {v: sig_class(T, v) for v in verbs}
    C0 = {v: forms(T, v) for v in verbs}
    by_c, by_c0 = collections.defaultdict(list), collections.defaultdict(list)
    for v in verbs:
        by_c[C[v]].append(v)
        by_c0[C0[v]].append(v)
    rows, texts = {}, {}
    for v in verbs:
        others = [u for u in by_c[C[v]] if u != v]
        p_c = mode(GOLD[u] for u in others)
        p_c0 = mode(GOLD[u] for u in by_c0[C0[v]] if u != v)
        p_d = display_frame(T.N[v].get("display", v))
        p_s = mode(GOLD[u] for u in verbs if u != v)
        rows[f"verb {v}"] = {"signature": int(p_c == GOLD[v]), "display": int(p_d == GOLD[v]),
                             "single": int(p_s == GOLD[v]), "coarse": int(p_c0 == GOLD[v]), "singleton": int(not others)}
        texts[v] = {"display": T.N[v].get("display", v), "gold": GOLD[v], "class": repr(C[v]),
                    "pred_signature": p_c, "pred_coarse": p_c0, "pred_display": p_d, "pred_single": p_s}
    R = list(rows.values())
    n = len(R)
    summ = {"errors": errors, "n_verbs": n, "n_class": len(by_c), "n_class_coarse": len(by_c0),
            "singletons": sum(r["singleton"] for r in R)}
    for k in ("signature", "display", "single", "coarse"):
        summ[f"acc_{k}"] = round(sum(r[k] for r in R) / n, 4)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_case_frame_by_signature.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for v, t in texts.items():
        print(v, t["display"], t["gold"], t["pred_signature"], t["class"])


if __name__ == "__main__":
    main()
