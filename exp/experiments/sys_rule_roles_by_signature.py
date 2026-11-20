"""h_rule_roles_by_signature を確かめる: 法則の役割（前提・導く文・求める文）を、役割の名詞の式（シグネチャ）で
書き分け、型検査が動詞の名前でなくその式から役割を読んでも、結果が変わらないか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.law_rule, signature_class])。
  登録（eb12e9f）の読み: 役割の名詞に式の差を足し、型検査はシグネチャから定まる分類で読む。
  対の解き方 h_rule_roles_by_frame（支持）は、役割を動詞の枠（pre・post・holds）で書き分けて読み返せた。
  しかし h_rule_verbs_unhardcode（反証、2b39186）で、枠を足すと導いた関係が 355 減った。
  足した枠そのものが評価に入るのが原因と見込んだ。この版は、評価に入らない名詞の定義に区別を置く。

現状（main）:
  premise  mod: {of: [v_assume, to],  with: law_rule}
  derived  mod: {of: [v_derive, to],  with: law_rule}
  required mod: {of: [v_require, to], with: law_rule}
  名詞の区別は動詞の名前にあり、動詞の区別は名詞の名前にある（互いに名前で指し合う）。
  型検査は RULE_VERBS（v_assume・v_derive・v_require）を名前で読む。

手順（体系のファイルは変えない。写しの上で変える）:
  cscl.yaml、cscl、exp/src を一時ディレクトリに写し、exp/experiments/results をそこへつなぐ。
  変種 L: 写しをそのまま。
  変種 S: 写しの syntax.yaml で、3 つの名詞の mod を文法の語（状態の指定）への式に置き換える:
      premise  mod: {of: [v_refer, from], with: pre}
      derived  mod: {of: [v_refer, from], with: post}
      required mod: {of: [v_refer, from], with: always}
    型検査の写しで、RULE_VERBS による読みを RULE_ROLE による読みに置き換える。
    RULE_ROLE は、syntax の動詞のうち from が law_rule のものについて、終点（to）の名詞の mod の with が
    pre → assume、post → derive、always → require として作る（動詞と名詞の名前は読まない）。
    置き換える箇所: q_fact の rule の判定、core_sections の key。
  変種 S0（対照）: 型検査の置き換えだけをし、名詞は変えない。読みが効いていれば L と違う結果になる。
  測るもの（各変種）:
    errors, ec_errors, laws_hash（型検査が集めた法則）, n_role（RULE_ROLE の数）
    関係: law_rules を評価した関係の行（pre・post を除く。h_rule_verbs_unhardcode と同じ）
  比べるもの（S と L）:
    n_only_L, n_only_S    片方にだけある関係の行の数
    n_diff_other          そのうち、行の中に premise・derived・required のどれも現れない行の数
  行（sys_rule_roles_by_signature.json）: "variant L/S/S0": {...}, "summary 要約": {...}

判定（事前に決める）:
  対照: S0 の errors・ec_errors・laws_hash のどれかが L と違う（違わなければ「外れ」とし、判定しない）。
  支持: S の errors = 0、ec_errors = 0、laws_hash が L と同じ、n_role = 3、n_diff_other = 0 のすべて。
  1 つでも外れれば反証。

開示（結果を見る前に分かっていること）:
  - 名詞の mod を変えるので、その名詞の定義から出る事実（mod、表示語の句など）は変わる見込みが高い。
    それは n_only_* に数え、判定は n_diff_other で行う。行に 3 つの名詞の語を含めば除くので、
    除き方は寛い側に寄る。除いた行の数は n_only_* と n_diff_other の差として報告する。
  - 必要条件を書き換えるので、名詞の表示語と式が食い違うことが、体系の法則で落ちる場合がある（errors に出る）。
  - pre・post・always は文法の語で、名前で読んでよい語である。v_refer も基礎の動詞の語である。
  - 型検査は 3 回走る。KEYWORDS（文法の節 rule_word との照合）は変えない。
使い方:
  python exp/experiments/sys_rule_roles_by_signature.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_roles_by_signature.json"

NOUN_EDITS = {
    "premise": ("{of: [v_assume, to], with: law_rule}", "{of: [v_refer, from], with: pre}"),
    "derived": ("{of: [v_derive, to], with: law_rule}", "{of: [v_refer, from], with: post}"),
    "required": ("{of: [v_require, to], with: law_rule}", "{of: [v_refer, from], with: always}"),
}
ROLE_WORDS = ("premise", "derived", "required")

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
                    _r = {"pre": "assume", "post": "derive", "always": "require"}.get(_m.get("with")) if isinstance(_m, dict) else None
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
keep = []
try:
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    for r, xs in sorted(F.by.items()):
        if r.split(".")[-1] in ("pre", "post"):
            continue
        keep += [f"{r}:{x}" for x in sorted(str(x) for x in xs)]
except Exception as e:
    keep = ["exc:" + repr(e)[:80]]
print(json.dumps({"errors": len(errs), "ec_errors": ec, "err_text": errs[:5],
                  "laws_hash": hashlib.sha256(laws.encode()).hexdigest()[:16],
                  "n_laws": len(O.get("laws") or {}), "n_rel": len(keep),
                  "n_role": len(getattr(tc, "RULE_ROLE", {}) or {}),
                  "role": getattr(tc, "RULE_ROLE", {}) or {}, "rel": keep}, ensure_ascii=False))
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
        for v, (a, b) in NOUN_EDITS.items():
            if l.startswith(f"  {v}: {{") and f"mod: {a}" in l:
                lines[i] = l.replace(f"mod: {a}", f"mod: {b}")
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
        return {"errors": -1, "ec_errors": -1, "stderr": r.stderr[-800:], "rel": []}
    return json.loads(out[-1])


def main():
    res, edits = {}, {}
    for k in ("L", "S", "S0"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            copy_tree(d)
            e = {}
            if k == "S":
                e["syntax"] = edit_syntax(d)
            if k in ("S", "S0"):
                e["checker"] = edit_checker(d)
            edits[k] = e
            res[k] = probe(d)
    L, S, S0 = res["L"], res["S"], res["S0"]
    rl, rs = set(L.get("rel") or []), set(S.get("rel") or [])
    only_l, only_s = sorted(rl - rs), sorted(rs - rl)
    other = [x for x in only_l + only_s if not any(w in x for w in ROLE_WORDS)]
    control_differs = int(any(S0.get(m) != L.get(m) for m in ("errors", "ec_errors", "laws_hash")))
    s = {"S_errors": S.get("errors"), "S_ec_errors": S.get("ec_errors"),
         "S_laws_same": int(S.get("laws_hash") == L.get("laws_hash")),
         "S_n_role": S.get("n_role"), "n_only_L": len(only_l), "n_only_S": len(only_s),
         "n_diff_other": len(other), "S0_errors": S0.get("errors"),
         "control_differs": control_differs, "L_errors": L.get("errors")}
    s["verdict_support"] = int(control_differs == 1 and s["S_errors"] == 0 and s["S_ec_errors"] == 0
                               and s["S_laws_same"] == 1 and s["S_n_role"] == 3 and s["n_diff_other"] == 0)
    rows = {}
    for k in res:
        r = {m: v for m, v in res[k].items() if m != "rel"}
        rows[f"variant {k}"] = {**r, "edits": edits[k]}
    rows["summary 要約"] = s
    rows["diff 差の行（先頭）"] = {"only_L": only_l[:20], "only_S": only_s[:20], "other": other[:20]}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:600])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "外れ（対照が効かない）" if not control_differs else ("支持" if s["verdict_support"] else "反証"))


if __name__ == "__main__":
    main()
