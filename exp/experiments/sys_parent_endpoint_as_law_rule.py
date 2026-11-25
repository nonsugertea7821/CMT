"""限定したものの上位の端の型は、規則の法則だけで名指せるか（h_parent_endpoint_as_law_rule）。

系列:
  E38（#710）: 退けた誤り 170 のうち、法則を名指さない 69。その 53 は限定の端の型の検査（コードの自由な文）。
  #903（h_unnamed_error_as_law_rule）: 端の型の法則 4 つ（上位の側 2・相手の側 2）を一時の写しに足した。
    相手の側の法則が正しい木で 25 の誤りを出し、判定しなかった。上位の側の法則は正しい木で 0、覆いは 20 のうち 18。
  そこで上位の側と相手の側を分けて登録した（#904）。ここでは上位の側だけを確かめる:
    h_parent_endpoint_as_law_rule: v_depend(type_check_result, [syntax.law_rule, syntax.extends])

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  写しの cscl/library/syntax/syntax.yaml に、関係 r_overlap と法則 4 つを足す（#903 の上位の側と同じ書き方）。
    overlap_down: r_below(a, b) なら r_overlap(a, b)。overlap_up: r_below(b, a) なら r_overlap(a, b)。
    mod_fits_from / mod_fits_to:
      mod(N, M)、of(M, V)、position(M, from|to)、extends(N, K)、r_end_from|r_end_to(V, T) なら r_overlap(K, T) を求める。
  相手の側の法則は足さない。

材料（モデルは走らせない）:
  E38・#903 と同じ: results/e37_writing_checker_version.json の cases のうち kind が written のもの（同じ (key, line) は 1 つ）。
  E38 の copy_now・probe・lines_of を使い、今の main の木の写しで、行ごとに置き換えて build() を呼ぶ。
  E37・E38 のスクリプトと結果ファイルは走らせない・書き換えない。#903 のスクリプトは main にないので、手をここに書き直した。

手順:
  1. 写しを作り、法則を足す前に置き換えなしで検査する（base）。誤りがあれば止める。書いた行ごとに検査する（before）。
  2. 写しに法則を足し、置き換えなしで検査する（control）。書いた行ごとに検査する（after）。
  3. 単位: before の誤りのうち、「<N>.mod[<i>]: <Y> は <V> の <P>（<T>）に来られない」に合い、
     Y の末尾の名前が、その書いた行（yaml で読む）の extends に入るもの（上位の側の端の誤り）。
     対応する法則は mod_fits_<P>。P が from・to でなければ、対応する法則はない（覆われないに数える）。
     覆われる: after の同じ行の誤りに、対応する法則を名指す誤りがある。
  4. C = 覆われた単位 / 単位（before・after のどちらかで検査が落ちた行は外す）。

判定（事前登録）:
  前提（control）: control の誤りが 0、かつ before で受け入れた行が after で 1 つも退けられない。
    満たさなければ判定しない。
  単位が 10 未満なら判定しない。
  h_parent_endpoint_as_law_rule: C ≥ 0.9 なら支持。C < 0.5 なら反証。その間は決まらない。
  参考（判定に使わない）: 覆われなかった単位の文。足した法則の誤りのうち、単位に対応しないものの数。

開示（結果を見る前に分かっていること）:
  - #903 の結果を見てから、この手順を書いた。#903 の木（そのときの main）では、上位の側は control 0、
    単位 20 のうち覆われたのは 18（0.9 ちょうど。覆われなかったのは organization と approved_inspection）。
    今の main は #903 の木から #904 の登録だけが進んだ木で、体系の型の部分は変わっていない見込みが高い。
    同じ数が出れば支持の線の上ちょうどになる。線は #903 の前に決めた値（0.9）のまま変えない。
  - 覆われなかった 2 つで、コードと規則のどちらの読みが違うかは、ここでも確かめない（参考に文を残すだけ）。
  - 検査器のコードの端の検査は消さない。支持は「規則で書けば名指せる」までで、コードの検査を消す採用は別の段。

出力: results/sys_parent_endpoint_as_law_rule.json
使い方:
  python exp/experiments/sys_parent_endpoint_as_law_rule.py
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
OUT = RES / "sys_parent_endpoint_as_law_rule.json"
SYN = "cscl/library/syntax/syntax.yaml"

NODES = """  r_overlap: {is: law_relation, display: 種類として重なる}
  overlap_down: {is: law_rule, display: 下なら重なる}
  overlap_up: {is: law_rule, display: 上なら重なる}
  mod_fits_from: {is: law_rule, display: 始点で限定したものの上位は、その動詞の始点の種類と重なる}
  mod_fits_to: {is: law_rule, display: 終点で限定したものの上位は、その動詞の終点の種類と重なる}
