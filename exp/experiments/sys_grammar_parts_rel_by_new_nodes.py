"""h_grammar_parts_rel_by_new_nodes を確かめる: 法則で導いた関係は、文章（ファイルの分け方）に依らないか。
#497 の反証（PCG の関係が C と違った）が、文法に足したノード parts・compose_from_domain に触れる項だけで説明できるか。

仮説（claims.yaml）: v_refer(h, v_not_depend(syntax.law_relation, syntax.passage))。登録 2676811（#876）。
系列:
  #502（h_fact_id_by_content、支持）: 事実の名を中身から作れば、exp.yaml を分けても関係は同じ（PC の rel = C）。
  h_grammar_names_parts（反証、2676811）: PCG（PC に文法の parts を足す）は errors 0、ec_errors 0、laws は C と同じ。
    関係は C と違った（n_rel 423271 → 424464、1193 増）。判定は「関係が C と同じ」で書いていて、
    ノードを足せば関係が増えることを見込んでいなかった。

手順（体系のファイルも型検査器も変えない。写しの上で変える。作りは sys_grammar_names_parts と同じ関数を使う）:
  C    型検査器の写しで、事実の名を中身から作る（FID.edit_name）。
  CG   C に、文法の変更だけを加える（edit_grammar。exp.yaml は分けない）。
  PCG  C に、部分を読む仕組みと exp.yaml の分割と文法の変更を加える（#497 の PCG と同じ）。
  各変種の関係の集まり（枠の鍵 pre・post を除く。PREV.probe の rel）を取り、差を数える。
  「新しいノードに触れる」= 関係の行の項に 'syntax.parts' か 'syntax.compose_from_domain' が引用符つきで出る。
  測るもの: errors、ec_errors、laws_hash、n_rel、
    n_C_minus_PCG・n_PCG_minus_C（差の数）、n_diff_untouched（差のうち新しいノードに触れない数）、
    PCG_same_CG（PCG と CG の関係が同じか）、n_CG_PCG_diff、差の関係の名ごとの数（記述）。
  行（sys_grammar_parts_rel_by_new_nodes.json）: "variant C/CG/PCG"、"summary 要約"。

判定（事前に決める）:
  外れ: C の errors が 0 でない、または PCG の errors・ec_errors が 0 でない。
  支持: n_diff_untouched = 0（C と PCG の差がすべて新しいノードに触れる）かつ PCG_same_CG = 1（分けても関係は同じ）。
  反証: それ以外。
  CG の errors は記述（exp.yaml を分けずに文法だけ変えたときに誤りが出るかは、ここでは問わない）。

開示:
  - 2676811 で、C と PCG の n_rel（423271、424464）を見ている。差の中身は見ていない。
  - いまの main は 2676811 から動いているので、数は変わりうる。
  - 新しいノードに触れるかは、項の字面（引用符つきの名前）で数える。関係の行は str(tuple) なので、項は引用符で囲まれる。
使い方:
  python exp/experiments/sys_grammar_parts_rel_by_new_nodes.py
"""
import collections
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_grammar_parts_rel_by_new_nodes.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV
import sys_check_immune_parts as CIP
import sys_fact_id_by_content as FID
import sys_grammar_names_parts as GNP

NEW = re.compile(r"'syntax\.(parts|compose_from_domain)'")


def build(k):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        PREV.copy_tree(d)
        e = {}
        if k == "PCG":
            e["checker"] = CIP.edit_checker(d)
        e["name"] = FID.edit_name(d)
        if k == "PCG":
            e.update(CIP.split_exp(d))
        if k in ("CG", "PCG"):
            e["grammar"] = GNP.edit_grammar(d)
        r = PREV.probe(d)
    rel = set(r.pop("rel", None) or [])
    r.pop("role", None)
    r["rel_hash"] = hashlib.sha256("\n".join(sorted(rel)).encode()).hexdigest()[:16]
    return {**r, "edits": e}, rel


def kinds(xs):
    return dict(collections.Counter(x.split(":")[0] for x in xs).most_common())


def main():
    res, rel = {}, {}
    for k in ("C", "CG", "PCG"):
        res[k], rel[k] = build(k)
    cm, pm = rel["C"] - rel["PCG"], rel["PCG"] - rel["C"]
    untouched = sorted(x for x in cm | pm if not NEW.search(x))
    gp = rel["CG"] ^ rel["PCG"]
    C, CG, PCG = res["C"], res["CG"], res["PCG"]
    s = {"C_errors": C.get("errors"), "C_ec_errors": C.get("ec_errors"),
         "CG_errors": CG.get("errors"), "CG_ec_errors": CG.get("ec_errors"),
         "PCG_errors": PCG.get("errors"), "PCG_ec_errors": PCG.get("ec_errors"),
         "PCG_laws_same_C": int(PCG.get("laws_hash") == C.get("laws_hash")),
         "C_n_rel": C.get("n_rel"), "CG_n_rel": CG.get("n_rel"), "PCG_n_rel": PCG.get("n_rel"),
         "n_C_minus_PCG": len(cm), "n_PCG_minus_C": len(pm), "n_diff_untouched": len(untouched),
         "PCG_same_CG": int(not gp), "n_CG_PCG_diff": len(gp)}
    bad = s["C_errors"] != 0 or s["PCG_errors"] != 0 or s["PCG_ec_errors"] != 0
    ok = s["n_diff_untouched"] == 0 and s["PCG_same_CG"] == 1
    s["verdict"] = "外れ" if bad else "支持" if ok else "反証"
    rows = {f"variant {k}": v for k, v in res.items()}
    rows["summary 要約"] = s
    rows["diff 差の内訳"] = {"C_minus_PCG_kinds": kinds(cm), "PCG_minus_C_kinds": kinds(pm),
                           "untouched_kinds": kinds(untouched), "untouched_head": untouched[:30],
                           "CG_PCG_kinds": kinds(gp), "CG_PCG_head": sorted(gp)[:30]}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False)[:600])
    print(json.dumps(rows["diff 差の内訳"], ensure_ascii=False)[:1500])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
