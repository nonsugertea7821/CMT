"""端の型の誤りを規則で書いた法則にすれば、検査はその法則を名指して退けるか（h_unnamed_error_as_law_rule）。

系列:
  E37（反証）: モデルが書いた行のうち退けられた行は、どの版の検査器でも退けられた。
  E38（#710）: 退けた誤り 170 のうち、法則を名指すのは 101（A = 0.594、h_error_kind_is_law は決まらない）。
    名指さない 69 のうち 53 が「Y は 動詞 V の 位置 P（T）に来られない」（限定の端の型の検査）で、
    検査器のコードが自由な文で積んでいる。law_given に帰せるものは 0（h_unnamed_error_is_law_given は反証）。
  反証からの片方の解き方として h_unnamed_error_as_law_rule を登録した:
    v_depend(type_check_result, syntax.law_rule)。端の型の検査を文法の事実の上の規則（law_rule）で書けば、
    検査はその法則を名指して退ける。

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  写しの cscl/library/syntax/syntax.yaml に、次の関係 1 つと法則 6 つを足す（検査器のコードは替えない）。
    r_overlap（種類として重なる）: overlap_down（r_below a b なら r_overlap a b）、overlap_up（r_below b a なら r_overlap a b）。
      検査器の overlaps(x, y) = x が any か、x が y の下か、y が x の下、を規則に写したもの（any は below_any で下に入る）。
    mod_fits_from / mod_fits_to:
      mod(N, M)、of(M, V)、position(M, from|to)、extends(N, K)、r_end_from|r_end_to(V, T) なら r_overlap(K, T)。
      （コードの 1277 行目の検査: 限定したものの上位 K と、限定の位置の端の種類 T が重なる）
    mod_with_fits_from / mod_with_fits_to:
      mod(N, M)、of(M, V)、position(M, from|to)、with(M, W)、反対の端 r_end_to|r_end_from(V, T) なら r_overlap(W, T)。
      （コードの 1289 行目の一般の場合。「属する」の終点と、動詞を受け取る端の例外は規則に書かない）
  位置 new の端の型の法則は書かない（その誤りがあれば、覆われないものに数える）。

材料（モデルは走らせない）:
  E38 と同じ: results/e37_writing_checker_version.json の cases のうち kind が written のもの（同じ (key, line) は 1 つ）。
  E38 の copy_now・probe・lines_of をそのまま使い、今の木の写しで、行ごとに置き換えて build() を呼ぶ。
  E37・E38 のスクリプトと結果ファイルは走らせない・書き換えない。

手順:
  1. 写しを 1 つ作る。法則を足す前に、置き換えなしで検査する（base）。誤りがあれば止める。
     書いた行ごとに検査する（before）。
  2. 写しの syntax.yaml に上の法則を足す。置き換えなしで検査する（control）。
     書いた行ごとに検査する（after）。
  3. 端の誤り（単位）: before の誤りのうち、
       「<N>.mod[<i>]: <Y> は <V> の <P>（<T>）に来られない」に合うもの（法則を名指さないもの）。
     種類: その行（書いた行を yaml で読む）の extends に Y の末尾の名前が入れば「上位」、そうでなければ「相手」。
     対応する法則: 上位なら mod_fits_<P>。相手なら、限定の位置は P の反対なので mod_with_fits_<P の反対>。
       P が from・to でなければ、対応する法則はない。
     覆われる: after の同じ行の誤りに、対応する法則を名指す誤りがある。
  4. C = 覆われた端の誤り / 端の誤り（検査器が落ちた行は、before・after のどちらかで落ちれば外す）。

判定（事前登録）:
  前提（control）: control の誤りが 0、かつ before で受け入れた行が after で 1 つも退けられない。
    満たさなければ判定しない（足した法則が正しい行を退ける。書き方の誤りとして開示する）。
  h_unnamed_error_as_law_rule: C ≥ 0.9 なら支持。C < 0.5 なら反証。その間は決まらない。
  端の誤りが 10 未満なら判定しない。
  参考（判定に使わない）: after での A（法則を名指す誤り / 誤り。E38 の A に当たるもの）、種類ごとの C、
    after で増えた法則の誤りのうち、before の端の誤りに対応しないもの（同じ行の別の限定を名指すもの）の数。

開示（結果を見る前に分かっていること）:
  - E38 の結果ファイル（summary と、先頭の行の誤り）を見てから、この手順を書いた。
    端の形の誤りが 53 あり、上位と相手の両方の種類があることを知っている。
  - 検査器のコードの端の検査は消さない。after でも自由な文の誤りは残る。支持は「規則で書けば名指せる」までで、
    コードの検査を法則に置き換えて消すこと（採用）は別の段。
  - 「属する」の終点と、動詞を受け取る端の例外を規則に書かないので、体系の正しい行でそれに当たる限定があれば、
    control が誤りを出して判定しない。
  - of・with・extends の事実が、検査器の中で名前を解いた形で積まれているかは、読んだだけで確かめていない。
    解いていなければ規則が当たらず、C が下がる（反証側に寄る）。

出力: results/sys_endpoint_error_as_law_rule.json
使い方:
  python exp/experiments/sys_endpoint_error_as_law_rule.py
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
OUT = RES / "sys_endpoint_error_as_law_rule.json"
SYN = "cscl/library/syntax/syntax.yaml"

NODES = """  r_overlap: {is: law_relation, display: 種類として重なる}
  overlap_down: {is: law_rule, display: 下なら重なる}
  overlap_up: {is: law_rule, display: 上なら重なる}
  mod_fits_from: {is: law_rule, display: 始点で限定したものの上位は、その動詞の始点の種類と重なる}
  mod_fits_to: {is: law_rule, display: 終点で限定したものの上位は、その動詞の終点の種類と重なる}
  mod_with_fits_from: {is: law_rule, display: 始点で限定する相手は、その動詞の終点の種類と重なる}
  mod_with_fits_to: {is: law_rule, display: 終点で限定する相手は、その動詞の始点の種類と重なる}
