"""h_fact_id_by_content を確かめる: 事実の識別子を、置かれた文章（ファイルと位置）でなく中身から作ると、
検査の結果は変わらず、exp.yaml を部分のファイルに分けても法則を評価した関係が変わらないか。

仮説（claims.yaml）: v_refer(h, v_not_depend(syntax.identifier, syntax.passage))。登録 #497。
  出どころ #496（h_check_immune_parts、反証）: 族を部分のファイルに移すと rel_hash が変わった。
  型検査器は事実を f"ifact {name} {j}"（ファイルの名と、ファイルの中の位置）で名づける（syntax_facts）。

手順（体系のファイルも型検査器も変えない。写しの上で変える）:
  変種 L: main の写しをそのまま。
  変種 C: 型検査器の写しで、事実の名を f"ifact {v} {a} {b}"（解決した動詞・始点・終点）にする。
  変種 PC: #496 の変種 P（merge_parts を移し、exp.yaml の族を exp/src/families/<F>.yaml に移す。
    sys_check_immune_parts の edit_checker と split_exp）に、C の名づけを加える。
  測るもの（各変種）: errors、ec_errors、err_text、laws_hash、rel_hash、n_rel（#496 と同じ）。
    あわせて、事実の行のうち is・from・to が文字列のものの数と、(is, from, to) の異なりの数
    （名の重なりの目安。解決前の文字列で数える）。
  行（sys_fact_id_by_content.json）: "variant L/C/PC"、"summary 要約"。

判定（事前に決める）:
  支持: 次をすべて満たす。
    (1) C の errors = 0、ec_errors = 0、laws_hash が L と同じ。
    (2) PC の rel_hash と laws_hash が C と同じ。
    (3) PC の errors と ec_errors はどちらも 1 以下で、err_text は文法に parts がないこと
       （「語 parts が、grammar.domain に書かれていない」）だけ。これは対の h_grammar_names_parts の
       側の問題として、この判定では許す。
  1 つでも外れれば反証。L の errors が 0 でなければ外れ（判定しない）。

開示: #496 で L と P の値（rel_hash、n_rel、P の文法の誤り）を見ている。C と PC は実行していない。
使い方:
  python exp/experiments/sys_fact_id_by_content.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_fact_id_by_content.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV
import sys_check_immune_parts as CIP

NAME_OLD = '                    t = f"ifact {name} {j}"'
NAME_NEW = '                    t = f"ifact {v} {a} {b}"'
GRAMMAR_ERR = "語 parts が、grammar.domain に書かれていない"


def edit_name(d):
    p = d / CIP.CHECKER
    t = p.read_text(encoding="utf-8")
    n = t.count(NAME_OLD)
    p.write_text(t.replace(NAME_OLD, NAME_NEW), encoding="utf-8")
    return n


def count_facts(d):
    rows = []
    for p in sorted(d.glob("**/*.yaml")):
        if ".git" in p.parts:
            continue
        try:
            D = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for f in (D.get("facts") if isinstance(D, dict) else None) or []:
            if isinstance(f, dict) and all(isinstance(f.get(k), str) for k in ("is", "from", "to")):
                rows.append((f["is"], f["from"], f["to"]))
    return {"n_fact_rows": len(rows), "n_fact_distinct": len(set(rows))}


def main():
    res = {}
    for k in ("L", "C", "PC"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {}
            if k == "PC":
                e["checker"] = CIP.edit_checker(d)
            if k in ("C", "PC"):
                e["name"] = edit_name(d)
            if k == "PC":
                e.update(CIP.split_exp(d))
            e.update(count_facts(d))
            r = PREV.probe(d)
            r["rel_hash"] = hashlib.sha256("\n".join(r.get("rel") or []).encode()).hexdigest()[:16]
            r.pop("rel", None)
            res[k] = {**r, "edits": e}
    L, C, PC = res["L"], res["C"], res["PC"]
    pc_err = PC.get("err_text") or []
    s = {"L_errors": L.get("errors"), "C_errors": C.get("errors"), "C_ec_errors": C.get("ec_errors"),
         "C_laws_same": int(C.get("laws_hash") == L.get("laws_hash")),
         "C_rel_same_L": int(C.get("rel_hash") == L.get("rel_hash")),
         "L_n_rel": L.get("n_rel"), "C_n_rel": C.get("n_rel"), "PC_n_rel": PC.get("n_rel"),
         "PC_rel_same_C": int(PC.get("rel_hash") == C.get("rel_hash")),
         "PC_laws_same_C": int(PC.get("laws_hash") == C.get("laws_hash")),
         "PC_errors": PC.get("errors"), "PC_ec_errors": PC.get("ec_errors"),
         "PC_other_errors": sum(1 for x in pc_err if GRAMMAR_ERR not in x),
         "n_fact_rows": L["edits"]["n_fact_rows"], "n_fact_distinct": L["edits"]["n_fact_distinct"]}
    ok = (s["C_errors"] == 0 and s["C_ec_errors"] == 0 and s["C_laws_same"] == 1
          and s["PC_rel_same_C"] == 1 and s["PC_laws_same_C"] == 1
          and (s["PC_errors"] or 0) <= 1 and (s["PC_ec_errors"] or 0) <= 1 and s["PC_other_errors"] == 0)
    s["verdict"] = "外れ" if s["L_errors"] != 0 else "支持" if ok else "反証"
    rows = {f"variant {k}": v for k, v in res.items()}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False)[:700])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
