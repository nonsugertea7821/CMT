"""h_measure_excludes_claim_kinds を確かめる: 主張の種類で項を除いた読みは、主張が増えても動かないか。

仮説（exp.yaml）: v_refer(h, v_depend(measurement_family, hypothesis, neg))。登録 #630（issue #631）。
  出どころ: #629（主張の項を除くと読みが動いた）。対の解き方は h_claims_apart_by_domain（#636、mixed）。

問い: 測る族が主張に依らないなら、主張が書き足されていく履歴の上で、種類で除いた読みは、すべての項の読みより動かない。
操作: main の first-parent の履歴から写しを取り、各写しで体系を読む（リポジトリの作業木は書き換えない）。
  写し: git rev-list --first-parent --reverse main の最後の 100 個（走らせる時点）から、
        添字 round(i * 99 / 9)（i = 0..9）の 10 個。git archive で一時のディレクトリに展開する。
  各写しで、その写しの type_checker の build() を別のプロセスで呼び、#629 と同じ定め方で J を数える
  （項・錨・主張の個体・主張の項・J は #629 のスクリプトと同じ。コードは写した）。通らない写しは除き、数える（n_fail）。
  動詞: #629 の対象の 15 語（下の V）。その写しで領域が二つ未満の動詞は、その写しでは数えない。
  読み all: すべての項。読み kind: 主張の項を除く。
  sd_all(v), sd_kind(v): 両方の読みで J がある写しの上での、J の標準偏差（母分散）。写しが 3 未満の動詞は除く。
  ch_all(v), ch_kind(v): その写しの上で、形式・実在（J >= 0.5）が一度でも入れ替わったか。
行（sys_measure_excludes_claim_kinds.json）: 写しごとに commit, n_claim_ind と、動詞ごとの J_all, J_kind。
  s: n_snap, n_fail, n_verb, mean_sd_all, mean_sd_kind, ratio（mean_sd_kind / mean_sd_all）, n_ch_all, n_ch_kind。

判定（事前に決める）:
  通った写しが 5 未満か n_verb < 4 なら外れ（状態を変えない）。
  支持: ratio <= 0.5（種類で除くと、履歴の上での揺れが半分以下になる）。
  反証: ratio >= 1（種類で除いても揺れは減らない）。
  mixed: それ以外。
開示: 履歴の上では、主張だけでなく概念の定義も変わる。どちらの読みにも概念の変化は入るので、比べられるのは
  主張の分の揺れだけで、それも概念の変化と重なれば分けられない。主張の種類の定め方（std.hypothesis など）が
  古い写しで違えば、その写しの kind の除き方は今と違う。走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_measure_excludes_claim_kinds.py
"""
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
K = 10
LAST = 100
V = ["ontology.is", "ontology.p", "ontology.v_above", "ontology.v_come_after", "ontology.v_come_before",
     "ontology.v_compose", "ontology.v_depend", "ontology.v_design", "ontology.v_express", "ontology.v_involve",
     "ontology.v_level", "ontology.v_not_before", "ontology.v_perform", "ontology.v_stage", "ontology.v_trigger"]
