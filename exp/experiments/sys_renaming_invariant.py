"""h_renaming_invariant を確かめる（絞った版）: 型検査器は、名前で読むと分かっている語のほかの識別子の選びに依存しないか。

仮説（claims.yaml）: v_not_depend(type_checker, name_choice)。
  登録（702414b）: シグネチャと文法の外の識別子を一対一に付け替えても、判定は付け替えのもとで同じ。
  そのままでは反証の見込みが立っていた（型検査器が ontology の名前を読む）。#216（sys_law_names_grammar）で、型検査器の
  コードに文字列として現れる名前（文法の語・層の名・基礎の関係・法則の名・ほか 12 語）が数えられた。
  絞り: 付け替えの外に置くのを「名前で読むと分かっている語」に広げ、その外に隠れた名前への依存があるかを見る。

手順（規則で決める）:
  体系を tc.build() で読み、付け替えの候補を作る: ノードの短い名と個体の名。
  外に置くもの（付け替えない）:
    文法の語と節の名、層の名と signature、基礎の関係の名、シグネチャの個体（ontology の individuals）、
    type_checker.py と exp_check.py の文字列の定数（docstring も含め、すべて）に一致する名、
    yaml で特別に読まれる語（true, false, null, yes, no, on, off）。
  残りの名を、出てくる順（ソート）に zq0, zq1, ... へ一対一に付け替える（新しい名は体系のどの語とも重ならない）。
  付け替えは、写し（cscl.yaml・cscl・exp/src・exp/tests・exp/experiments/results）の cscl/ と exp/src/ の yaml の全文に、
    語の境界（前後が英数字でも _ でも / でもない。後ろが .yaml・.json・.py でない）で当てる。
  変種:
    before: 付け替えなし。
    R: 上の付け替え。
    C（対照）: R に加えて、名前で読むと分かっている role も付け替える（zqrole）。
  測るもの:
    errors: tc.build() の誤りの数。ec_errors: exp_check.build() の誤りの数（参考。判定には使わない）。
    facts_diff: 法則を評価した事実（tc.evaluate）の文を、付け替えを逆に戻して（文字列の上で同じ境界で）比べた、
      before との対称差の大きさ。
判定:
  C の errors も facts_diff も 0 なら「外れ」（付け替えが効いていないか、role を名前で読んでいない）。
  そうでなく、R で errors が before と同じ（0）で facts_diff が 0 なら支持。そうでなければ反証（誤りの中身を行に書く）。

開示（結果を見る前に分かっていること）:
  - #216 の数え: 型検査器のコードに識別子として現れる名は 72 が文法の語、10 が法則の名、12 がほか。
  - 名前の接頭辞（v_ など）や並びの順に依る読み方があるかは調べていない。結果は予想しない。
  - ec は、結果ファイルの綴り（v_spell や val の text）と付け替えた名がぶつかると誤りを出しうる。そのため判定に使わない。
使い方:
  python exp/experiments/sys_renaming_invariant.py
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_renaming_invariant.json"
CODE = ("cscl/bootstrap/type_checker/type_checker.py", "exp/src/exp_check.py")
YAML_WORDS = {"true", "false", "null", "yes", "no", "on", "off"}

PROBE = r'''
import contextlib, io, json, os, re, sys
sys.path[:0] = ["cscl/bootstrap/type_checker", "exp/src"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, Dm = tc.build()
errs = [str(e) for e in tc.errors]
with contextlib.redirect_stdout(io.StringIO()):
    import exp_check
    del tc.errors[:]
    try:
        exp_check.build()
    except SystemExit:
        pass
ec = len(tc.errors)
F = tc.Facts(T.syntax_facts())
tc.evaluate(tc.law_rules(O), F, tc.variables(O))
inv = json.load(open(os.environ["RN_INV"], encoding="utf-8")) if os.environ.get("RN_INV") else {}
if inv:
    pat = re.compile(r"(?<![\w/])(" + "|".join(sorted(map(re.escape, inv), key=len, reverse=True)) + r")(?![\w/])(?!\.(?:yaml|json|py))")
    back = lambda s: pat.sub(lambda m: inv[m.group(1)], s)
else:
    back = lambda s: s
stmts = sorted({back(r + " " + str(x)) for r, xs in F.by.items() for x in xs})
out = {"errors": len(errs), "ec_errors": ec, "err_text": [back(e) for e in errs[:20]], "stmts": stmts}
if os.environ.get("RN_NAMES"):
    core = set((O.get("individuals") or {}))
    out["names"] = {"nodes": sorted({tc.short(k) for k in T.N}), "inds": sorted(T.I),
                    "gram": sorted(set(T.G) | {w for v in T.G.values() for w in (v or [])}),
                    "doms": sorted(set(Dm) | {"signature"}), "base": sorted(O["base"]), "core": sorted(core)}
print(json.dumps(out, ensure_ascii=False))
'''


def code_constants():
    out = set()
    for p in CODE:
        for n in ast.walk(ast.parse((ROOT / p).read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                out.add(n.value)
    return out


def copy_tree(d):
    for p in ("cscl.yaml", "cscl", "exp/src", "exp/tests", "exp/experiments/results"):
        src, dst = ROOT / p, Path(d) / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)


def run(mapping, names=False):
    with tempfile.TemporaryDirectory() as d:
        copy_tree(d)
        env = dict(os.environ)
        if mapping:
            pat = re.compile(r"(?<![\w/])(" + "|".join(sorted(map(re.escape, mapping), key=len, reverse=True))
                             + r")(?![\w/])(?!\.(?:yaml|json|py))")
            for base in ("cscl", "exp/src"):
                for f in Path(d, base).rglob("*.yaml"):
                    s = f.read_text(encoding="utf-8")
                    f.write_text(pat.sub(lambda m: mapping[m.group(1)], s), encoding="utf-8")
            inv = Path(d) / "inv.json"
            inv.write_text(json.dumps({v: k for k, v in mapping.items()}, ensure_ascii=False), encoding="utf-8")
            env["RN_INV"] = str(inv)
        if names:
            env["RN_NAMES"] = "1"
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True, env=env)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    b0 = run({}, names=True)
    N = b0["names"]
    excl = set(N["gram"]) | set(N["doms"]) | set(N["base"]) | set(N["core"]) | code_constants() | YAML_WORDS
    cand = sorted((set(N["nodes"]) | set(N["inds"])) - excl)
    R = {w: f"zq{i}" for i, w in enumerate(cand)}
    assert not set(R.values()) & (set(N["nodes"]) | set(N["inds"]))
    C = R | {"role": "zqrole"}
    res = {"before": b0, "R": run(R), "C": run(C)}
    base_st = set(b0["stmts"])
    rows = {}
    for k, r in res.items():
        diff = set(r["stmts"]) ^ base_st
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "facts_diff": len(diff),
                                "n_stmts": len(r["stmts"])}
        rows |= {f"diff {k} {i}": {"text": t[:300], "side": "after" if t in r["stmts"] else "before"}
                 for i, t in enumerate(sorted(diff)[:20])}
        rows |= {f"error {k} {i}": {"text": e} for i, e in enumerate(r["err_text"])}
    v = lambda k, x: rows[f"variant {k}"][x]
    if v("C", "errors") == 0 and v("C", "facts_diff") == 0:
        verdict = "外れ"
    elif v("R", "errors") == v("before", "errors") == 0 and v("R", "facts_diff") == 0:
        verdict = "支持"
    else:
        verdict = "反証"
    rows["summary 要約"] = {"verdict_support": int(verdict == "支持"), "n_renamed": len(R), "n_excluded": len(excl),
                          "n_candidates_all": len(set(N["nodes"]) | set(N["inds"])),
                          **{f"{k}_{x}": v(k, x) for k in res for x in ("errors", "ec_errors", "facts_diff")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, x in rows.items():
        if not k.startswith(("error", "diff")):
            print(k, json.dumps(x, ensure_ascii=False))
    print("判定:", verdict)


if __name__ == "__main__":
    main()
