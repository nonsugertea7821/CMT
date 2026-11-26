"""端の法則を本物の体系に入れ、検査器のコードの端の検査を外しても、同じ行を受け入れ・退けるか（h_endpoint_law_replaces_code_check）。

系列:
  #911: コードの端の誤り 54 のうち 52 を、法則が同じ限定・同じ動詞で名指した（支持）。
  #914: 相手の名を r_below(相手, any) で求めた。軸を相手にした 2 を名指せず、決まらない。
  #917: 相手の名を「領域の事実を持つか any か」で求め、54 すべてを名指した（支持）。
  ただし #911〜#917 は、コードの検査を残したまま、法則も同じ誤りを出すかを見ただけ。
  仮説: h_endpoint_law_replaces_code_check: v_depend(type_check_result, syntax.law_rule)

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  before: 今の main の木そのまま（コードの端の検査あり、端の法則なし）。
  after: 写しの syntax.yaml に #917 の法則をそのまま足し（mod_fits_*・mod_with_fits_*・r_named・named_by_domain・named_any・mod_with_named ほか）、
    写しの type_checker.py で、端の誤りを出す 2 つの文（「<上位> は <動詞> の <位置>（…）に来られない」と
    「<相手> は <動詞> の <反対の位置>（…）に来られない」）の err(...) を pass に替える。
    「位置 new には with を付けられない」「種類でない」「動詞でない」の検査は残す（端の法則が扱う形でないため）。

材料（モデルは走らせない）:
  #911・#914・#917 と同じ: results/e37_writing_checker_version.json の cases のうち kind が written のもの（同じ (key, line) は 1 つ）。
  E38 の copy_now・probe を使い、木の写しで、行ごとに置き換えて build() を呼ぶ。

手順:
  1. before の木で base（置き換えなし）と、行ごとの before を取る。
  2. 写しを after に替え、control（置き換えなし）と、行ごとの after を取る。
  3. 行の判定: 誤りが 1 つでもあれば「退ける」、0 なら「受け入れる」。走らなかった（壊れた・行が見つからない）行は別に数える。
  4. 一致: before と after の両方が走った行のうち、受け入れ・退けが同じ行。
     不一致のうち、before で退け after で受け入れたもの（取りこぼし）と、before で受け入れ after で退けたもの（余分な退け）を分けて数える。
     before で走り after で壊れた行は、不一致（壊れ）として数える。
  5. 単位と厳しい覆いは #917 と同じ（before の端の誤りに対し、after の同じ行に、候補の法則を名指し var1 が N、var3 が V の誤りがある）。
     C = 覆われた単位 / 単位。

判定（事前登録）:
  前提: control の誤りが 0。満たさなければ判定しない。単位が 10 未満なら判定しない。
  h_endpoint_law_replaces_code_check:
    不一致が 0（取りこぼし 0、余分な退け 0、壊れ 0）かつ C = 1 なら支持。
    不一致が 1 以上なら反証。
    不一致が 0 で C < 1 なら決まらない（受け入れは一致するが、端の誤りを法則が名指していない行がある）。
  参考（判定に使わない）: 不一致の行の before・after の誤り、after にだけ出た誤りの文、
    端の誤りだけで退けられていた行の数（コードを外したとき、法則がなければ受け入れに変わる行）。

開示（結果を見る前に分かっていること）:
  - #917 の記録済みの結果を読んでいる。そこでは、単位に対応しない新しい法則の誤りが 3 あった。
    それが before で受け入れた行に出ていれば余分な退けになるが、#917 の newly_rejected は空だったので、
    3 はすでに退けられていた行に出た見込み。
  - コードの err を外すと、検査器の後の段が、前は出なかった誤りを出すことがありうる（誤りの数で段を止める作りかは読んでいない）。
  - 写しのコードの置き換えは、文字列で 2 つの err の行を探して替える。見つからなければ止める（その場合は判定しない）。
  - 支持でも、言えるのはこの 59 行の材料の上で受け入れと退けが一致したこと。体系全体での一致ではない。
  - 反証でも「規則で書けない」とまでは言えない。言えるのは、この書き方の法則が、この材料でコードと同じ線を引かないこと。

出力: results/sys_endpoint_law_replaces_code.json
使い方:
  python exp/experiments/sys_endpoint_law_replaces_code.py
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
OUT = RES / "sys_endpoint_law_replaces_code.json"
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
TC = "cscl/bootstrap/type_checker/type_checker.py"
CODE_ERRS = (
    """err(f"{where}: {n['extends']} は {verb} の {pos}（{self.spot_type(verb, pos)}）に来られない")""",
    """err(f"{where}: {m['with']} は {verb} の {other}（{self.end(verb, other)}）に来られない")""",
)


def patch(tree):
    f = tree / SYN
    s = f.read_text(encoding="utf-8")
    node_anchor = next(ln for ln in s.split("\n") if ln.startswith("  below_any:"))
    fact_anchor = next(ln for ln in s.split("\n") if "from: below_any, to: {is: r_below" in ln)
    assert s.count(node_anchor + "\n") == 1 and s.count(fact_anchor + "\n") == 1
    s = s.replace(node_anchor + "\n", node_anchor + "\n" + NODES)
    s = s.replace(fact_anchor + "\n", fact_anchor + "\n" + FACTS)
    f.write_text(s, encoding="utf-8")
    t = tree / TC
    c = t.read_text(encoding="utf-8")
    for e in CODE_ERRS:
        assert c.count(e) == 1, e
        c = c.replace(e, "pass")
    t.write_text(c, encoding="utf-8")


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
        out.append({"text": e["text"], "node": m.group(1), "partner": m.group(3), "verb": m.group(4), "pos": pos, "cands": cands})
    return out


def cover(u, after_errors):
    strict = []
    for side, law in u["cands"].items():
        hits = [e for e in after_errors if e["named"] == law]
        if any(var(e["text"], "var1") == u["node"] and var(e["text"], "var3") == u["verb"] for e in hits):
            strict.append(side)
    return strict


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
        return bool(r.get("crashed") or r.get("missing"))

    rows = []
    for k in keys:
        b, a = before[k], after[k]
        row = {"key": k[0], "line": k[1], "before": b, "after": a}
        if not bad(b):
            us = units(b["errors"])
            row["only_endpoint"] = bool(us) and len(us) == len(b["errors"])
            if bad(a):
                row["status"] = "broke"
            else:
                rb, ra = bool(b["errors"]), bool(a["errors"])
                row["status"] = "agree" if rb == ra else "missed" if rb else "over"
                for u in us:
                    u["sides"] = cover(u, a["errors"])
                    u["covered"] = bool(u["sides"])
                row["units"] = us
                bt = {e["text"] for e in b["errors"]}
                row["after_only"] = [e["text"] for e in a["errors"] if e["text"] not in bt]
        else:
            row["status"] = "not_run"
        rows.append(row)

    ctrl_errors = control.get("errors") if not control.get("crashed") else None
    control_ok = ctrl_errors == []
    st = Counter(r["status"] for r in rows)
    disagree = st["missed"] + st["over"] + st["broke"]
    us = [u for r in rows for u in r.get("units", [])]
    C = sum(u["covered"] for u in us) / len(us) if us else None
    if not control_ok or len(us) < 10:
        verdict = "not_judged"
    elif disagree:
        verdict = "refute"
    else:
        verdict = "support" if C == 1 else "undecided"
    summary = {
        "n_cases": len(rows),
        "n_not_run": st["not_run"],
        "n_agree": st["agree"],
        "n_missed": st["missed"],
        "n_over": st["over"],
        "n_broke": st["broke"],
        "n_disagree": disagree,
        "control_errors": len(ctrl_errors) if ctrl_errors is not None else None,
        "control_error_texts": [e["text"] for e in (ctrl_errors or [])][:20],
        "control_ok": control_ok,
        "n_units": len(us),
        "n_covered": sum(u["covered"] for u in us),
        "C": C,
        "uncovered": [u["text"] for u in us if not u["covered"]],
        "n_only_endpoint_rows": sum(1 for r in rows if r.get("only_endpoint")),
        "disagree_rows": [{"key": r["key"], "status": r["status"]} for r in rows if r["status"] in ("missed", "over", "broke")],
    }
    out = {"summary": summary, "judgment": {"h_endpoint_law_replaces_code_check": verdict}, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "control_error_texts"}, ensure_ascii=False))
    print(json.dumps(out["judgment"]))


if __name__ == "__main__":
    main()