CHILD = r"""
import contextlib, io, itertools, json, os, sys
from pathlib import Path
root = Path(sys.argv[1]); V = json.loads(sys.argv[2])
os.chdir(root); sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    r = tc.build()
T = r[0] if isinstance(r, tuple) else r
N = T.N
CLAIM_KINDS = ("std.hypothesis", "exp.observation", "exp.backlog_item")
def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k != "display":
                yield from strings(x)
def anchor(x):
    for y in [x] + list(T.ancestors(x)):
        if T.domain(y) == "ontology":
            return y
    return None
cfg = tc.yload((root / "cscl.yaml").read_text(encoding="utf-8"))
files = [root / cfg["root"]]
for pat in list(cfg.get("library") or []) + list(cfg.get("include") or []):
    files += sorted(root.glob(pat))
loaded, claim_ind = [], set()
for f in files:
    y = tc.yload(f.read_text(encoding="utf-8")) or {}
    dom = y.get("domain")
    if not isinstance(dom, str):
        continue
    loaded.append((dom, y))
    for k, v in (y.get("individuals") or {}).items():
        k_is = v.get("is") if isinstance(v, dict) else None
        r = T.resolve(k_is, dom) if isinstance(k_is, str) else None
        if r in N and any(c in N and T.is_a(r, c) for c in CLAIM_KINDS):
            claim_ind.add(f"{dom}.{k}")
items = []
for dom, y in loaded:
    for sec in ("nodes", "individuals", "axes"):
        for k, v in (y.get(sec) or {}).items():
            items.append((dom, f"{dom}.{k}" if sec == "nodes" else None, f"{dom}.{k}" if sec == "individuals" else None, v))
    for v in y.get("facts") or []:
        items.append((dom, None, None, v))
A = {"all": {v: {} for v in V}, "kind": {v: {} for v in V}}
for dom, self_id, self_ind, v in items:
    raw = list(strings(v))
    claim = self_ind in claim_ind or any(w in claim_ind or f"{dom}.{w}" in claim_ind for w in raw)
    rs = [T.resolve(w, dom) for w in raw]
    rs = [r for r in rs if r in N]
    for verb in set(rs):
        if verb not in A["all"] or verb == self_id:
            continue
        anc = {an for r in rs if r != verb for an in [anchor(r)] if an}
        A["all"][verb].setdefault(dom, set()).update(anc)
        if not claim:
            A["kind"][verb].setdefault(dom, set()).update(anc)
def J(byd):
    doms = sorted(byd)
    if len(doms) < 2:
        return None
    js = []
    for a, b in itertools.combinations(doms, 2):
        u = byd[a] | byd[b]
        js.append(len(byd[a] & byd[b]) / len(u) if u else 1.0)
    return sum(js) / len(js)
print(json.dumps({"n_claim_ind": len(claim_ind),
                  "J": {v: [J(A["all"][v]), J(A["kind"][v])] for v in V}}))
"""


def sd(xs):
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def main():
    revs = subprocess.run(["git", "rev-list", "--first-parent", "--reverse", "main"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.split()
    revs = revs[-LAST:]
    pick = sorted({round(i * (len(revs) - 1) / (K - 1)) for i in range(K)})
    rows, fail = {}, 0
    for i in pick:
        rev = revs[i]
        with tempfile.TemporaryDirectory() as d:
            tar = subprocess.run(["git", "archive", rev], cwd=ROOT, capture_output=True, check=True).stdout
            tarfile.open(fileobj=io.BytesIO(tar)).extractall(d)
            p = subprocess.run([sys.executable, "-c", CHILD, d, json.dumps(V)], capture_output=True, text=True)
        try:
            rows[f"{i:03d} {rev[:7]}"] = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            fail += 1
    sds_all, sds_kind = [], []
    n_ch_all = n_ch_kind = 0
    for v in V:
        pairs = [r["J"][v] for r in rows.values() if r["J"][v][0] is not None and r["J"][v][1] is not None]
        if len(pairs) < 3:
            continue
        a = [x[0] for x in pairs]
        k = [x[1] for x in pairs]
        sds_all.append(sd(a))
        sds_kind.append(sd(k))
        n_ch_all += len({x >= 0.5 for x in a}) > 1
        n_ch_kind += len({x >= 0.5 for x in k}) > 1
    n_verb = len(sds_all)
    ma = sum(sds_all) / n_verb if n_verb else 0.0
    mk = sum(sds_kind) / n_verb if n_verb else 0.0
    s = {"n_snap": len(rows), "n_fail": fail, "n_verb": n_verb, "mean_sd_all": ma, "mean_sd_kind": mk,
         "ratio": mk / ma if ma else None, "n_ch_all": n_ch_all, "n_ch_kind": n_ch_kind}
    out = ROOT / "exp/experiments/results/sys_measure_excludes_claim_kinds.json"
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
