"""sys_family_refers_laws の訂正（開示）: 元の結果（sys_family_refers_laws.json）では、写しに exp/experiments/results を
置かなかったので、ec が結果ファイルを見つけられない誤りを 1751 出した（before・R・U で同じ数）。ec の誤りは、この測りの欠けで
決まっており、仮説について何も言わない。tc の誤りは R・U とも 0、事実の差（changed）も R・U とも 0 だった。

訂正: 写しに exp/experiments/results を写す（実物への symlink。写しの中で結果ファイルは書かない）。他の手順・判定・変種は
  sys_family_refers_laws.py のまま。判定は、取り直した R の errors・ec_errors・changed に、規則（どれも 0 なら支持）をそのまま
  当てる。元の結果ファイルは上書きしない。出力は sys_family_refers_laws_fix.json。

結果を見て分かっていること（開示）: 元の結果（上）。特に、体系にない法則を参照した U が、tc で拒まれなかった（errors 0）。

使い方:
  python exp/experiments/sys_family_refers_laws_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_family_refers_laws as m  # noqa: E402

m.OUT = m.ROOT / "exp/experiments/results/sys_family_refers_laws_fix.json"
_copy = m.shutil.copytree


def copytree(src, dst, *a, **k):
    r = _copy(src, dst, *a, **k)
    if Path(src) == m.ROOT / "exp/src":
        (Path(dst).parent / "experiments").mkdir(exist_ok=True)
        (Path(dst).parent / "experiments/results").symlink_to(m.ROOT / "exp/experiments/results")
    return r


m.shutil.copytree = copytree

if __name__ == "__main__":
    m.main()
