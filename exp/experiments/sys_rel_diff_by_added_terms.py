"""h_rel_diff_by_added_terms を確かめる: 文法にノードを足したときの関係の差は、足したノードと、その中身（mod の項）で説明できるか。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.law_relation, [syntax.nodes, syntax.mod]))。登録 #884。
系列:
  h_grammar_parts_rel_by_new_nodes（#884、反証）: C（事実の名を中身から作る）に文法の parts・compose_from_domain を足すと（CG）、
    関係が 1193 増え、そのうち 208 は名前 'syntax.parts'・'syntax.compose_from_domain' を含まなかった。
    手元の確かめ（記録していない scratch）で、その 208 は無名の中身の項
    （of: [ontology.v_compose, from]、with: syntax.domain を yaml にした文字列）を含んでいた。
    exp.yaml を分けても分けなくても関係は同じだった（PCG = CG）。
  事前登録の「触れる」の定めが名前だけで、中身の項を数えていなかった。ここでは中身の項も「足した項」に数える。

手順（体系のファイルも型検査器も変えない。#884 の build をそのまま使う）:
  C   = sys_grammar_parts_rel_by_new_nodes.build("C")
  CG  = sys_grammar_parts_rel_by_new_nodes.build("CG")（C に文法の変更だけを足す）
  関係の行は "<関係の名>:<項の組の str>"。最初の ':' で切り、残りを ast.literal_eval で組に戻す。
  項の集まり T(X) = X のすべての行の項（文字列にしたもの）。
  新しい項 = T(CG) − T(C)、消えた項 = T(C) − T(CG)。
  行が「足した項に触れる」= その行の項のどれかが、新しい項か消えた項に入る。
  新しい項の出どころ（足したもので説明できるか）:
    足した名前: 'syntax.parts'・'syntax.compose_from_domain'。
    足した中身: 項を yaml.safe_load で読み、辞書で、鍵が of・with（と quant）だけ、
      値の名前の修飾（最後の '.' より前）を外したものが、足したノードの of・with（compose_from_domain の
      of: [v_compose, from]、with: domain）と同じ。
    それ以外を「よそから来た新しい項」と数える。
  測るもの: errors・ec_errors（C・CG）、n_rel、n_CG_minus_C・n_C_minus_CG、n_unparsed（組に戻せない行）、
    n_new_terms・n_gone_terms、n_new_foreign（よそから来た新しい項）、n_diff_old_only（差の行のうち足した項に触れない数）、
    新しい項の一覧、差の行の関係の名ごとの数、触れない行の先頭 30（記述）。
  行（sys_rel_diff_by_added_terms.json）: "variant C/CG"、"summary 要約"、"diff 差の内訳"。

判定（事前に決める）:
  外れ: C か CG の errors が 0 でない、または n_unparsed > 0（行を組に戻せず、測れない）。
  支持: n_diff_old_only = 0 かつ n_new_foreign = 0 かつ n_gone_terms = 0。
  反証: それ以外。

開示:
  - #884 の結果（1193、208、PCG = CG）と、208 が無名の中身の項を含むこと（scratch の確かめ）を見てから書いた。
    つまり、名前か無名の中身のどちらかを含むことは、ほぼ分かっている。新しく問うのは、
    (1) 古い項だけからなる行が差に出ないか（足したノードが、古い項どうしの関係を変えないか）、
    (2) 新しい項が足したものだけから来るか、(3) 項が消えないか。
  - 同じ中身 {of: [v_compose, from], with: domain} を、C のどこかがすでに無名で持っていれば、その項は新しくならない。
    そのとき、その項を含む差の行は「触れない」に数えられ、反証になりうる。それは「中身の項が足したものでない」ことで、
    仮説の読み（関係は節と mod に依る）とは別の問いになる。そうなったら、その行を記述する。
使い方:
  python exp/experiments/sys_rel_diff_by_added_terms.py
"""
import ast
import collections
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rel_diff_by_added_terms.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_grammar_parts_rel_by_new_nodes as GPRN

ADDED_NAMES = {"syntax.parts", "syntax.compose_from_domain"}
ADDED_CONTENT = [{"of": ["v_compose", "from"], "with": "domain"}]


def terms(rel):
    by, bad = {}, 0
    for x in rel:
        r, _, rest = x.partition(":")
        try:
            v = ast.literal_eval(rest)
        except Exception:
            bad += 1
            continue
        by[x] = {str(e) for e in (v if isinstance(v, tuple) else (v,))}
    return by, bad


def bare(v):
    if isinstance(v, str):
        return v.rsplit(".", 1)[-1]
    if isinstance(v, list):
        return [bare(e) for e in v]
    return v


def from_added(t):
    if t in ADDED_NAMES:
        return True
    try:
        v = yaml.safe_load(t)
    except Exception:
        return False
    if not isinstance(v, dict) or not set(v) <= {"of", "with", "quant"}:
        return False
    w = {k: bare(v[k]) for k in ("of", "with") if k in v}
    return w in ADDED_CONTENT


def kinds(xs):
    return dict(collections.Counter(x.split(":")[0] for x in xs).most_common())


def main():
    res, rel = {}, {}
    for k in ("C", "CG"):
        res[k], rel[k] = GPRN.build(k)
    tc, bc = terms(rel["C"])
    tg, bg = terms(rel["CG"])
    TC = set().union(*tc.values()) if tc else set()
    TG = set().union(*tg.values()) if tg else set()
    new, gone = TG - TC, TC - TG
    pm, cm = rel["CG"] - rel["C"], rel["C"] - rel["CG"]
    touch = new | gone
    old_only = sorted(x for x in pm if not (tg.get(x, set()) & touch)) + sorted(x for x in cm if not (tc.get(x, set()) & touch))
    foreign = sorted(t for t in new if not from_added(t))
    C, CG = res["C"], res["CG"]
    s = {"C_errors": C.get("errors"), "C_ec_errors": C.get("ec_errors"),
         "CG_errors": CG.get("errors"), "CG_ec_errors": CG.get("ec_errors"),
         "C_n_rel": C.get("n_rel"), "CG_n_rel": CG.get("n_rel"),
         "n_CG_minus_C": len(pm), "n_C_minus_CG": len(cm), "n_unparsed": bc + bg,
         "n_new_terms": len(new), "n_gone_terms": len(gone), "n_new_foreign": len(foreign),
         "n_diff_old_only": len(old_only)}
    bad = s["C_errors"] != 0 or s["CG_errors"] != 0 or s["n_unparsed"] > 0
    ok = s["n_diff_old_only"] == 0 and s["n_new_foreign"] == 0 and s["n_gone_terms"] == 0
    s["verdict"] = "外れ" if bad else "支持" if ok else "反証"
    rows = {f"variant {k}": v for k, v in res.items()}
    rows["summary 要約"] = s
    rows["diff 差の内訳"] = {"new_terms": sorted(new), "gone_terms": sorted(gone)[:30], "foreign": foreign[:30],
                           "CG_minus_C_kinds": kinds(pm), "C_minus_CG_kinds": kinds(cm),
                           "old_only_kinds": kinds(old_only), "old_only_head": old_only[:30]}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["diff 差の内訳"], ensure_ascii=False)[:2000])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
