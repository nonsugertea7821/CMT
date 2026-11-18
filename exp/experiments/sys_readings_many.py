"""h_readings_many を確かめる: 同じ主語の読みの式が2つ以上あるとき、先に書いた式も、読まれれば検査に通るか。

仮説（claims.yaml）: 述べる(syntax.many, 読みの式)。many が読みの式に掛かれば、同じ主語の式はどれも読まれる。
  いまの型検査器の gather は、読みの式を代入で集めるので、後の式が先の式を上書きする（#223 で観察: 14 式・7 主語）。
  ここでは、many を読みの式に掛けても体系が保たれるか、すなわち、上書きされて読まれていない先の式が、
  読まれたときに検査（tc と、checkers の ec）に通るかを数える。

手順（規則で決める）:
  cscl.yaml の root・library・include の yaml を、その順に行ごとに読み、最上位の事実の行で
  「- {is: v_refer, from: 主語, to: {」の形（is は領域を付けてもよい）のものを、主語ごとに集める。
  主語ごとの式が2つ以上なら、最後のもの以外（先の式）それぞれについて変異を1つ作る:
    その主語の、それより後の式の行をすべて消す（先の式が、その主語の最後の式になる）。
  変異ごとに、HEAD の写し（git archive と結果のフォルダ）で型検査器を走らせ、検査に通ったかを記録する。
  変異の前の写しが検査に通らなければ測らない。一度に4つ並べる。
  行（sys_readings_many.json）: "hidden 主語 #k": {kind（h_ 0、o_ 1、d_ 2、ほか 3）, passed（0 か 1）, n_errors}
  要約: n_subjects, n_hidden, n_passed, n_failed
判定: n_failed が 0 なら支持（先の式はどれも、読まれても検査に通る）。1 以上なら反証。

開示（結果を見る前に分かっていること）:
  - #223 で、上書きされる式は 7 主語にある: h_layers_unhardcode と、o_sys_money_*・o_sys_unit_axis_* の観察。
  - h_layers_unhardcode の先の式は「型検査器は名前の選び方に依らない」で、h_renaming_invariant と同じ中身。
  - o_sys_money_unit_stops_overextension の先の式は、前と後の値の比べ（v_come_before）。測った値がそれを満たすかは見ていない。
  - 仮説の判定の ec は、仮説の読みの式と観察を照らす。先の式が読まれると、照らす相手が変わる。どうなるかは予想しない。
  - この測り方は、仮説（言語の規則）そのものでなく、規則を変えても今の体系が保たれるかを見る。

使い方:
  python exp/experiments/sys_readings_many.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
LINE = re.compile(r"^\s*- \{is: (?:[a-z_]+\.)?v_refer, from: ([A-Za-z0-9_.]+), to: \{")
KINDS = {"h_": 0, "o_": 1, "d_": 2}


def yaml_files():
    c = yaml.safe_load((ROOT / "cscl.yaml").read_text(encoding="utf-8"))
    pats = [c["root"]] + c.get("library", []) + c.get("include", [])
    return [p.relative_to(ROOT).as_posix() for g in pats for p in sorted(ROOT.glob(g))]


def check(d):
    r = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=d, capture_output=True, text=True)
    m = re.search(r"検査に失敗: (\d+) 件", r.stdout)
    n = int(m.group(1)) if m else (0 if "検査に成功" in r.stdout else -1)
    return n, [ln.strip() for ln in r.stdout.splitlines() if ln.startswith(" - ")][:5]


def worktree():
    d = Path(tempfile.mkdtemp(prefix="readings_"))
    subprocess.run(f"git archive HEAD cscl exp/src cscl.yaml | tar -x -C {d}", shell=True, cwd=ROOT, check=True)
    shutil.copytree(OUT, d / "exp/experiments/results", dirs_exist_ok=True)
    return d


def main():
    by = {}
    for rel in yaml_files():
        for ln, text in enumerate((ROOT / rel).read_text(encoding="utf-8").split("\n")):
            m = LINE.match(text)
            if m:
                by.setdefault(m.group(1), []).append((rel, ln))
    multi = {s: fs for s, fs in by.items() if len(fs) > 1}
    base = worktree()
    n0, msg0 = check(base)
    if n0 != 0:
        raise SystemExit(f"写した作業場が検査に通らない: {msg0}")
    jobs = [(s, k) for s, fs in sorted(multi.items()) for k in range(len(fs) - 1)]

    def one(job):
        s, k = job
        d = Path(tempfile.mkdtemp(prefix="readings_m_"))
        shutil.copytree(base, d, dirs_exist_ok=True)
        drop = {}
        for rel, ln in multi[s][k + 1:]:
            drop.setdefault(rel, set()).add(ln)
        for rel, lns in drop.items():
            p = d / rel
            L = p.read_text(encoding="utf-8").split("\n")
            p.write_text("\n".join(x for i, x in enumerate(L) if i not in lns), encoding="utf-8")
        n, msgs = check(d)
        shutil.rmtree(d)
        return job, n, msgs

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    shutil.rmtree(base)
    rows, detail = {}, []
    for (s, k), n, msgs in res:
        rel, ln = multi[s][k]
        rows[f"hidden {s} #{k}"] = {"kind": KINDS.get(s[:2], 3), "passed": int(n == 0), "n_errors": n}
        detail.append({"subject": s, "index": k, "file": rel, "line": ln + 1, "errors": n, "msgs": msgs})
    R = list(rows.values())
    rows["summary 要約"] = {"n_subjects": len(multi), "n_hidden": len(R), "n_passed": sum(r["passed"] for r in R),
                          "n_failed": sum(1 - r["passed"] for r in R)}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_readings_many.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_readings_many.py", "_commit": head, "rows": rows, "hidden": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    for x in detail:
        print(x["subject"], x["index"], x["errors"], x["msgs"][:2])
    print("判定:", "支持" if rows["summary 要約"]["n_failed"] == 0 else "反証")


if __name__ == "__main__":
    main()
