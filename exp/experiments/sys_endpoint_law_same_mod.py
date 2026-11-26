"""端の型の法則は、コードが退けたのと同じ限定を名指すか（h_endpoint_law_names_same_mod）。

系列:
  E38（#710）: 退けた誤り 170 のうち、法則を名指さない 69。その 53 は限定の端の型の検査（コードの自由な文）。
  #907（h_parent_endpoint_as_law_rule）: 上位の側の法則。C = 18/20 で支持（マージ済み）。
  #908（h_with_endpoint_as_law_rule）: 相手の側の法則（個体の下・種類の端の除外つき）。C = 30/34 で決まらない。
  どちらも「覆われる」を、同じ行の after のどこかに対応する法則の名があればよい、と数えていた。
  誤りの定義 N に対して法則が出たかで数え直すと（事後）、#907 は 15/20、#908 は 16/34。
  単位を上位・相手に分けるのも、書いた行の extends で比べていた。
  ここでは、コードの誤りごとに、同じ限定を法則が名指すかを確かめる:
    h_endpoint_law_names_same_mod: v_depend(type_check_result, [syntax.law_rule, syntax.mod])

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  写しの cscl/library/syntax/syntax.yaml に、#907 と #908 の法則をそのまま合わせて足す:
    overlap_down・overlap_up（r_overlap）、below_by_is、mod_fits_from・mod_fits_to（上位の側）、
    mod_with_fits_from・mod_with_fits_to（相手の側。端の型が ontology.kind の下なら外す）。
  法則の書き方は #907・#908 から変えない（ここで変えるのは物差しだけ）。

材料（モデルは走らせない）:
  E38・#903・#907・#908 と同じ: results/e37_writing_checker_version.json の cases のうち kind が written のもの（同じ (key, line) は 1 つ）。
  E38 の copy_now・probe を使い、今の main の木の写しで、行ごとに置き換えて build() を呼ぶ。
  ほかの実験のスクリプトと結果ファイルは走らせない・書き換えない。

手順:
  1. 写しを作り、法則を足す前に置き換えなしで検査する（base）。誤りがあれば止める。書いた行ごとに検査する（before）。
  2. 写しに法則を足し、置き換えなしで検査する（control）。書いた行ごとに検査する（after）。
  3. 単位: before の誤りのうち、法則を名指さず、「<N>.mod[<i>]: <Y> は <V> の <P>（<T>）に来られない」に合うもの。上位・相手で分けない。
     対応する法則は 2 つの候補: 上位の側なら mod_fits_<P>、相手の側なら mod_with_fits_<P の反対>。P が from・to でなければ候補はない。
     覆われる: after の同じ行の誤りに、候補のどちらかを名指し、かつ var1 が N、var3 が V のものがある（同じ定義の、同じ動詞の限定）。
     どちらの候補で覆われたか（上位・相手）は参考に数える。
  4. C = 覆われた単位 / 単位（before・after のどちらかで検査が落ちた行は外す）。

判定（事前登録）:
  前提（control）: control の誤りが 0、かつ before で受け入れた行が after で 1 つも退けられない。満たさなければ判定しない。
  単位が 10 未満なら判定しない。
  h_endpoint_law_names_same_mod: C ≥ 0.9 なら支持。C < 0.5 なら反証。その間は決まらない。
  参考（判定に使わない）: 覆われなかった単位の文、上位・相手の内訳、
    緩い読み（#907・#908 の決め方: 候補のどちらかが同じ行のどこかに出る）での C、足した法則の誤りのうち単位に対応しないものの数。

開示（結果を見る前に分かっていること）:
  - #907 と #908 の結果を見て、事後の数え直しをしてから、この手順を書いた。
    数え直しは片側ずつの法則の写しでのもので、両方を合わせた写しではまだ数えていない。
    片側ずつの事後の数（15/20 と 16/34）を足すと 31/54 = 0.57 で、決まらないの範囲に入る見込みがある。
    両方の法則を合わせると、片側で覆えなかった単位がもう片側の候補で覆われうるので、数は変わりうる。
  - 数える関数（units・cover）が動くかを、#908 の記録済みの結果（相手の側の法則だけの写し）に当てて確かめた。
    上位・相手を分けない単位で 54、厳しく覆われたのは 21（0.39）。これは上位の側の法則がない写しでの数で、
    この実験の写し（両方の法則）では上位の側の候補が足されるので上がりうる。この数を見たうえで、線は変えない。
  - var1 と var3 は、誤りの文の「var1=<名前>,」「var3=<名前>,」を読む。法則の変数の順は #907・#908 の書き方で決まっている。
  - 法則の書き方は変えないので、反証でも「規則で端の型を書けない」とまでは言えない。言えるのは、この書き方の法則がコードと同じ限定を名指さないこと。
  - 検査器のコードの端の検査は消さない。

出力: results/sys_endpoint_law_same_mod.json
使い方:
  python exp/experiments/sys_endpoint_law_same_mod.py
"""
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e38_error_kind_is_law as e38