"""

FACTS = """  - {is: v_assume, from: overlap_down, to: {is: r_below, from: var1, to: var2}}
  - {is: v_derive, from: overlap_down, to: {is: r_overlap, from: var1, to: var2}}
  - {is: v_assume, from: overlap_up, to: {is: r_below, from: var2, to: var1}}
  - {is: v_derive, from: overlap_up, to: {is: r_overlap, from: var1, to: var2}}
"""
for pos, end in (("from", "r_end_from"), ("to", "r_end_to")):
    FACTS += f"""  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: mod, from: var1, to: var2}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: of, from: var2, to: var3}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: position, from: var2, to: {pos}}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: extends, from: var1, to: var4}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: {end}, from: var3, to: var5}}}}
  - {{is: v_require, from: mod_fits_{pos}, to: {{is: r_overlap, from: var4, to: var5}}}}
"""

ENDPOINT = re.compile(r"^(\S+)\.mod\[(\d+)\]: (\S+) は (\S+) の (\S+)（(.+)）に来られない$")
NEW_LAWS = {"mod_fits_from", "mod_fits_to"}


def patch(tree):
    f = tree / SYN
    s = f.read_text(encoding="utf-8")
    node_anchor = next(ln for ln in s.split("\n") if ln.startswith("  below_any:"))
    fact_anchor = next(ln for ln in s.split("\n") if "from: below_any, to: {is: r_below" in ln)
    assert s.count(node_anchor + "\n") == 1 and s.count(fact_anchor + "\n") == 1
    s = s.replace(node_anchor + "\n", node_anchor + "\n" + NODES)
    s = s.replace(fact_anchor + "\n", fact_anchor + "\n" + FACTS)
    f.write_text(s, encoding="utf-8")


def parents(line):
    node = next(iter((yaml.safe_load(line) or {}).values()), None) or {}
    ex = node.get("extends")
    return {str(x).split(".")[-1] for x in (ex if isinstance(ex, list) else [ex]) if x is not None}


def units(line, errors):
    out = []
    ps = parents(line)
    for e in errors:
        if e["named"]:
            continue
        m = ENDPOINT.match(e["text"])
        if not m or m.group(3).split(".")[-1] not in ps:
            continue
        pos = m.group(5)
        out.append({"text": e["text"], "pos": pos, "law": f"mod_fits_{pos}" if pos in ("from", "to") else None})
    return out


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
            us = units(k[1], b["errors"])
            named_after = {e["named"] for e in a["errors"] if e["named"]}
            for u in us:
                u["covered"] = u["law"] in named_after
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
        want = Counter(u["law"] for u in r["units"])
        got = Counter(e["named"] for e in r["after"]["errors"] if e["named"] in NEW_LAWS)
        extra += sum(max(0, got[l] - want[l]) for l in got)

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
        "n_new_law_errors_beyond_units": extra,
    }
    out = {"summary": summary, "judgment": {"h_parent_endpoint_as_law_rule": verdict}, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "control_error_texts"}, ensure_ascii=False))
    print(json.dumps(out["judgment"]))


if __name__ == "__main__":
    main()
