"""体系そのものを数える（4）。仮説 h_anomaly_defect（A）の確かめ: 宣言した真偽の対称性を実装が壊すと、欠陥になるか。

この手順は、結果を見る前に登録した（cscl/design/claims.yaml の h_anomaly_defect と b_anomaly_defect）。

変異（cscl/bootstrap/runtime/runtime.py。真偽の読み方と歩みを実装する検査器）
  ソースの構文木の次の箇所それぞれを1つだけ変えたものを、1つの変異とする。箇所は構文木の順にすべて数える。
    比較の演算子   == ↔ !=、in ↔ not in、is ↔ is not
    真偽の定数     True ↔ False、None → False
    否定           not x → x
    論理の結合     and ↔ or
  元のソースも、変異と同じく構文木から書き直したもの（ast.unparse）を使う。

予測するもの（σ の確かめ。sys_structure.py の symmetry と同じ場合を使う）
  live    元と同じ場合を与えて、読み方の判定か、1歩の後の状態のどれかが元と違う
  breaks  σ の確かめ（読み方 900、歩み 360）に食い違いが1つでもある
  crash   読み込みか確かめの途中で例外が出るか、60秒で終わらない（比べる対象から外し、数だけ記録する）

欠陥の基準（σ と別に決める）
  fail    実行の記録の検査（runtime.py の main。exp/tests の記録を体系に照らす）が失敗するか、例外を出す
  実行の記録 exp/tests/adopt_withdraw.yaml は、真偽の対称性を調べる作業より前に書かれた（cc2617a）。閉世界だけを使う。

判定（登録した基準）。live で crash でない変異だけを比べる
  支持      breaks の変異の fail の割合が、breaks でない変異より大きく、片側 Fisher の正確検定で p < 0.05
  反証      breaks の変異の fail の割合が、breaks でない変異以下
  どちらでもない  大きいが p >= 0.05
  どちらかの組が 0 件なら、判定しない

結果ファイル sys_anomaly.json
  変異ごとに1行。列は live（0/1）、crash（0/1）、live で crash でない変異には {breaks|keeps}_fail（0/1）。
  行 "test" に p_value。

使い方:
  python exp/experiments/sys_anomaly.py           すべての変異を、1つずつ別のプロセスで調べる
  python exp/experiments/sys_anomaly.py --one K   K 番目の変異（-1 は元）だけを調べ、JSON を1行出す
"""
import ast
import contextlib
import io
import itertools
import json
import random
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "cscl/bootstrap/runtime/runtime.py"
OUT = ROOT / "exp/experiments/results"
sys.path[:0] = [str(Path(__file__).resolve().parent)]
SWAP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def sites(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            out += [(node, "cmp", i) for i, op in enumerate(node.ops) if type(op) in SWAP]
        elif isinstance(node, ast.Constant) and (node.value is None or type(node.value) is bool):
            out.append((node, "const", None))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            out.append((node, "not", None))
        elif isinstance(node, ast.BoolOp):
            out.append((node, "bool", None))
    return out


def mutant(k):
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    if k < 0:
        return ast.unparse(tree), "元"
    node, kind, i = sites(tree)[k]
    if kind == "cmp":
        node.ops[i] = SWAP[type(node.ops[i])]()
        desc = f"比較 {type(node.ops[i]).__name__}"
    elif kind == "const":
        node.value = {True: False, False: True, None: False}[node.value]
        desc = f"定数 → {node.value}"
    elif kind == "not":
        for parent in ast.walk(tree):
            for f, v in ast.iter_fields(parent):
                if v is node:
                    setattr(parent, f, node.operand)
                elif isinstance(v, list):
                    for j, x in enumerate(v):
                        if x is node:
                            v[j] = node.operand
        desc = "not を外す"
    else:
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        desc = f"結合 → {type(node.op).__name__}"
    return ast.unparse(ast.fix_missing_locations(tree)), f"{desc}（{getattr(node, 'lineno', '?')} 行）"


def load(src):
    mod = types.ModuleType("runtime_mutant")
    mod.__file__ = str(SRC)
    exec(compile(src, str(SRC), "exec"), mod.__dict__)
    return mod


def trace(rt, T):
    """σ の確かめと同じ場合で、読み方の判定と1歩の後の状態を並べる（変異が振る舞いを変えたかを見る）。"""
    U, out = rt.UNSTATED, []
    rt.WORLDS["co_closed_world"] = True
    rng = random.Random(0)
    inds = ["a", "b", "c"]
    run = {"individuals": {i: {"is": "continuant"} for i in inds}, "facts": []}
    atoms = [("exists", (i,)) for i in inds] + [("depend", p) for p in itertools.permutations(inds, 2)]
    for i in range(300):
        st = {a: rng.choice([True, False]) for a in atoms if rng.random() < 0.5}
        for w in ("closed_world", "co_closed_world", "world"):
            m = rt.Machine(T, run, "x", w)
            m.facts = dict(st)
            out.append([m.holds(r, *a) for a in atoms for r in (True, False, U)])
    run2 = {"individuals": {"a": {"is": "continuant"}, "b": {"is": "continuant"}, "k": {"is": "any"}}, "facts": []}
    rels = ("depend", "part", "refer", "after", "involve")
    space = [("exists", (i,)) for i in "abk"] + [(r, p) for r in rels for p in itertools.permutations("abk", 2)]
    for v in [v for v in T.N if "pre" in T.N[v]]:
        news = any("new" in rt.atom(f)[2] for f in T.N[v]["pre"] + T.N[v]["post"])
        b = dict(zip(["from", "to"] + (["new"] if news else []), "abk"))
        for i in range(20):
            st = {a: rng.choice([True, False]) for a in space if rng.random() < 0.4}
            for w in ("closed_world", "co_closed_world", "world"):
                m = rt.Machine(T, run2, "x", w)
                m.facts = dict(st)
                m.check_laws = lambda *a: None
                m.step(v, b, "s")
                out.append([sorted(map(str, m.facts.items())), len(m.errors)])
    del rt.WORLDS["co_closed_world"]
    return out


def one(k):
    import sys_structure as ss
    tc = ss.tc
    with contextlib.redirect_stdout(io.StringIO()):
        O2 = tc.load(tc.root_name())
        for _, name in tc.register_domains(O2):
            tc.merge_domain(name, O2)
        T2 = tc.Ontology(O2)
    src, desc = mutant(k)
    res = {"k": k, "desc": desc}
    try:
        rt = load(src)
        res["trace"] = json.dumps(trace(rt, T2), default=str)
        ss.rt = rt
        rows = ss.symmetry(T2)
        res["breaks"] = int(any(v == 0 for r in rows.values() for v in r.values()))
    except Exception as e:   # noqa: BLE001
        res["crash"] = f"{type(e).__name__}: {e}"[:200]
        print(json.dumps(res, ensure_ascii=False))
        return
    try:
        rt = load(src)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rt.main()
        res["fail"] = 0
    except SystemExit as e:
        res["fail"] = int(bool(e.code))
    except Exception:   # noqa: BLE001
        res["fail"] = 1
    print(json.dumps(res, ensure_ascii=False))


def fisher_greater(a, b, c, d):
    from math import comb
    n1, k, n = a + b, a + c, a + b + c + d
    return sum(comb(k, i) * comb(n - k, n1 - i) for i in range(a, min(n1, k) + 1)) / comb(n, n1)


def main():
    n = len(sites(ast.parse(SRC.read_text(encoding="utf-8"))))
    def run(k):
        try:
            p = subprocess.run([sys.executable, __file__, "--one", str(k)], capture_output=True, text=True, timeout=60)
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (subprocess.TimeoutExpired, IndexError, json.JSONDecodeError) as e:
            return {"k": k, "crash": type(e).__name__}
    base = run(-1)
    assert "crash" not in base and base["fail"] == 0 and base["breaks"] == 0, base
    rows = {}
    for k in range(n):
        r = run(k)
        if "crash" in r:
            rows[f"m{k:03d}"] = {"live": 1, "crash": 1, "desc": r.get("desc", ""), "why": r["crash"]}
            continue
        live = int(r["trace"] != base["trace"])
        row = {"live": live, "crash": 0, "desc": r["desc"]}
        if live:
            row[f"{'breaks' if r['breaks'] else 'keeps'}_fail"] = r["fail"]
        rows[f"m{k:03d}"] = row
        print(f"m{k:03d} {r['desc']:30} live={live} breaks={r['breaks']} fail={r['fail']}", flush=True)
    col = lambda c: [r[c] for r in rows.values() if c in r]
    b, kp = col("breaks_fail"), col("keeps_fail")
    p = fisher_greater(sum(b), len(b) - sum(b), sum(kp), len(kp) - sum(kp)) if b and kp else None
    rows["test"] = {"p_value": p if p is not None else 1.0}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_anomaly.json").write_text(json.dumps({"_source": "exp/experiments/sys_anomaly.py", "_commit": commit,
                                                      "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"変異 {n}、live {sum(col('live'))}、crash {sum(col('crash'))}")
    print(f"breaks: n={len(b)} fail={sum(b)}  keeps: n={len(kp)} fail={sum(kp)}  p={p}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--one":
        one(int(sys.argv[2]))
    else:
        main()
