"""h_sync_scan_quadratic を確かめる: issue の同期の時間は、主張の数とノードの数の両方に依存する。

仮説（exp.yaml）: v_refer(h, v_depend(magnitude, [hypothesis, decision, syntax.nodes]))。登録 #623。
  出どころ: 利用者の指摘（同期が長い。データ量に線形なら手を打つ）。sync_issues.py の claims() は、主張ごとに
  cscl と exp の yaml をすべて読み直す。

入力: GitHub の issues ワークフロー（issues.yml）の、push で起きて終わった実行の一覧（actions の API の
  list_workflow_runs、event=push、status=completed、per_page=100 の 1 頁）。引数で渡す JSON の写し。
  各実行の時間 t = updated_at - run_started_at（秒）。head_sha をそのときの体系とする。
操作: 各 head_sha で、git show で cscl/ と exp/ の下の .yaml を読む（作業木は書き換えない）。
  L: それらの行の数の和。
  C: 行のうち、正規表現 ^  (h|d)_\\w+: \\{is: に当たるものの数（仮説と決定の宣言）。
  conclusion が success でない実行と、head_sha を読めない実行は除き、数える（n_drop）。
  モデル（最小二乗、切片あり）: lin: t ~ L、quad: t ~ C*L。各の決定係数 r2_lin, r2_quad。
行（ops_sync_duration.json）: 実行ごとに sha, t, C, L。s: n_run, n_drop, r2_lin, r2_quad, slope_quad。
  入力の写しは results/ops_sync_duration_runs.json に置く（sha・時間・結論だけ）。

判定（事前に決める）:
  n_run < 20 なら外れ（状態を変えない）。
  支持: r2_quad > r2_lin かつ r2_quad >= 0.7。
  反証: それ以外。
開示: 実行一覧は、この手順を書く前に取得し、15 件ほどの時間を見ている（C と L は見ていない）。
  時間には runner の準備（checkout、python、pip）が入り、ばらつく。
  C と L は互いに強く相関しうるので、二つのモデルの差は小さく出うる。
  走らせる前に C・L・決定係数は計算していない。
使い方:
  python exp/experiments/ops_sync_duration.py <runs.json>
"""
import datetime as D
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
RES = ROOT / "exp/experiments/results"
PAT = re.compile(r"^  (h|d)_\w+: \{is:", re.M)


def sec(r):
    f = lambda s: D.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (f(r["updated_at"]) - f(r.get("run_started_at") or r["created_at"])).total_seconds()


def size(sha):
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha, "cscl", "exp"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    L = C = 0
    for n in names:
        if n.endswith(".yaml"):
            t = subprocess.run(["git", "show", f"{sha}:{n}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            L += t.count("\n")
            C += len(PAT.findall(t))
    return C, L


def fit(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx
    a = my - b * mx
    ss = sum((v - my) ** 2 for v in y)
    se = sum((v - a - b * u) ** 2 for u, v in zip(x, y))
    return 1 - se / ss, b


def main(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    runs = d.get("workflow_runs", d)
    keep = [{"sha": r["head_sha"], "t": sec(r), "conclusion": r.get("conclusion")} for r in runs]
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "ops_sync_duration_runs.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1) + "\n")
    rows, drop = {}, 0
    for r in keep:
        if r["conclusion"] != "success":
            drop += 1
            continue
        try:
            C, L = size(r["sha"])
        except subprocess.CalledProcessError:
            drop += 1
            continue
        rows[f"{len(rows):03d} {r['sha'][:7]}"] = {"sha": r["sha"], "t": r["t"], "C": C, "L": L}
    t = [r["t"] for r in rows.values()]
    r2_lin, _ = fit([r["L"] for r in rows.values()], t)
    r2_quad, b = fit([r["C"] * r["L"] for r in rows.values()], t)
    s = {"n_run": len(rows), "n_drop": drop, "r2_lin": r2_lin, "r2_quad": r2_quad, "slope_quad": b}
    (RES / "ops_sync_duration.json").write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
