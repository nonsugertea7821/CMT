"""h_checker_find_by_ancestry を確かめる: 検査器が語を「occurrent の直下」でなく祖先（extends の鎖）でたどって見つければ、
端の広い動詞を下の層に置く移し替え（#537 の M1）が tc を通る。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, syntax.extends))。登録 #538。
  出どころ: #537（h_wider_verb_lower、反証）。M1（exp.v_rely を ontology へ移し、v_depend の extends を v_rely にする）で、
  tc が「役割だが、根拠となる定義（依存する定義）がない」で落ちた。検査器は 依存する を under_o（extends == occurrent）から探す。

操作（一時の写し。体系のファイルと検査器は書き換えない）:
  写し（.git と __pycache__ を除く）を作る。条件は 2×2:
    checker: orig（そのまま）/ anc（写しの検査器で、依存する を探す行の under_o を、occurrent を祖先に持つノード全部に替える）
    data:    base（そのまま）/ m1（#537 の M1 と同じ移し替え）
  anc の置き換え: 依存する の行の `for x in under_o` を `for x in desc_o` にし、その前に
    desc_o = extends の鎖をたどって occurrent に届く（自身は除く）ノード の定義を足す。ほかの語の探し方は変えない。
  各条件で写しの tc を走らせ、通る（"検査に成功" を含む）を 1、落ちるを 0 とする。
行（sys_checker_find_by_ancestry.json）: "orig base"・"orig m1"・"anc base"・"anc m1"・"summary 要約"

判定（事前に決める）:
  orig base が 0、または置き換え・移し替えの文字列が見つからなければ外れ（状態を変えない）。
  支持: anc base = 1 かつ anc m1 = 1。
  反証: anc base = 1 かつ anc m1 = 0。
  anc base = 0 なら外れ（置き換えが体系そのものを壊す）。
開示: #537 の M1 の落ち方（tail の 4 行）を見てからこの手順を書いた。
  依存する の探索が落ちたのか、別の段で落ちたのかは、tail だけでは確かめていない。
使い方:
  python exp/experiments/sys_checker_find_by_ancestry.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_checker_find_by_ancestry.json"
ONT = "cscl/library/ontology/ontology.yaml"
SRC = "exp/src/exp.yaml"
TC = "cscl/bootstrap/type_checker/type_checker.py"
OLD_DEP = 'self.v_depend = one("依存する", [x for x in under_o if'
UNDER = '        under_o = [x for x, n in N.items() if n.get("extends") == self.top_o]\n'
DESC = ('        def _reach_o(x, seen=()):\n'
        '            e = N.get(x, {}).get("extends")\n'
        '            return e == self.top_o or (isinstance(e, str) and e in N and e not in seen and _reach_o(e, seen + (x,)))\n'
        '        desc_o = [x for x in N if _reach_o(x)]\n')


def copy():
    tmp = tempfile.mkdtemp()
    dst = Path(tmp) / "repo"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return tmp, dst


def tc_ok(dst):
    p = subprocess.run([sys.executable, str(dst / TC)], cwd=dst, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip().splitlines()
    return int("検査に成功" in p.stdout), out[:3] + out[-3:]


def line_of(text, name):
    return re.search(rf"^  {re.escape(name)}: \{{.*\}}\n", text, re.M)


def patch_checker(dst):
    t = (dst / TC).read_text(encoding="utf-8")
    if t.count(UNDER) != 1 or t.count(OLD_DEP) != 1:
        return 0
    t = t.replace(UNDER, UNDER + DESC, 1).replace(OLD_DEP, OLD_DEP.replace("under_o", "desc_o"), 1)
    (dst / TC).write_text(t, encoding="utf-8")
    return 1


def move_m1(dst):
    src = (dst / SRC).read_text(encoding="utf-8")
    ont = (dst / ONT).read_text(encoding="utf-8")
    a, s2 = line_of(src, "v_rely"), line_of(ont, "v_depend")
    if not (a and s2) or "extends: occurrent" not in s2.group(0):
        return 0
    moved = a.group(0)
    (dst / SRC).write_text(src[:a.start()] + src[a.end():], encoding="utf-8")
    ont = ont.replace(s2.group(0), s2.group(0).replace("extends: occurrent", "extends: v_rely", 1), 1)
    b = line_of(ont, "v_depend")
    ont = ont[:b.start()] + moved + ont[b.start():]
    (dst / ONT).write_text(ont, encoding="utf-8")
    return 1


def main():
    rows = {}
    found = 1
    for ck in ("orig", "anc"):
        for dk in ("base", "m1"):
            tmp, dst = copy()
            try:
                f = 1
                if ck == "anc":
                    f &= patch_checker(dst)
                if dk == "m1":
                    f &= move_m1(dst)
                if not f:
                    found = 0
                    rows[f"{ck} {dk}"] = {"found": 0}
                    continue
                ok, tail = tc_ok(dst)
                rows[f"{ck} {dk}"] = {"found": 1, "tc_ok": ok, "tail": tail}
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    g = lambda k: rows.get(k, {}).get("tc_ok", 0)
    if not found or not g("orig base") or not g("anc base"):
        verdict = "外れ"
    else:
        verdict = "支持" if g("anc m1") else "反証"
    s = {"found": found, "orig_base_tc_ok": g("orig base"), "orig_m1_tc_ok": g("orig m1"),
         "anc_base_tc_ok": g("anc base"), "anc_m1_tc_ok": g("anc m1"), "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
