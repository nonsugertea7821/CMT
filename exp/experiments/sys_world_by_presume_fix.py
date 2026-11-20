"""h_world_by_presume_facts の訂正（sys_world_by_presume.py の後、結果を見てから、実行の前に登録した）。

訂正の理由: 元の手順は other を「B の誤りに無いもの」と決めた。そのため、版 D が std に二つ目の
  v_presume を足したこと自体から既にある検査が出す誤り（「ontology.yaml std: 関係 world の事実が2つ以上ある」、
  終点 world が many でない関係を一つの個体が二つ持つ）を、other に数えた（other_D = 1）。
  元の結果: すべての版で agree = 1。py_R = rule_R = 11、py_D = 1、rule_D = 2、B と Q は 0。
訂正した操作: 版ごとに、文も規則も足さない対照（検査器と syntax.yaml の写しを変えず、版の書き換えだけ行う）を
  もう 1 回走らせる。other_<v> は、足した版の誤りのうち、world_declared・world_unique・world_rule の誤りでも、
  同じ版の対照の誤りでもないものの数とする。
  ほかは元と同じ（足す文・関係・規則・版・agree の定義・判定）。
行（sys_world_by_presume_fix.json）: 元の行に加え、
  ctrl_<v>  対照の誤りの数

使い方:
  python exp/experiments/sys_world_by_presume_fix.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_world_by_presume as base

OUT = base.ROOT / "exp/experiments/results/sys_world_by_presume_fix.json"


def run(case, add):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        R = base.ROOT
        shutil.copy(R / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(R / "cscl", d / "cscl")
        shutil.copytree(R / "exp/src", d / "exp/src")
        shutil.copytree(R / "exp/experiments/results", d / "exp/experiments/results")
        if add:
            base.patch(d / base.TC, base.TC_ANCHOR, base.TC_ADD + base.TC_ANCHOR)
            base.patch(d / base.SYN, base.SYN_IND_ANCHOR, base.SYN_IND_ANCHOR + base.SYN_IND)
            base.patch(d / base.SYN, base.SYN_FACTS_ANCHOR, base.SYN_FACTS_ANCHOR + base.SYN_FACTS)
        for f, old, new in base.CASES[case]:
            base.patch(d / f, old, new)
        r = subprocess.run([sys.executable, "-c", base.PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return ["probe failed: " + r.stderr[-300:]]


def main():
    summary, texts = {}, {}
    for c in base.CASES:
        errs = run(c, True)
        ctrl = run(c, False)
        py = [e for e in errs if "法則 world_declared" in e]
        ru = [e for e in errs if "法則 world_rule" in e]
        rd = [e for e in errs if "法則 world_unique" in e]
        other = [e for e in errs if e not in py and e not in ru and e not in rd and e not in ctrl]
        py_law = {m.group(1) for e in py for m in [re.search(r"法則 (\S+) は否定を前提に使うが", e)] if m}
        py_dom = {m.group(1) for e in py for m in [re.search(r"領域 (\S+) が、書かれていない文の扱いを2つ以上", e)] if m}
        rule_law = set().union(set(), *map(base.var1, ru))
        rule_dom = set().union(set(), *map(base.var1, rd))
        summary[f"py_{c}"] = len(py)
        summary[f"rule_{c}"] = len(ru) + len(rd)
        summary[f"agree_{c}"] = int(py_law == rule_law and py_dom == rule_dom)
        summary[f"other_{c}"] = len(other)
        summary[f"ctrl_{c}"] = len(ctrl)
        texts[f"errors {c}"] = (py + ru + rd + other)[:6]
        texts[f"control {c}"] = ctrl[:6]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
