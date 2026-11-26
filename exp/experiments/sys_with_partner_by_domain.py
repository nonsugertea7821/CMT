"""限定の相手を domain の事実で読めば、軸を相手にした誤りも法則で名指せるか（h_with_partner_named_by_domain）。

系列:
  #911: コードの端の誤り 54 のうち 52 を、法則が同じ限定・同じ動詞で名指した（支持）。
  #914: 相手の名を r_below(相手, any) で求める法則 mod_with_named を足した。定義のない相手の単位 D は 7、
    そのうち 5 を名指した（C_D = 0.714、決まらない）。名指せなかった 2 は、相手が軸だった:
      subj.deficit.mod[0]: amount は syntax.v_measure の to（any）に来られない
      subj.shared_address.mod[0]: people は syntax.v_refer の to（any）に来られない
    軸は exists の事実を持つので、below_any で any の下に入り、r_below(相手, any) が立ってしまう。
  仮説: h_with_partner_named_by_domain: v_depend(type_check_result, [syntax.law_rule, syntax.with])

見立て（事前に、コードと記録を読んで立てたもの。走らせて確かめてはいない）:
  - 検査器の事実の生成（syntax_facts）では、domain の事実は定義（N）と個体（I）にだけ出る。軸には出ない。
  - コードの端の検査は、相手が定義か個体か any であることを求める。
  - したがって「相手が domain の事実を持つか、any である」を求める法則は、コードの検査と同じ線を引く見込み。

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  写しの cscl/library/syntax/syntax.yaml に、#911 の法則をそのまま足し、さらに次を足す:
    r_named: 名のある（law_relation）
    named_by_domain: domain(var1, var2) なら r_named(var1, var1) を導く。
    named_any: with(var1, any) なら r_named(any, any) を導く（any は domain を持たないため）。
    mod_with_named: 限定 var2 が定義 var1 にあり、動詞 var3 の限定で、相手が var4 なら、r_named(var4, var4) を求める。
  #914 の mod_with_named（r_below(var4, any) を求める）は足さない。名は同じにして、読み手が #914 と並べられるようにする。

材料（モデルは走らせない）:
  #911・#914 と同じ: results/e37_writing_checker_version.json の cases のうち kind が written のもの（同じ (key, line) は 1 つ）。
  E38 の copy_now・probe を使い、今の main の木の写しで、行ごとに置き換えて build() を呼ぶ。

手順:
  1. #914 と同じ。base・before・（法則を足して）control・after。
  2. 単位・候補・厳しい覆い（var1 が N、var3 が V）は #914 と同じ。
  3. D: 相手 Y に「.」がない単位（#914 と同じ読み）。
  4. A: D のうち、相手が軸（amount・people）である単位。軸かどうかは、写しの木の軸の表（type_checker の AX）で引く。
  5. C = 覆われた単位 / 単位。C_D = mod_with_named で覆われた D の単位 / D の単位。
     C_A = mod_with_named で覆われた A の単位 / A の単位。

判定（事前登録）:
  前提（control）: control の誤りが 0、かつ before で受け入れた行が after で 1 つも退けられない。満たさなければ判定しない。
  A の単位が 0、または全体の単位が 10 未満なら判定しない。
  h_with_partner_named_by_domain:
    C_A = 1 かつ C_D = 1 かつ C ≥ 0.9 なら支持。
    C_A = 0 なら反証。
    その間は決まらない。
  参考（判定に使わない）: 覆われなかった単位の文、候補ごとの内訳、
    mod_with_named の誤りのうち単位に対応しないものの数。

開示（結果を見る前に分かっていること）:
  - #914 の記録済みの結果（rows）を読み、D の 7 と、名指せなかった 2 の相手が軸であることを見てから、この手順を書いた。
    A に入るのはこの 2 の見込み。数が少ないので、この実験は数の確かさより、仕組みが働くかを見る。
  - 写しに法則を足しての試し走りはしていない。法則の機械が、assume にだけ現れる var2（named_by_domain）や、
    定数 any を端に置いた derive（named_any）を受け付けるかは、確かめていない。受け付けなければ、壊れるか control が落ちる。それは結果として記録する。
  - with の事実で相手がどの綴り（解決した名か、書いたままか）で出るかは、確かめていない。
    綴りが domain の事実と違えば、定義のある相手も名指され、control が落ちる見込み。
  - 個体の domain の事実は、検査器の生成で出ることを、コードで読んだ。
  - 反証でも「規則で書けない」とまでは言えない。言えるのは、この書き方の法則が、この形を名指さないこと。
  - 検査器のコードの端の検査は消さない。

出力: results/sys_with_partner_by_domain.json
使い方:
  python exp/experiments/sys_with_partner_by_domain.py
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
OUT = RES / "sys_with_partner_by_domain.json"
SYN = "cscl/library/syntax/syntax.yaml"

NODES = """  r_overlap: {is: law_relation, display: 種類として重なる}
  overlap_down: {is: law_rule, display: 下なら重なる}
  overlap_up: {is: law_rule, display: 上なら重なる}
  below_by_is: {is: law_rule, display: 個体はその種類の下}
  mod_fits_from: {is: law_rule, display: 始点で限定したものの上位は、その動詞の始点の種類と重なる}
  mod_fits_to: {is: law_rule, display: 終点で限定したものの上位は、その動詞の終点の種類と重なる}
  mod_with_fits_from: {is: law_rule, display: 始点で限定する相手は、その動詞の終点の種類と重なる}
  mod_with_fits_to: {is: law_rule, display: 終点で限定する相手は、その動詞の始点の種類と重なる}
  r_named: {is: law_relation, display: 名のある}
  named_by_domain: {is: law_rule, display: 領域を持つものは名のあるもの}
  named_any: {is: law_rule, display: any は名のあるもの}
  mod_with_named: {is: law_rule, display: 限定する相手は、名のあるもの}
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
FACTS += """  - {is: v_assume, from: mod_with_named, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: mod_with_named, to: {is: of, from: var2, to: var3}}
  - {is: v_assume, from: mod_with_named, to: {is: with, from: var2, to: var4}}
  - {is: v_require, from: mod_with_named, to: {is: r_named, from: var4, to: var4}}
  - {is: v_assume, from: named_by_domain, to: {is: domain, from: var1, to: var2}}
  - {is: v_derive, from: named_by_domain, to: {is: r_named, from: var1, to: var1}}
  - {is: v_assume, from: named_any, to: {is: with, from: var1, to: any}}
  - {is: v_derive, from: named_any, to: {is: r_named, from: any, to: any}}
"""

