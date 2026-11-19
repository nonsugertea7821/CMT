"""h_collect_by_formula を確かめる: 型検査器が "syntax.v_collect" と名前で読む区別を、限定（mod）の式で読めるか。

仮説（claims.yaml）: v_refer(syntax.mod, syntax.v_collect)。
  登録（7a60bc2）の読み: #301（h_renaming_invariant）の反証から。型検査器は "syntax.v_collect" と層の名を付けた文字列で
  v_collect を読み、付け替えで集まりが消えた。式で区別する道を仮説にした。

式 F（動詞 v が集める動詞であること）:
  v は動詞で、v の端 from の種類 K（か K の上位）が、限定 {of: [u, from]}（with なし、否定なし）を持ち、v が u の下にある。
  （syntax で kind_collection は mod {of: [v_collect, from]} と書かれ、v_collect の from は kind_collection。
   種類が「その動詞の始点であること」で定義され、動詞がその種類を始点に取る、という自己参照の形。）

操作: 体系のファイルも検査器も変えない。リポジトリを一時ディレクトリに写し（.git を除く）、写しの中で:
  patch:  写しの type_checker.py で、名前で読む 2 か所を式 F に替える。
          L372 の `T.resolve(f.get("is"), dom) == "syntax.v_collect"` → `_is_coll(T, T.resolve(f.get("is"), dom))`
          L377 で動詞を T.COLLV に残し、L984 の `add("of", t, "syntax.v_collect")` → その動詞。
  どの組でも、写しの type_checker.py の末尾に _is_coll を足す（patch でない組では、静的に数えるためだけに使う）。
  rename: 写しの yaml（cscl と exp/src の下）で、語 v_collect（単語境界）を v_gather に付け替える。.py は変えない。
走らせる組（4 回、別のプロセス）: orig、patch、rename、patch_rename。
数える: 回ごとに n_err（tc.errors の数）、n_coll（T.COLL の数）。
  静的（orig の回で）: S_name = {v : v は動詞で is_a(v, syntax.v_collect)}、S_form = {v : 式 F}。
    n_name、n_form、missing = |S_name − S_form|、extra = |S_form − S_name|。
仮説からの見込み（事前に決める）:
  orig の n_err = 0、n_coll > 0。
  missing = extra = 0。
  patch と patch_rename は、n_err = 0 で n_coll が orig と同じ。
  rename（対照）は、#301 のとおり n_coll が減るか n_err が増える（記録だけ。判定には使わない）。
判定（事前に決める）:
  orig が n_err > 0 か n_coll = 0 なら、手順が壊れているので外れとし、状態を変えない。
  静的が一致し、patch と patch_rename が見込みどおりなら支持。
  静的が一致しないか、patch が見込みどおりでないなら反証（式 F は v_collect の区別にならない）。
  静的と patch は見込みどおりだが、patch_rename が外れれば mixed（式は区別になるが、ほかの名前の読みが付け替えを妨げる）。
開示（結果を見る前に分かっていること）:
  - 式 F は、syntax の kind_collection の書き方を見て作った。ほかの動詞が同じ形を持つかは見ていない。
  - 付け替えは、yaml の中の v_collect の文字列をすべて替える（法則の of: v_collect の参照も替わる）。

行（sys_collect_by_formula.json）: "static": {...}, "case <組>": {...}, "summary 要約": {...}
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_collect_by_formula.json"
TCP = "cscl/bootstrap/type_checker/type_checker.py"
HELPER = '''

def _is_coll(T, v):
    if v not in T.N or not T.is_verb(v):
        return False
    K = T.N[v].get("from")
    K = (T.resolve(K, "signature") or K) if isinstance(K, str) and K not in T.N else K
    if not isinstance(K, str) or K not in T.N:
        return False
    for y in [K] + T.ancestors(K):
        ms = T.N[y].get("mod") or []
        for m in (ms if isinstance(ms, list) else [ms]):
            if isinstance(m, dict) and isinstance(m.get("of"), list) and len(m["of"]) == 2 and m["of"][1] == "from" \\
                    and "with" not in m and not m.get("neg"):
                u = m["of"][0]
                u = u if u in T.N else (T.resolve(u, "signature") or u)
                if u in T.N and T.is_a(v, u):
                    return True
    return False
'''
A1 = 'T.resolve(f.get("is"), dom) == "syntax.v_collect"'
B1 = '_is_coll(T, T.resolve(f.get("is"), dom))'
A2 = '                    T.COLL[f["from"]] = k'
B2 = '                    T.COLL[f["from"]] = k\n                    T.__dict__.setdefault("COLLV", {})[f["from"]] = T.resolve(f.get("is"), dom)'
A3 = 'add("of", t, "syntax.v_collect")'
B3 = 'add("of", t, getattr(self, "COLLV", {}).get(c, "syntax.v_collect"))'
PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T, O, Dm = tc.build()
        ok = 1
    except Exception as e:
        ok, T = 0, None
r = {"built": ok, "n_err": len(tc.errors), "n_coll": len(getattr(T, "COLL", {}) or {}) if T else -1, "errs": [str(x)[:160] for x in tc.errors[:5]]}
if T and STATIC:
    vs = [v for v in T.N if T.is_verb(v)]
    s_name = {v for v in vs if T.is_a(v, "syntax.v_collect")}
    s_form = {v for v in vs if tc._is_coll(T, v)}
    r["static"] = {"n_name": len(s_name), "n_form": len(s_form), "missing": sorted(s_name - s_form), "extra": sorted(s_form - s_name)}
print(json.dumps(r, ensure_ascii=False))
'''


def prepare(work, src_tc, patch, rename, base_yaml):
    t = src_tc
    if patch:
        for a, b in ((A1, B1), (A2, B2), (A3, B3)):
            assert t.count(a) == 1, a
            t = t.replace(a, b)
    t = t + HELPER
    (work / TCP).write_text(t, encoding="utf-8")
    for p, s in base_yaml.items():
        (work / p).write_text(re.sub(r"\bv_collect\b", "v_gather", s) if rename else s, encoding="utf-8")


def main():
    src_tc = (ROOT / TCP).read_text(encoding="utf-8")
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        base_yaml = {str(p.relative_to(work)): p.read_text(encoding="utf-8")
                     for p in list((work / "cscl").rglob("*.yaml")) + list((work / "exp/src").rglob("*.yaml"))}
        for name, patch, rename in (("orig", False, False), ("patch", True, False), ("rename", False, True), ("patch_rename", True, True)):
            prepare(work, src_tc, patch, rename, base_yaml)
            code = PROBE.replace("STATIC", "True" if name == "orig" else "False")
            p = subprocess.run([sys.executable, "-c", code], cwd=work, capture_output=True, text=True)
            try:
                r = json.loads(p.stdout.strip().split("\n")[-1])
            except (ValueError, IndexError):
                r = {"built": 0, "n_err": -1, "n_coll": -1, "fail": p.stderr.strip()[-300:]}
            if "static" in r:
                rows["static"] = r.pop("static")
            rows[f"case {name}"] = r
            print(name, json.dumps(r, ensure_ascii=False), flush=True)
    g = lambda n: rows[f"case {n}"]
    st = rows.get("static", {})
    o = g("orig")
    s = {"base_ok": 1 if o["n_err"] == 0 and o["n_coll"] > 0 else 0,
         "n_coll_orig": o["n_coll"],
         "static_match": 1 if st and not st["missing"] and not st["extra"] else 0,
         "patch_same": 1 if g("patch")["n_err"] == 0 and g("patch")["n_coll"] == o["n_coll"] else 0,
         "patch_rename_same": 1 if g("patch_rename")["n_err"] == 0 and g("patch_rename")["n_coll"] == o["n_coll"] else 0,
         "rename_lost": 1 if g("rename")["n_coll"] < o["n_coll"] or g("rename")["n_err"] > 0 else 0}
    s["verdict_support"] = 1 if s["base_ok"] and s["static_match"] and s["patch_same"] and s["patch_rename_same"] else 0
    s["verdict_refute"] = 1 if s["base_ok"] and not (s["static_match"] and s["patch_same"]) else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
