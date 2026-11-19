"""h_rule_verbs_unhardcode を確かめる: 型検査が法則の役割を名前（RULE_VERBS）でなく枠から読んでも、結果は変わらないか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.pre, syntax.post, syntax.holds])。
  登録（1003f36）の読み: h_rule_roles_by_frame（#335）で、役割は枠の位置で書き分けられ、読み返せると分かった。
  型検査の読み方を名前から枠へ置き換えても、検査と法則の評価は変わらない。

手順（体系のファイルは変えない。写しの上で変える）:
  cscl.yaml、cscl、exp/src を一時ディレクトリに写し、exp/experiments/results をそこへつなぐ。
  変種:
    L   そのまま。
    U   (1) 写しの syntax.yaml で、#335 と同じく v_assume に pre、v_derive に post、v_require に holds を足す
            （中身は 3 つとも {is: v_refer, from: from, to: to}）。
        (2) 写しの type_checker.py で、名前の並び RULE_VERBS を読む 2 か所を、枠から求めた対応 RULE_ROLE に置き換える:
            - q_fact の「規則の文か」の判定: short(f["is"]) in RULE_VERBS → in RULE_ROLE
            - core_sections の役割の対応 key: v_assume/v_derive/v_require の名前の表 → RULE_ROLE（と v_govern）
            RULE_ROLE は、読み込んだ層のファイルの syntax のノードのうち、from が law_rule の語で、
            枠の鍵が pre だけ → assume、post だけ → derive、holds だけ → require とする。
            文法の語の照合（KEYWORDS）は変えない。
    U0  (2) だけ（枠を足さない）。置き換えが効いていることの対照: 役割が読めず、結果が L と違うはず。
  測るもの（各変種）:
    errors, ec_errors     誤りの数
    laws_hash             O["laws"] の正規の形のハッシュ
    rel_hash              法則の評価（tc.evaluate(law_rules, syntax_facts)）で導いた関係（pre・post を除く）のハッシュ
    n_role                RULE_ROLE の数（L は 0）
  行（sys_rule_verbs_unhardcode.json）: "variant L/U/U0": {...}, "summary 要約": {...}
判定（事前に決める）:
  まず対照: U0 が L と同じ（errors・laws_hash・rel_hash がすべて同じ）なら、置き換えが効いていないので外れ（状態は変えない）。
  対照が L と違うとき: U の errors・ec_errors・laws_hash・rel_hash がすべて L と同じなら支持。どれかが違えば反証。

開示（結果を見る前に分かっていること）:
  - #335 で、(1) だけでは errors 0、ec_errors 0、法則の集まりは同じだった。
  - RULE_ROLE の判定に、law_rule と pre・post・holds の語を名前で使う。どれも文法の語（grammar の laws と、枠の鍵）。
  - 型検査は 3 回走る。
使い方:
  python exp/experiments/sys_rule_verbs_unhardcode.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_verbs_unhardcode.json"
X = "{is: v_refer, from: from, to: to}"
EDITS = {"v_assume": "pre", "v_derive": "post", "v_require": "holds"}

ROLE_BLOCK = '''    global RULE_ROLE
    RULE_ROLE = {}
    for _f, _D in [(name, A)] + libs:
        if _D.get("domain") != "syntax":
            continue
        for _nid, _n in (_D.get("nodes") or {}).items():
            if isinstance(_n, dict) and _n.get("from") == "law_rule":
                _has = frozenset(k for k in ("pre", "post", "holds") if _n.get(k))
                _r = {frozenset({"pre"}): "assume", frozenset({"post"}): "derive", frozenset({"holds"}): "require"}.get(_has)
                if _r:
                    RULE_ROLE[_nid] = _r
'''

PROBE = r'''
import contextlib, hashlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker", "exp/src"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T, O, _ = tc.build()
        ok = True
    except Exception as e:
        ok = False
        exc = repr(e)[:300]
if not ok:
    print(json.dumps({"errors": -1, "ec_errors": -1, "exc": exc}))
    sys.exit(0)
errs = [str(e) for e in tc.errors]
with contextlib.redirect_stdout(io.StringIO()):
    import exp_check
    del tc.errors[:]
    try:
        exp_check.build()
    except SystemExit:
        pass
    except Exception:
        tc.errors.append("exception")
ec = len(tc.errors)
laws = json.dumps(O.get("laws"), sort_keys=True, ensure_ascii=False, default=str)
try:
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    keep = []
    for r, xs in sorted(F.by.items()):
        if r.split(".")[-1] in ("pre", "post"):
            continue
        keep += [f"{r}:{x}" for x in sorted(str(x) for x in xs)]
    rel = hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]
    n_rel = len(keep)
except Exception as e:
    rel, n_rel = "exc:" + repr(e)[:80], -1
print(json.dumps({"errors": len(errs), "ec_errors": ec, "err_text": errs[:5],
                  "laws_hash": hashlib.sha256(laws.encode()).hexdigest()[:16],
                  "n_laws": len(O.get("laws") or {}), "rel_hash": rel, "n_rel": n_rel,
                  "n_role": len(getattr(tc, "RULE_ROLE", {}) or {})}, ensure_ascii=False))
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


def edit_checker(dst):
    p = dst / "cscl/bootstrap/type_checker/type_checker.py"
    t = p.read_text(encoding="utf-8")
    n = 0
    a = '    rule = short(f["is"]) in RULE_VERBS\n'
    if a in t:
        t, n = t.replace(a, '    rule = short(f["is"]) in RULE_ROLE\n'), n + 1
    b = '    key = {"v_assume": "assume", "v_derive": "derive", "v_require": "require", "v_govern": "govern"}\n'
    if b in t:
        t, n = t.replace(b, '    key = {**RULE_ROLE, "v_govern": "govern"}\n'), n + 1
    c = '    _SCOPES.clear()\n'
    if c in t:
        t, n = t.replace(c, c + ROLE_BLOCK, 1), n + 1
    t = t.replace('RULE_VERBS = ("v_assume", "v_derive", "v_require")\n',
                  'RULE_VERBS = ("v_assume", "v_derive", "v_require")\nRULE_ROLE = {}\n')
    p.write_text(t, encoding="utf-8")
    return n


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "ec_errors": -1, "stderr": r.stderr[-800:]}
    return json.loads(out[-1])


def main():
    res, edits = {}, {}
    for k in ("L", "U", "U0"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            copy_tree(d)
            e = {}
            if k == "U":
                e["syntax"] = edit_syntax(d)
            if k in ("U", "U0"):
                e["checker"] = edit_checker(d)
            edits[k] = e
            res[k] = probe(d)
    L, U, U0 = res["L"], res["U"], res["U0"]
    same = lambda a, b: all(a.get(m) == b.get(m) for m in ("errors", "ec_errors", "laws_hash", "rel_hash"))
    control_differs = int(not same(U0, L))
    s = {"U_errors": U.get("errors"), "U_ec_errors": U.get("ec_errors"),
         "U_laws_same": int(U.get("laws_hash") == L.get("laws_hash")),
         "U_rel_same": int(U.get("rel_hash") == L.get("rel_hash")),
         "U_n_role": U.get("n_role"), "U0_errors": U0.get("errors"),
         "control_differs": control_differs, "L_errors": L.get("errors")}
    s["verdict_support"] = int(control_differs == 1 and same(U, L))
    rows = {f"variant {k}": {**res[k], "edits": edits[k]} for k in res}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:600])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "外れ（対照が効かない）" if not control_differs else ("支持" if s["verdict_support"] else "反証"))


if __name__ == "__main__":
    main()