ROOT = e38.ROOT
RES = ROOT / "exp/experiments/results"
OUT = RES / "sys_endpoint_law_same_mod.json"
SYN = "cscl/library/syntax/syntax.yaml"

NODES = """  r_overlap: {is: law_relation, display: 種類として重なる}
  overlap_down: {is: law_rule, display: 下なら重なる}
  overlap_up: {is: law_rule, display: 上なら重なる}
  below_by_is: {is: law_rule, display: 個体はその種類の下}
  mod_fits_from: {is: law_rule, display: 始点で限定したものの上位は、その動詞の始点の種類と重なる}
  mod_fits_to: {is: law_rule, display: 終点で限定したものの上位は、その動詞の終点の種類と重なる}
  mod_with_fits_from: {is: law_rule, display: 始点で限定する相手は、その動詞の終点の種類と重なる}
  mod_with_fits_to: {is: law_rule, display: 終点で限定する相手は、その動詞の始点の種類と重なる}
"""

FACTS = """  - {is: v_assume, from: overlap_down, to: {is: r_below, from: var1, to: var2}}
  - {is: v_derive, from: overlap_down, to: {is: r_overlap, from: var1, to: var2}}
  - {is: v_assume, from: overlap_up, to: {is: r_below, from: var2, to: var1}}
  - {is: v_derive, from: overlap_up, to: {is: r_overlap, from: var1, to: var2}}
  - {is: v_assume, from: below_by_is, to: {is: is, from: var1, to: var3}}
  - {is: v_assume, from: below_by_is, to: {is: r_below, from: var3, to: var2}}
  - {is: v_derive, from: below_by_is, to: {is: r_below, from: var1, to: var2}}
"""
for pos, end in (("from", "r_end_from"), ("to", "r_end_to")):
    FACTS += f"""  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: mod, from: var1, to: var2}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: of, from: var2, to: var3}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: position, from: var2, to: {pos}}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: extends, from: var1, to: var4}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: {end}, from: var3, to: var5}}}}
  - {{is: v_require, from: mod_fits_{pos}, to: {{is: r_overlap, from: var4, to: var5}}}}
"""
for pos, end in (("from", "r_end_to"), ("to", "r_end_from")):
    FACTS += f"""  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: mod, from: var1, to: var2}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: of, from: var2, to: var3}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: position, from: var2, to: {pos}}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: with, from: var2, to: var4}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: {end}, from: var3, to: var5}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: r_below, from: var5, to: ontology.kind, neg: true}}}}
  - {{is: v_require, from: mod_with_fits_{pos}, to: {{is: r_overlap, from: var4, to: var5}}}}
"""

ENDPOINT = re.compile(r"^(\S+)\.mod\[(\d+)\]: (\S+) は (\S+) の (\S+)（(.+)）に来られない$")
NEW_LAWS = {"mod_fits_from", "mod_fits_to", "mod_with_fits_from", "mod_with_fits_to"}
OTHER = {"from": "to", "to": "from"}


def patch(tree):
    f = tree / SYN
    s = f.read_text(encoding="utf-8")
    node_anchor = next(ln for ln in s.split("\n") if ln.startswith("  below_any:"))
    fact_anchor = next(ln for ln in s.split("\n") if "from: below_any, to: {is: r_below" in ln)
    assert s.count(node_anchor + "\n") == 1 and s.count(fact_anchor + "\n") == 1
    s = s.replace(node_anchor + "\n", node_anchor + "\n" + NODES)
    s = s.replace(fact_anchor + "\n", fact_anchor + "\n" + FACTS)
    f.write_text(s, encoding="utf-8")


