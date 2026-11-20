"""仮説 h_named_mod_is_spelling（修飾の意味は識別子に依存しない: v_not_depend(syntax.mod, syntax.identifier)）を、
体系の全体で確かめる。結果を見る前に、この説明と手順を登録した（#422）。

問い: 名前を付けた修飾語を名前で使う書き方を、すべて中身をその場に書く書き方に変えても、
  意味（検査器が作る文 syntax_facts と、named_mod 以外の誤り）は変わらないか。
  変わるのが「名前を書いた」という文（r_written）だけなら、名前は綴りで、修飾の意味に入っていない。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  対象のファイル: cscl.yaml の範囲にある、domain と nodes を持つ yaml のすべて。
  D0: 写しをそのまま。
  D1: 各ファイルで、行の中の「mod: 名前}」を探す。名前が同じファイルの nodes にあり、その節点が of を持つ
      （名前を付けた修飾語である）とき、その節点の of・with・neg・at を流れの形の yaml にして、その場に書き換える。
      領域の印の付いた名前（例 syntax.x）と、mod を並べた形は変えない（領域をまたぐと、中身の語の解き方が変わるため）。
  D0 と D1 で tc.build() を 1 回ずつ走らせ、誤りと syntax_facts を読む。
数える量:
  n_inlined         書き換えた箇所の数
  n_names           書き換えた修飾語の名前の数
  py_D0, py_D1      法則 named_mod の誤りの数（D1 では、書き換えた箇所の数だけ出る見込み。判定には使わない）
  other_D0, other_D1  それ以外の誤りの数
  other_same        named_mod 以外の誤りが、文の集まりとして D0 と D1 で等しければ 1
  n_diff_written    D0 と D1 で違う文のうち、関係が r_written のものの数
  n_diff_other      D0 と D1 で違う文のうち、それ以外の数
判定（事前に決める）:
  n_inlined ≥ 1 かつ other_same = 1 かつ n_diff_other = 0 なら支持。
  n_inlined ≥ 1 かつ（other_same = 0 または n_diff_other ≥ 1）なら反証。
  n_inlined = 0 は手順の誤りとして開示し、状態を変えない。
行（sys_named_mod_is_spelling.json）:
  "summary 要約": 上の量
  "texts": 書き換えた名前、named_mod 以外で違う誤り（最大 10）、r_written 以外で違う文（最大 10）

使い方:
  python exp/experiments/sys_named_mod_is_spelling.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_named_mod_is_spelling.json"
MOD = re.compile(r"mod: ([a-z_][a-z0-9_]*)\}")

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T, O, _ = tc.build()
        facts = sorted({json.dumps([r, [str(a) for a in xs]], ensure_ascii=False) for r, xs in T.syntax_facts()})
        crash = ""
    except Exception as e:
        facts, crash = [], repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
py = [e for e in errs if "named_mod" in e]
other = sorted(e for e in errs if e not in py)
print(json.dumps({"py": len(py), "other": other, "facts": facts}, ensure_ascii=False))
'''


def files():
    out = sorted({p.resolve() for g in ("cscl/**/*.yaml", "exp/src/*.yaml") for p in ROOT.glob(g)})
    keep = []
    for p in out:
        y = yaml.safe_load(p.read_text())
        if isinstance(y, dict) and "domain" in y and "nodes" in y:
            keep.append(p)
    return keep


def inline(text):
    nodes = (yaml.safe_load(text) or {}).get("nodes") or {}
    count, names = 0, set()

    def rep(m):
        nonlocal count
        name = m.group(1)
        n = nodes.get(name)
        if not isinstance(n, dict) or "of" not in n:
            return m.group(0)
        body = {k: n[k] for k in ("of", "with", "neg", "at") if k in n}
        flow = yaml.safe_dump(body, default_flow_style=True, allow_unicode=True, sort_keys=False, width=10**6).strip()
        count += 1
        names.add(name)
        return f"mod: {flow}}}"

    out = []
    in_nodes = False
    for line in text.splitlines(keepends=True):
        if re.match(r"^[a-z_]+:", line):
            in_nodes = line.startswith("nodes:")
        out.append(MOD.sub(rep, line) if in_nodes else line)
    return "".join(out), count, names


def run(edit):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        count, names = 0, set()
        if edit:
            for p in files():
                q = d / p.relative_to(ROOT)
                s, c, ns = inline(q.read_text())
                if c:
                    q.write_text(s)
                    count += c
                    names |= {f"{p.name}:{n}" for n in ns}
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        res = json.loads(r.stdout.strip().splitlines()[-1])
        res["count"], res["names"] = count, sorted(names)
        return res


def main():
    R0, R1 = run(False), run(True)
    f0, f1 = set(R0["facts"]), set(R1["facts"])
    diff = f0 ^ f1
    written = [x for x in diff if json.loads(x)[0] == "r_written"]
    other = sorted(x for x in diff if json.loads(x)[0] != "r_written")
    summary = {"n_inlined": R1["count"], "n_names": len(R1["names"]),
               "py_D0": R0["py"], "py_D1": R1["py"],
               "other_D0": len(R0["other"]), "other_D1": len(R1["other"]),
               "other_same": int(R0["other"] == R1["other"]),
               "n_diff_written": len(written), "n_diff_other": len(other)}
    texts = {"names": R1["names"],
             "other_errors_diff": sorted(set(R0["other"]) ^ set(R1["other"]))[:10],
             "facts_diff_other": other[:10]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
