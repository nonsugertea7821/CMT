"""h_rule_roles_by_named_mod を確かめる: 法則の役割の名詞を名前のある中身で書けば、型検査は名詞の mod から
役割を読み、errors 0 で、関係の差は変えた定義とその参照の行だけに収まるか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.law_rule, syntax.mod])。
  登録（a627c49、#479）。前の版 h_rule_roles_by_signature（#478、反証）は、名詞の mod を名前のない中身
  {v_refer from, with: pre/post/always} で書き、役割は 3 つとも読めたが、法則 named_mod_use と named_mod_share で
  3 件落ちた。また、関係の差の振り分けを名詞の名前で行ったため、名前のない中身の行が漏れた（事後に数えると、
  残りは定義の参照の行 9 だけだった）。

手順（体系のファイルは変えない。写しの上で変える）:
  cscl.yaml、cscl、exp/src を一時ディレクトリに写し、exp/experiments/results をそこへつなぐ。
  変種 L: 写しをそのまま。
  変種 N: 写しで次を変える。
    syntax.yaml に、名前のある中身を 2 つ足す（refer_from_post と同じ形）:
      refer_from_pre:    {display: 前の状態の指定へ述べる（始点）, extends: quality, of: [v_refer, from], with: pre}
      refer_from_always: {display: どのステップでも成り立つ状態の指定へ述べる（始点）, extends: quality, of: [v_refer, from], with: always}
    syntax.yaml の 3 つの名詞の mod を置き換える:
      premise  mod: refer_from_pre
      derived  mod: refer_from_post
      required mod: refer_from_always
    runtime.yaml の pre_rule の mod {of: [v_refer, from], with: pre} を refer_from_pre に置き換える
      （同じ中身を二つのノードが足すので、名前で書く。named_mod_use が求める）。
    型検査の写しで、RULE_VERBS による読みを RULE_ROLE による読みに置き換える。
    RULE_ROLE は、syntax の動詞のうち from が law_rule のものについて、終点（to）の名詞の mod をたどり
    （名前なら syntax のノードを引く）、その with が pre → assume、post → derive、always → require として作る。
    置き換える箇所: q_fact の rule の判定、core_sections の key（#478 と同じ）。
  変種 N0（対照）: 型検査の置き換えだけをし、体系は変えない。
  測るもの（各変種）: errors, ec_errors, laws_hash, n_role、law_rules を評価した関係の行（pre・post を除く）。
  比べるもの（N と L の、片方にだけある行）:
    帰属する行: 次のどれかを含む行。
      変えたノードの語: premise, derived, required, pre_rule, refer_from_pre, refer_from_post, refer_from_always
      名前のない中身の項（"of:\\n" を含む行。#478 の穴を事前に塞ぐ）
    n_diff_def     帰属しない行のうち、関係が定義の参照（r_def_back, r_defined, r_written）の行の数
    n_diff_eval    帰属せず、定義の参照でもない行の数
  行（sys_rule_roles_by_named_mod.json）: "variant L/N/N0": {...}, "summary 要約": {...}

判定（事前に決める）:
  対照: N0 の errors・ec_errors・laws_hash のどれかが L と違う（違わなければ「外れ」とし、判定しない）。
  支持: N の errors = 0、ec_errors = 0、laws_hash が L と同じ、n_role = 3、n_diff_eval = 0 のすべて。
  1 つでも外れれば反証。n_diff_def は報告するが判定に使わない（仮説は定義の参照の行の差を許す）。

開示（結果を見る前に分かっていること）:
  - #478 で、名前のない中身による errors 3 件の文面と、事後の探索で残った 9 行（r_def_back 6、r_defined 2、
    r_written 1）を見ている。今回の判定の閾値（n_diff_eval = 0 で、定義の参照を除く）は、その事後の読みを
    仮説として事前に置いたもので、#478 の結果を見て選んだ。
  - 足す名前の表示語は refer_from_post の形にならった。表示語の重なりで落ちれば errors に出る。
  - pre・post・always は文法の語で、名前で読んでよい語である。
使い方:
  python exp/experiments/sys_rule_roles_by_named_mod.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_roles_by_named_mod.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV

NEW_NODES = [
    "  refer_from_pre: {display: 前の状態の指定へ述べる（始点）, extends: quality, of: [v_refer, from], with: pre}",
    "  refer_from_always: {display: どのステップでも成り立つ状態の指定へ述べる（始点）, extends: quality, of: [v_refer, from], with: always}",
]
NOUN_EDITS = {
    "premise": ("{of: [v_assume, to], with: law_rule}", "refer_from_pre"),
    "derived": ("{of: [v_derive, to], with: law_rule}", "refer_from_post"),
    "required": ("{of: [v_require, to], with: law_rule}", "refer_from_always"),
}
RUNTIME_EDIT = ("  pre_rule: {display: 前の状態の確かめ方, extends: strategy, mod: {of: [v_refer, from], with: pre}}",
                "  pre_rule: {display: 前の状態の確かめ方, extends: strategy, mod: refer_from_pre}")
ATTR = ("premise", "derived", "required", "pre_rule", "refer_from_pre", "refer_from_post", "refer_from_always", "of:\\n")
DEF_RELS = ("r_def_back", "r_defined", "r_written")

ROLE_BLOCK = '''    global RULE_ROLE
    RULE_ROLE = {}
    for _f, _D in [(name, A)] + libs:
        if _D.get("domain") != "syntax":
            continue
        _N = _D.get("nodes") or {}
        for _nid, _n in _N.items():
            if isinstance(_n, dict) and _n.get("from") == "law_rule" and isinstance(_N.get(_n.get("to")), dict):
                _ms = _N[_n["to"]].get("mod")
                _ms = _ms if isinstance(_ms, list) else [_ms]
                for _m in _ms:
                    if isinstance(_m, str) and isinstance(_N.get(_m), dict):
                        _m = _N[_m]
                    _r = {"pre": "assume", "post": "derive", "always": "require"}.get(_m.get("with")) if isinstance(_m, dict) else None
                    if _r:
                        RULE_ROLE[_nid] = _r
'''


def edit_system(dst):
    p = dst / "cscl/library/syntax/syntax.yaml"
    lines = p.read_text(encoding="utf-8").split("\n")
    done = 0
    for i, l in enumerate(lines):
        for v, (a, b) in NOUN_EDITS.items():
            if l.startswith(f"  {v}: {{") and f"mod: {a}" in l:
                lines[i] = l.replace(f"mod: {a}", f"mod: {b}")
                done += 1
    j = next(i for i, l in enumerate(lines) if l.startswith("  refer_from_post: {"))
    lines[j + 1:j + 1] = NEW_NODES
    done += len(NEW_NODES)
    p.write_text("\n".join(lines), encoding="utf-8")
    r = dst / "cscl/library/runtime/runtime.yaml"
    t = r.read_text(encoding="utf-8")
    if RUNTIME_EDIT[0] in t:
        t, done = t.replace(RUNTIME_EDIT[0], RUNTIME_EDIT[1]), done + 1
    r.write_text(t, encoding="utf-8")
    return done


def edit_checker(dst):
    keep = PREV.ROLE_BLOCK
    PREV.ROLE_BLOCK = ROLE_BLOCK
    try:
        return PREV.edit_checker(dst)
    finally:
        PREV.ROLE_BLOCK = keep


def main():
    res, edits = {}, {}
    for k in ("L", "N", "N0"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {}
            if k == "N":
                e["system"] = edit_system(d)
            if k in ("N", "N0"):
                e["checker"] = edit_checker(d)
            edits[k] = e
            res[k] = PREV.probe(d)
    L, N, N0 = res["L"], res["N"], res["N0"]
    rl, rn = set(L.get("rel") or []), set(N.get("rel") or [])
    only_l, only_n = sorted(rl - rn), sorted(rn - rl)
    rest = [x for x in only_l + only_n if not any(w in x for w in ATTR)]
    dfn = [x for x in rest if x.split(":", 1)[0] in DEF_RELS]
    ev = [x for x in rest if x.split(":", 1)[0] not in DEF_RELS]
    control_differs = int(any(N0.get(m) != L.get(m) for m in ("errors", "ec_errors", "laws_hash")))
    s = {"N_errors": N.get("errors"), "N_ec_errors": N.get("ec_errors"),
         "N_laws_same": int(N.get("laws_hash") == L.get("laws_hash")),
         "N_n_role": N.get("n_role"), "n_only_L": len(only_l), "n_only_N": len(only_n),
         "n_diff_def": len(dfn), "n_diff_eval": len(ev), "N0_errors": N0.get("errors"),
         "control_differs": control_differs, "L_errors": L.get("errors")}
    s["verdict_support"] = int(control_differs == 1 and s["N_errors"] == 0 and s["N_ec_errors"] == 0
                               and s["N_laws_same"] == 1 and s["N_n_role"] == 3 and s["n_diff_eval"] == 0)
    rows = {}
    for k in res:
        r = {m: v for m, v in res[k].items() if m != "rel"}
        rows[f"variant {k}"] = {**r, "edits": edits[k]}
    rows["summary 要約"] = s
    rows["diff 差の行"] = {"def": dfn[:40], "eval": ev[:40], "only_L_head": only_l[:10], "only_N_head": only_n[:10]}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:600])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "外れ（対照が効かない）" if not control_differs else ("支持" if s["verdict_support"] else "反証"))


if __name__ == "__main__":
    main()
