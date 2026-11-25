"""h_grammar_names_parts を確かめる: 文法が、領域を分けた文章（部分のファイル）を語として持てば、
exp.yaml を部分のファイルに分けても、検査の誤りが消え、法則を評価した関係が変わらないか。

仮説（claims.yaml）: v_refer(h, v_refer(syntax.grammar, syntax.passage))。登録 #497（わき道）。
系列:
  #496（h_check_immune_parts、反証）: exp.yaml を部分に分けると errors 1、関係の名がずれた。
  #502（h_fact_id_by_content、支持）: 事実の名を中身から作れば、分けても関係は同じ（PC の rel_hash = C）。
    残った誤りは「語 parts が、grammar.domain に書かれていない」の 1 件（errors 1、ec_errors 1）。
  利用者が決めた識別子化への順の二つ目（法則の役割を枠で書く → 文法に parts → 事実の名を中身から → 類と種差）。

手順（体系のファイルも型検査器も変えない。写しの上で変える）:
  変種 C:   型検査器の写しで、事実の名を中身から作る（sys_fact_id_by_content の edit_name）。
  変種 PC:  C に、部分のファイルを読む仕組みと exp.yaml の分割を加える（sys_check_immune_parts の edit_checker と split_exp）。
            #502 の PC と同じ作り。いまの main で作り直す。
  変種 PCG: PC に、文法の変更を加える（写しの syntax.yaml）:
    (1) grammar.domain に parts を足す: [domain, axes, nodes, individuals, facts, parts]
    (2) ノード parts を足す（文法の語はノードに当たる必要がある）:
        parts: {display: 部分の文章, extends: passage, mod: compose_from_domain}
        compose_from_domain: {display: 領域へ部分になる（始点）, extends: quality, of: [v_compose, from], with: domain}
        （名前のある中身にする。compose_from_system と同じ書き方）
  測るもの（各変種）: errors、ec_errors、err_text、laws_hash、rel_hash、n_rel（#502 と同じ probe）。

判定（事前に決める）:
  支持: PCG の errors = 0、ec_errors = 0、rel_hash と laws_hash が C と同じ。
  反証: それ以外。
  C の errors が 0 でなければ外れ（判定しない）。PC は対照（#502 の再現。記述）。

開示:
  - #502 で、PC の誤りが grammar.domain の 1 件だけだったことを見ている。
  - ノード parts の式（passage を広げ、領域の部分になる）は、ここで決めた。文法の語にはノードが要るため。
  - 部分を読む仕組み（merge_parts）は、型検査器の写しにだけ入れる。本体への採用は、支持されたら別に行う。
  - PC の ec_errors 1 の中身は #502 で記録していない。PCG で ec_errors が 0 にならなければ、その文を記録する。
使い方:
  python exp/experiments/sys_grammar_names_parts.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_grammar_names_parts.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV
import sys_check_immune_parts as CIP
import sys_fact_id_by_content as FID

SYN = "cscl/library/syntax/syntax.yaml"
G_OLD = "  domain: [domain, axes, nodes, individuals, facts]\n"
G_NEW = "  domain: [domain, axes, nodes, individuals, facts, parts]\n"
N_AT = "  compose_from_system: {display: 体系へ部分になる（始点）, extends: quality, of: [v_compose, from], with: system}\n"
N_ADD = ("  compose_from_domain: {display: 領域へ部分になる（始点）, extends: quality, of: [v_compose, from], with: domain}\n"
         "  parts: {display: 部分の文章, extends: passage, mod: compose_from_domain}\n")


def edit_grammar(d):
    p = d / SYN
    t = p.read_text(encoding="utf-8")
    assert t.count(G_OLD) == 1 and t.count(N_AT) == 1
    p.write_text(t.replace(G_OLD, G_NEW).replace(N_AT, N_AT + N_ADD), encoding="utf-8")
    return 2


def main():
    res = {}
    for k in ("C", "PC", "PCG"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {}
            if k in ("PC", "PCG"):
                e["checker"] = CIP.edit_checker(d)
            e["name"] = FID.edit_name(d)
            if k in ("PC", "PCG"):
                e.update(CIP.split_exp(d))
            if k == "PCG":
                e["grammar"] = edit_grammar(d)
            r = PREV.probe(d)
            r["rel_hash"] = hashlib.sha256("\n".join(r.get("rel") or []).encode()).hexdigest()[:16]
            r.pop("rel", None)
            res[k] = {**r, "edits": e}
    C, PC, PCG = res["C"], res["PC"], res["PCG"]
    s = {"C_errors": C.get("errors"), "C_ec_errors": C.get("ec_errors"),
         "PC_errors": PC.get("errors"), "PC_ec_errors": PC.get("ec_errors"),
         "PC_rel_same_C": int(PC.get("rel_hash") == C.get("rel_hash")),
         "PCG_errors": PCG.get("errors"), "PCG_ec_errors": PCG.get("ec_errors"),
         "PCG_rel_same_C": int(PCG.get("rel_hash") == C.get("rel_hash")),
         "PCG_laws_same_C": int(PCG.get("laws_hash") == C.get("laws_hash")),
         "C_n_rel": C.get("n_rel"), "PC_n_rel": PC.get("n_rel"), "PCG_n_rel": PCG.get("n_rel")}
    ok = (s["PCG_errors"] == 0 and s["PCG_ec_errors"] == 0 and s["PCG_rel_same_C"] == 1 and s["PCG_laws_same_C"] == 1)
    s["verdict"] = "外れ" if s["C_errors"] != 0 else "支持" if ok else "反証"
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
