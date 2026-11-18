"""仮説 h_case_frame_formula（に依存しない(動詞の格の枠, 表示語)）を確かめる: 動詞の格の枠（相手に付く助詞）は、
動詞の式（holds に書いた基礎の関係）から決まるか。表示語の形から決めるより、よく当たるか。
結果を見る前に、この説明と手順と正解の表を登録した（issue #167）。

正解の表 GOLD: h_ja_case_frame（#165）で数えた 57 の動詞それぞれについて、今の表示語で
  「〈始点〉が〈終点〉＿〈表示語〉」と言うとき、＿に入る助詞（を, に, の, と, で, について, が）。
  「で書かれる」のように表示語が助詞で始まるものは、その助詞を正解にする。
  一人（Claude）が表示語だけを見て付けた。holds は見ずに付けた（ただし ontology の動詞の holds は、
  以前の会話で見たことがある）。この表は判断で、外の基準ではない。
式の署名 S(v): v とその祖先の holds の項を (is, from, to, neg) の組の集合にしたもの。holds がなければ空集合。
予測（leave-one-out）:
  式から: v を除いた、同じ S を持つ動詞の GOLD の最頻値（同数なら辞書順で最初）。ほかに同じ S がなければ外れ。
  表示語の形から（#165 の F）: 表示語が助詞で始まればその助詞、名詞の語＋助詞なら「の」、ほかは「を」。
  一つの枠: v を除いた全動詞の GOLD の最頻値。
数える量（要約）:
  n_verbs, n_sig（異なる署名の数）, n_empty（holds のない動詞の数）, singletons（ほかに同じ署名がない動詞の数）
  acc_formula, acc_display, acc_single  それぞれの予測が GOLD と一致した割合
判定（tc が通るもとで）:
  acc_formula ≥ 0.7 かつ acc_formula > max(acc_display, acc_single) なら支持（v_support）。
  acc_formula ≤ max(acc_display, acc_single) なら反証（v_contradict）。
  そのほか（上回るが 0.7 に届かない）は mixed（支持と反証の両方の観察を置く）。
見込み: 領域（exp, subj）の動詞の多くは holds を持たないので、空の署名に集まり、式からの予測は一つの枠に近づく。
  なので反証の見込みもある。反証なら、今の式（holds）は格の枠を決めるには足りず、枠は表示語（語彙）の側にある、と読む。

行（sys_case_frame_formula.json）:
  "summary 要約": 上の数
  "verb <v>": formula, display, single（予測が当たれば 1）, singleton（0 か 1）
  "texts": 動詞ごとの表示語、GOLD、署名、三つの予測（記述）

使い方:
  python exp/experiments/sys_case_frame_formula.py
"""
import collections
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
P1 = ("について", "から", "より", "に", "で", "と", "を", "へ")
NOUN_HEAD = re.compile(r"^[一-鿿゠-ヿ]")

GOLD = {
    "exp.v_adopt": "を", "exp.v_answer": "に", "exp.v_challenge": "に", "exp.v_expose": "を", "exp.v_judge": "を",
    "exp.v_judge_definition": "の", "exp.v_read": "を", "exp.v_report": "を", "exp.v_see": "を", "exp.v_speak": "を",
    "exp.v_teach": "を", "exp.v_use": "を", "exp.v_withdraw": "を",
    "ontology.is": "に", "ontology.p": "と", "ontology.v_agree": "と", "ontology.v_come_after": "の",
    "ontology.v_come_before": "の", "ontology.v_compose": "の", "ontology.v_depend": "に", "ontology.v_design": "を",
    "ontology.v_express": "で", "ontology.v_involve": "に", "ontology.v_not_after": "の", "ontology.v_not_before": "の",
    "ontology.v_perform": "を", "ontology.v_refer": "を", "ontology.v_stage": "の", "ontology.v_trigger": "を",
    "runtime.v_execute": "を",
    "std.v_close": "について", "std.v_compute": "を", "std.v_freeze": "を", "std.v_sum": "と", "std.v_vary": "を",
    "subj.v_allocate": "に", "subj.v_approve": "を", "subj.v_begin": "に", "subj.v_classify": "の", "subj.v_contract": "と",
    "subj.v_employ": "を", "subj.v_end": "に", "subj.v_live": "に", "subj.v_located": "に", "subj.v_pay": "に",
    "subj.v_place": "を", "subj.v_register": "を", "subj.v_seated": "の", "subj.v_sell": "を", "subj.v_store": "に",
    "subj.v_weekday_of": "の",
    "syntax.v_above": "を", "syntax.v_assume": "を", "syntax.v_collect": "を", "syntax.v_derive": "を",
    "syntax.v_measure": "を", "syntax.v_require": "が",
}


def display_frame(vd):
    for p in P1:
        if vd.startswith(p):
            return p
    if any(vd.find(p) > 0 for p in P1) and NOUN_HEAD.match(vd):
        return "の"
    return "を"


def mode(xs):
    c = collections.Counter(xs)
    return min(c, key=lambda k: (-c[k], k)) if c else None


def signature(T, v):
    out = set()
    for x in [v] + T.ancestors(v):
        for h in T.N[x].get("holds") or []:
            out.add((h.get("is"), str(h.get("from")), str(h.get("to")), bool(h.get("neg"))))
    return frozenset(out)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, _, _ = tc.build()
    errors = len(tc.errors)
    verbs = sorted(GOLD)
    missing = [v for v in verbs if v not in T.N]
    verbs = [v for v in verbs if v in T.N]
    sig = {v: signature(T, v) for v in verbs}
    by_sig = collections.defaultdict(list)
    for v in verbs:
        by_sig[sig[v]].append(v)
    rows, texts, hit = {}, {}, collections.Counter()
    for v in verbs:
        others = [u for u in by_sig[sig[v]] if u != v]
        p_f = mode(GOLD[u] for u in others)
        p_d = display_frame(T.N[v].get("display", v))
        p_s = mode(GOLD[u] for u in verbs if u != v)
        r = {"formula": int(p_f == GOLD[v]), "display": int(p_d == GOLD[v]), "single": int(p_s == GOLD[v]),
             "singleton": int(not others)}
        hit.update({k: r[k] for k in ("formula", "display", "single")})
        rows[f"verb {v}"] = r
        texts[v] = {"display": T.N[v].get("display", v), "gold": GOLD[v], "signature": sorted(map(list, sig[v])),
                    "pred_formula": p_f, "pred_display": p_d, "pred_single": p_s}
    n = len(verbs)
    summ = {"errors": errors, "missing": len(missing), "n_verbs": n, "n_sig": len(by_sig),
            "n_empty": sum(1 for v in verbs if not sig[v]), "singletons": sum(r["singleton"] for r in rows.values()),
            "acc_formula": round(hit["formula"] / n, 4), "acc_display": round(hit["display"] / n, 4),
            "acc_single": round(hit["single"] / n, 4)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_case_frame_formula.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for v, t in texts.items():
        print(v, t["display"], t["gold"], t["pred_formula"], t["pred_display"], len(t["signature"]))


if __name__ == "__main__":
    main()
