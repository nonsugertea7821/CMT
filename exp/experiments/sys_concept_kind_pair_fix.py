"""sys_concept_kind_pair の訂正: exp_check を、結果ファイルを入れた写しで測り直す。結果を見る前に、この手順を登録した。

訂正の理由（開示）: sys_concept_kind_pair は写しに cscl.yaml, cscl, exp/src だけを入れ、exp/experiments/results を入れなかった。
  exp_check は結果ファイルから測定値を読むので、何も変えていない L でも ec_fail 1 になった
  （写しで exp_check を走らせ、「測定値でない」の誤りが出ることを確かめた）。型検査の量（errors, n_both, rel_eq_f）は
  結果ファイルを読まないので、訂正しない。
手順: L, E, N（枠を足さない版）それぞれについて、写しに exp/experiments/results も入れ、sys_concept_kind_pair.edit で
  同じ変更をして、exp_check を 1 回走らせる。
数える量: ec_fail_<V>（終了コードが 0 でなければ 1）, ec_lines_<V>（出力のうち " - " で始まる行の数。記述）
判定: sys_concept_kind_pair の判定の ec_fail を、この値に置き換える（ほかは変えない）。
行（sys_concept_kind_pair_fix.json）: "summary 要約": 上の量、"texts": 版ごとの誤りの行（先頭 10）
使い方:
  python exp/experiments/sys_concept_kind_pair_fix.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "exp/experiments")]
from sys_concept_kind_pair import SYN, edit  # noqa: E402

OUT = ROOT / "exp/experiments/results/sys_concept_kind_pair_fix.json"


def run(version):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src", "exp/experiments/results"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        f = Path(d) / SYN
        f.write_text(edit(f.read_text(encoding="utf-8"), version, False), encoding="utf-8")
        out = subprocess.run([sys.executable, "exp/src/exp_check.py"], cwd=d, capture_output=True, text=True)
        lines = [l for l in (out.stdout + out.stderr).splitlines() if l.startswith(" - ")]
        return int(out.returncode != 0), lines


def main():
    summ, texts = {}, {}
    for v in "LEN":
        fail, lines = run(v)
        summ |= {f"ec_fail_{v}": fail, f"ec_lines_{v}": len(lines)}
        texts[v] = lines[:10]
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ}, "texts": texts}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, t in texts.items():
        for e in t:
            print(k, e)


if __name__ == "__main__":
    main()