"""

FACTS = """  - {is: v_assume, from: overlap_down, to: {is: r_below, from: var1, to: var2}}
  - {is: v_derive, from: overlap_down, to: {is: r_overlap, from: var1, to: var2}}
  - {is: v_assume, from: overlap_up, to: {is: r_below, from: var2, to: var1}}
  - {is: v_derive, from: overlap_up, to: {is: r_overlap, from: var1, to: var2}}
"""
for pos, end, other_end in (("from", "r_end_from", "r_end_to"), ("to", "r_end_to", "r_end_from")):
    FACTS += f"""  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: mod, from: var1, to: var2}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: of, from: var2, to: var3}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: position, from: var2, to: {pos}}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: extends, from: var1, to: var4}}}}
  - {{is: v_assume, from: mod_fits_{pos}, to: {{is: {end}, from: var3, to: var5}}}}
  - {{is: v_require, from: mod_fits_{pos}, to: {{is: r_overlap, from: var4, to: var5}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: mod, from: var1, to: var2}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: of, from: var2, to: var3}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: position, from: var2, to: {pos}}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: with, from: var2, to: var4}}}}
  - {{is: v_assume, from: mod_with_fits_{pos}, to: {{is: {other_end}, from: var3, to: var5}}}}
  - {{is: v_require, from: mod_with_fits_{pos}, to: {{is: r_overlap, from: var4, to: var5}}}}
"""

ENDPOINT = re.compile(r"^(\S+)\.mod\[(\d+)\]: (\S+) は (\S+) の (\S+)（(.+)）に来られない$")
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
        if not m:
            continue
        y, pos = m.group(3), m.group(5)
        kind = "parent" if y.split(".")[-1] in ps else "with"
        if pos not in OTHER:
            law = None
        elif kind == "parent":
            law = f"mod_fits_{pos}"
        else:
            law = f"mod_with_fits_{OTHER[pos]}"
        out.append({"text": e["text"], "kind": kind, "pos": pos, "law": law})
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
    errs_after = [e for r in rows if "units" in r and r["after"]["errors"] for e in r["after"]["errors"]]
    A_after = sum(1 for e in errs_after if e["named"]) / len(errs_after) if errs_after else None
    new_laws = {"mod_fits_from", "mod_fits_to", "mod_with_fits_from", "mod_with_fits_to"}
    extra = 0
    for r in rows:
        if "units" not in r:
            continue
        want = Counter(u["law"] for u in r["units"])
        got = Counter(e["named"] for e in r["after"]["errors"] if e["named"] in new_laws)
        extra += sum(max(0, got[l] - want[l]) for l in got)

    def by(kind):
        x = [u for u in us if u["kind"] == kind]
        return {"n": len(x), "covered": sum(u["covered"] for u in x)}

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
        "by_kind": {"parent": by("parent"), "with": by("with")},
        "n_no_law_pos": sum(1 for u in us if u["law"] is None),
        "A_after": A_after,
        "n_new_law_errors_beyond_units": extra,
    }
    out = {"summary": summary, "judgment": {"h_unnamed_error_as_law_rule": verdict}, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "control_error_texts"}, ensure_ascii=False))
    print(json.dumps(out["judgment"]))


if __name__ == "__main__":
    main()
