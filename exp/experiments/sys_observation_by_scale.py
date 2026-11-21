"""h_observation_by_scale を確かめる: 体系の観察の値は、体系の規模に依存する。

仮説（exp.yaml）: v_refer(h, v_depend(observation, [syntax.system, magnitude]))。登録 #609（issue #610）。

操作: main の first-parent の履歴から写しを取り、各写しで体系を読む（リポジトリの作業木は書き換えない）。
  写し: git rev-list --first-parent --reverse main の 431 個（登録時の数。走らせる時点の数を使う）から、
        添字 round(i * (n-1) / 11)（i = 0..11）の 12 個。写しは git archive で一時のディレクトリに展開する。
  各写しで、その写しの type_checker の build() を別のプロセスで呼ぶ。通らない写しは除き、数える（n_fail）。
  値（ノードの集まり T.N の上で）:
    n_node: ノードの数（規模）。
    m_mod: mod を書いたノードの割合。
    m_verb: holds・pre・post のどれかを書いたノードの割合。
    m_depth: T.ancestors(x) の長さの平均。
  ずれ: 各値について、最後の写し（今の main）の値との差の絶対値。
  rho: 最後の写しを除いた通った写しで、n_node とずれの Spearman の順位相関（同順位は平均順位）。
行（sys_observation_by_scale.json）: 写しごとに commit, n_node, m_mod, m_verb, m_depth。
  s: n_snap, n_fail, rho_mod, rho_verb, rho_depth, maxdev_mod, maxdev_verb, maxdev_depth, n_dep。
  n_dep: rho <= -0.5 かつ maxdev >= 0.05 を満たす値の数。

判定（事前に決める）:
  通った写しが 5 未満なら外れ（状態を変えない）。
  支持: n_dep >= 2（規模が大きくなるほど、観察の値が今の値に近づく値が多数）。
  反証: n_dep <= 1。
開示: 一つの体系の時間の上での規模で、別の体系の規模ではない。規模と同時に書き方の取り決めも変わっているので、
  依存が見えても規模だけによるとは言えない。ずれが小さい値は、規模に依存しないと数える（maxdev の閾）。
  走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_observation_by_scale.py
"""
import json
import subprocess
import sys
import tarfile
import io
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
K = 12
CHILD = r"""
import contextlib, io, json, os, sys
os.chdir(sys.argv[1]); sys.path[:0] = [os.path.join(sys.argv[1], "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    r = tc.build()
T = r[0] if isinstance(r, tuple) else r
N = T.N
n = len(N)
m_mod = sum(1 for v in N.values() if isinstance(v, dict) and v.get("mod") is not None) / n
m_verb = sum(1 for v in N.values() if isinstance(v, dict) and any(v.get(k) for k in ("holds", "pre", "post"))) / n
m_depth = sum(len(T.ancestors(x)) for x in N) / n
print(json.dumps({"n_node": n, "m_mod": m_mod, "m_verb": m_verb, "m_depth": m_depth}))
"""


def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    c = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return c / (va * vb) if va and vb else 0.0


def main():
    revs = subprocess.run(["git", "rev-list", "--first-parent", "--reverse", "main"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.split()
    n = len(revs)
    pick = sorted({round(i * (n - 1) / (K - 1)) for i in range(K)})
    rows, fail = {}, 0
    for i in pick:
        rev = revs[i]
        with tempfile.TemporaryDirectory() as d:
            tar = subprocess.run(["git", "archive", rev], cwd=ROOT, capture_output=True, check=True).stdout
            tarfile.open(fileobj=io.BytesIO(tar)).extractall(d)
            p = subprocess.run([sys.executable, "-c", CHILD, d], capture_output=True, text=True)
        try:
            rows[f"{i:03d} {rev[:7]}"] = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            fail += 1
    keys = sorted(rows)
    s = {"n_snap": len(rows), "n_fail": fail}
    if len(rows) >= 2:
        last = rows[keys[-1]]
        prev = [rows[k] for k in keys[:-1]]
        s["n_dep"] = 0
        for m in ("mod", "verb", "depth"):
            dev = [abs(r[f"m_{m}"] - last[f"m_{m}"]) for r in prev]
            s[f"rho_{m}"] = spearman([r["n_node"] for r in prev], dev)
            s[f"maxdev_{m}"] = max(dev)
            s["n_dep"] += s[f"rho_{m}"] <= -0.5 and s[f"maxdev_{m}"] >= 0.05
    out = ROOT / "exp/experiments/results/sys_observation_by_scale.json"
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
