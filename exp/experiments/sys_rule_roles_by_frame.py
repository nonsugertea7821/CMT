"""h_rule_roles_by_frame を確かめる: 法則の役割（前提・導く文・求める文）を、前後の状態の指定の位置で書き分け、そこから読めるか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.law_rule, syntax.pre, syntax.post])。
  登録（eb12e9f）の読み: 前提は pre、導く文は post、求める文は両側で成り立つ（holds）。
  背景: h_identifier_by_bisimulation（#331）で、v_assume・v_derive・v_require とその目的語は
  式の上で区別がなく（双模倣で同じ類）、型検査は RULE_VERBS で名前で読んでいると分かった。

手順（体系のファイルは変えない。写しの上で変える）:
  cscl.yaml、cscl、exp/src を一時ディレクトリに写し、exp/experiments/results をそこへつなぐ。
  変種 V: 写しの syntax.yaml で、3 つの動詞に同じ中身の文 X = {is: v_refer, from: from, to: to} を、
    違う位置に足す:
      v_assume  に pre:   [X]
      v_derive  に post:  [X]
      v_require に holds: [X]
    ほかは変えない（型検査の RULE_VERBS も変えない）。
  測るもの:
    errors        変種で tc.build() の errors の数
    ec_errors     変種で exp_check の errors の数
    role_match    枠から読んだ役割（pre だけ → assume、post だけ → derive、holds → require）が、
                  名前の対応（v_assume→assume、v_derive→derive、v_require→require）と一致する動詞の数（0〜3）
    bisim_split   双模倣（sys_identifier_bisimulation と同じ分割の細分）で、
                  {v_assume, v_derive, v_require} と {premise, derived, required} が
                  それぞれ別々の類に分かれていれば 1
    laws_same     変種の O["laws"]（型検査が名前で集めた法則の前提・導く文・求める文）が、
                  元の体系と同じなら 1
  行（sys_rule_roles_by_frame.json）: "variant V": {...}, "summary 要約": {...}
判定（事前に決める）: errors = 0、ec_errors = 0、role_match = 3、bisim_split = 1、laws_same = 1 のすべてで支持。
  1 つでも外れれば反証。

開示（結果を見る前に分かっていること）:
  - この版は、型検査の読み方を名前から枠へ置き換えていない。枠で書き分けられ、そこから役割が
    読み返せることまでを確かめる。置き換えて結果が変わらないかは、別に確かめる。
  - pre・post・holds は文法の語で、名前で読んでよい語である。
  - X の中身は 3 つで同じにした。違いは位置だけにするため。中身が法則の意味として正しいかは問わない。
  - 型検査は元と変種で 2 回走る。
使い方:
  python exp/experiments/sys_rule_roles_by_frame.py
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_roles_by_frame.json"
DROP = ("display", "gloss")
X = "{is: v_refer, from: from, to: to}"
EDITS = {"v_assume": "pre", "v_derive": "post", "v_require": "holds"}
NAME_ROLE = {"v_assume": "assume", "v_derive": "derive", "v_require": "require"}

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker", "exp/src"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
errs = [str(e) for e in tc.errors]
errors = len(errs)
with contextlib.redirect_stdout(io.StringIO()):
    import exp_check
    del tc.errors[:]
    try:
        exp_check.build()
    except SystemExit:
        pass
ec_errors = len(tc.errors)
N = T.N
names = sorted(N)
cls = {q: 0 for q in names}
def canon(x):
    if isinstance(x, str):
        return f"<{cls[x]}>" if x in N else json.dumps(x, ensure_ascii=False)
    if isinstance(x, dict):
        return "{" + ",".join(f"{json.dumps(k)}:{canon(v)}" for k, v in sorted(x.items())) + "}"
    if isinstance(x, list):
        return "[" + ",".join(sorted(canon(v) for v in x)) + "]"
    return json.dumps(x)
n = 1
while True:
    keys = {q: (cls[q], canon({k: v for k, v in N[q].items() if k not in ("display", "gloss")})) for q in names}
    ids = {k: i for i, k in enumerate(sorted(set(keys.values())))}
    cls = {q: ids[keys[q]] for q in names}
    if len(ids) == n:
        break
    n = len(ids)
def role(v):
    d = N.get("syntax." + v, {})
    has = {k for k in ("pre", "post", "holds") if d.get(k)}
    return {frozenset({"pre"}): "assume", frozenset({"post"}): "derive", frozenset({"holds"}): "require"}.get(frozenset(has))
print(json.dumps({
    "errors": errors, "ec_errors": ec_errors, "err_text": [e[:200] for e in errs[:5]],
    "roles": {v: role(v) for v in ("v_assume", "v_derive", "v_require")},
    "verb_cls": [cls["syntax." + v] for v in ("v_assume", "v_derive", "v_require")],
    "noun_cls": [cls["syntax." + v] for v in ("premise", "derived", "required")],
    "laws": json.dumps(O.get("laws"), sort_keys=True, ensure_ascii=False, default=str),
}, ensure_ascii=False))
'''


def copy_tree(dst):
    for p in ("cscl.yaml", "cscl", "exp/src"):
        s, d = ROOT / p, dst / p
        d.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if s.is_dir() else shutil.copy2)(s, d)
    (dst / "exp/experiments").mkdir(parents=True, exist_ok=True)
    os.symlink(ROOT / "exp/experiments/results", dst / "exp/experiments/results")


def edit_syntax(dst):
    p = dst / "cscl/library/syntax/syntax.yaml"
    lines = p.read_text(encoding="utf-8").split("\n")
    done = 0
    for i, l in enumerate(lines):
        for v, k in EDITS.items():
            if l.startswith(f"  {v}: {{") and l.endswith("}"):
                lines[i] = l[:-1] + f", {k}: [{X}]}}"
                done += 1
    p.write_text("\n".join(lines), encoding="utf-8")
    return done


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "ec_errors": -1, "stderr": r.stderr[-800:]}
    return json.loads(out[-1])


def main():
    with tempfile.TemporaryDirectory() as t0, tempfile.TemporaryDirectory() as t1:
        L, V = Path(t0), Path(t1)
        copy_tree(L)
        copy_tree(V)
        edited = edit_syntax(V)
        base, var = probe(L), probe(V)
    roles = var.get("roles", {})
    role_match = sum(1 for v, r in NAME_ROLE.items() if roles.get(v) == r)
    vc, nc = var.get("verb_cls", [0, 0, 0]), var.get("noun_cls", [0, 0, 0])
    bisim_split = int(len(set(vc)) == 3 and len(set(nc)) == 3)
    laws_same = int(var.get("laws") is not None and var.get("laws") == base.get("laws"))
    rowV = {"edited": edited, "errors": var.get("errors"), "ec_errors": var.get("ec_errors"),
            "err_text": var.get("err_text", var.get("stderr")), "roles": roles,
            "verb_cls_distinct": len(set(vc)), "noun_cls_distinct": len(set(nc))}
    rowL = {"errors": base.get("errors"), "ec_errors": base.get("ec_errors"),
            "verb_cls_distinct": len(set(base.get("verb_cls", []))), "noun_cls_distinct": len(set(base.get("noun_cls", [])))}
    s = {"errors": var.get("errors"), "ec_errors": var.get("ec_errors"), "role_match": role_match,
         "bisim_split": bisim_split, "laws_same": laws_same, "base_errors": base.get("errors")}
    s["verdict_support"] = int(s["errors"] == 0 and s["ec_errors"] == 0 and role_match == 3 and bisim_split == 1 and laws_same == 1)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": {"variant L": rowL, "variant V": rowV, "summary 要約": s}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rowL, ensure_ascii=False))
    print(json.dumps(rowV, ensure_ascii=False))
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "支持" if s["verdict_support"] else "反証")


if __name__ == "__main__":
    main()