def var(text, k):
    m = re.search(rf"{k}=([^,\s]+)", text)
    return m.group(1) if m else None


def units(errors):
    out = []
    for e in errors:
        if e["named"]:
            continue
        m = ENDPOINT.match(e["text"])
        if not m:
            continue
        pos = m.group(5)
        cands = {"parent": f"mod_fits_{pos}", "with": f"mod_with_fits_{OTHER[pos]}"} if pos in OTHER else {}
        out.append({"text": e["text"], "node": m.group(1), "verb": m.group(4), "pos": pos, "cands": cands})
    return out


def cover(u, after_errors):
    strict, loose = [], False
    for side, law in u["cands"].items():
        hits = [e for e in after_errors if e["named"] == law]
        loose = loose or bool(hits)
        if any(var(e["text"], "var1") == u["node"] and var(e["text"], "var3") == u["verb"] for e in hits):
            strict.append(side)
    return strict, loose


def main():
    e37 = json.loads((RES / "e37_writing_checker_version.json").read_text(encoding="utf-8"))
    cases = {}
    for c in e37["cases"]:
        if c["kind"] == "written":
            cases.setdefault((c["key"], c["line"]), c)
    keys = sorted(cases)
    with tempfile.TemporaryDirectory() as td:
        tree = Path(td)
        e38.copy_now(tree)
        base = e38.probe(tree)
        if base.get("crashed") or base["errors"]:
            OUT.write_text(json.dumps({"base": base}, ensure_ascii=False, indent=1), encoding="utf-8")
            sys.exit("base tree has errors")
        before = {}
        for k in keys:
            before[k] = e38.probe(tree, *k)
            print("before", k[0], flush=True)
        patch(tree)
        control = e38.probe(tree)
        after = {}
        for k in keys:
            after[k] = e38.probe(tree, *k)
            print("after", k[0], flush=True)

    def bad(r):
        return r.get("crashed") or r.get("missing")

    rows = []
    for k in keys:
        b, a = before[k], after[k]
        row = {"key": k[0], "line": k[1], "before": b, "after": a}
        if not bad(b) and not bad(a):
            us = units(b["errors"])
            for u in us:
                u["sides"], u["loose"] = cover(u, a["errors"])
                u["covered"] = bool(u["sides"])
            row["units"] = us
        rows.append(row)

    ctrl_errors = control.get("errors") if not control.get("crashed") else None
    newly_rejected = [r["key"] for r in rows if not bad(r["before"]) and not r["before"]["errors"]
                      and (bad(r["after"]) or r["after"]["errors"])]
    control_ok = ctrl_errors == [] and not newly_rejected
    us = [u for r in rows for u in r.get("units", [])]
    C = sum(u["covered"] for u in us) / len(us) if us else None
    extra = 0
    for r in rows:
        if "units" not in r:
            continue
        mine = {(u["node"], u["verb"]) for u in r["units"]}
        extra += sum(1 for e in r["after"]["errors"] if e["named"] in NEW_LAWS
                     and (var(e["text"], "var1"), var(e["text"], "var3")) not in mine)

    if not control_ok or C is None or len(us) < 10:
        verdict = "not_judged"
    else:
        verdict = "support" if C >= 0.9 else "refute" if C < 0.5 else "undecided"
    summary = {
        "n_cases": len(rows),
        "n_crashed_or_missing": sum(1 for r in rows if "units" not in r),
        "control_errors": len(ctrl_errors) if ctrl_errors is not None else None,
        "control_error_texts": [e["text"] for e in (ctrl_errors or [])][:20],
        "newly_rejected": newly_rejected,
        "control_ok": control_ok,
        "n_units": len(us),
        "n_covered": sum(u["covered"] for u in us),
        "C": C,
        "uncovered": [u["text"] for u in us if not u["covered"]],
        "n_covered_parent": sum("parent" in u["sides"] for u in us),
        "n_covered_with": sum("with" in u["sides"] for u in us),
        "n_covered_loose": sum(u["loose"] for u in us),
        "n_new_law_errors_beyond_units": extra,
    }
    out = {"summary": summary, "judgment": {"h_endpoint_law_names_same_mod": verdict}, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "control_error_texts"}, ensure_ascii=False))
    print(json.dumps(out["judgment"]))


if __name__ == "__main__":
    main()