ENDPOINT = re.compile(r"^(\S+)\.mod\[(\d+)\]: (\S+) は (\S+) の (\S+)（(.+)）に来られない$")
NEW_LAWS = {"mod_fits_from", "mod_fits_to", "mod_with_fits_from", "mod_with_fits_to", "mod_with_named"}
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


def axis_names(tree):
    names = set()
    for p in tree.rglob("*.yaml"):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and isinstance(d.get("axes"), dict):
            names |= {str(k) for k in d["axes"]}
    return names


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
        cands["named"] = "mod_with_named"
        out.append({"text": e["text"], "node": m.group(1), "partner": m.group(3), "verb": m.group(4), "pos": pos,
                    "undefined": "." not in m.group(3), "cands": cands})
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
        axes = axis_names(tree)
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

    D = [u for u in us if u["undefined"]]
    C_D = sum("named" in u["sides"] for u in D) / len(D) if D else None
    A = [u for u in D if u["partner"] in axes]
    C_A = sum("named" in u["sides"] for u in A) / len(A) if A else None
    if not control_ok or C is None or len(us) < 10 or not A:
        verdict = "not_judged"
    else:
        verdict = "support" if C_A == 1 and C_D == 1 and C >= 0.9 else "refute" if C_A == 0 else "undecided"
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
        "n_covered_named": sum("named" in u["sides"] for u in us),
        "n_undefined_units": len(D),
        "n_undefined_covered_named": sum("named" in u["sides"] for u in D),
        "C_D": C_D,
        "undefined_units": [u["text"] for u in D],
        "n_axis_units": len(A),
        "n_axis_covered_named": sum("named" in u["sides"] for u in A),
        "C_A": C_A,
        "axis_units": [u["text"] for u in A],
        "n_new_law_errors_beyond_units": extra,
    }
    out = {"summary": summary, "judgment": {"h_with_partner_named_by_domain": verdict}, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "control_error_texts"}, ensure_ascii=False))
    print(json.dumps(out["judgment"]))


if __name__ == "__main__":
    main()
