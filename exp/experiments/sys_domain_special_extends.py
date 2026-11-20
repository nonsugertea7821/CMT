"""h_domain_special_extends を確かめる: 領域をまたいで同じ形の動詞は、使われる側の動詞を extends する特化か。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.extends, [syntax.holds, syntax.domain]))。登録 #526（issue #527）。
  出どころ: #525（h_domain_by_refer、反証）で、reach の読みでも領域をまたぐ extra が 9 残った。

操作 1（静的）: #525 の reach の読みの形に、new_kind を足す。new_kind は端と同じく包含で比べる
  （W に new_kind がなければ何でもよい。あれば x の new_kind が W のものの下位）。
  cross_extra_nk = それでも残る、領域をまたぐ extra の対 (x, W)。
操作 2（一時の写し）: リポジトリの写し（.git を除く）を scratch に作り、cross_extra_nk の各 x の extends を W に書き換え、
  写しの上で tc を走らせる。対ごとに 1 回（他の対は元のまま）。体系のファイルは書き換えない。
  書き換えの条件: W が x の元の extends の下位であること（そうでなければ tc にかけず「不適」と数える）。
行（sys_domain_special_extends.json）: "word <W>"・"ref <W>"・"pair <x> < <W>"・"summary 要約"

判定（事前に決める）:
  build が失敗するか、対象 W が 0 なら外れ（状態を変えない）。
  支持: 全対象・参考で missing = 0、cross_extra_nk の対が 1 つ以上あり、そのすべてで書き換えが適し、tc が通る。
  反証: cross_extra_nk の対が 0（領域をまたぐ区別は new_kind の式で足り、extends に領域は要らない）、
        または不適か tc が落ちる対がある、または missing > 0。
開示: この手順を書く前に、#525 の extra 9 の new_kind を見ている。std.v_learn（realizable_entity）と
  exp.v_judge（information_entity）・exp.v_see（quality）、std.v_vary（quality）と exp.v_withdraw（role）は new_kind で分かれ、
  ontology.v_level（new_kind なし）と exp.v_near（tolerance）は残ると予想している。予想どおりなら、支持の根拠は 1 対だけになる。
使い方:
  python exp/experiments/sys_domain_special_extends.py
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_domain_special_extends.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
KEYS = ("holds", "pre", "post")


def main():
    os.chdir(ROOT)
    rows = {}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            import type_checker as tc
            T, O, Dm = tc.build()
    except Exception as e:
        rows["summary 要約"] = {"build_ok": 0, "error": str(e)[:300], "verdict": "外れ"}
        OUT.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(rows)
        return
    N = T.N
    res = lambda w: w if (not isinstance(w, str) or w in N) else (T.resolve(w, "signature") or w)

    def eff(x, k):
        for y in [x] + T.ancestors(x):
            if k in N.get(y, {}):
                return N[y].get(k) or []
        return []

    def atoms(x, k):
        v = eff(x, k)
        v = v if isinstance(v, list) else [v]
        out = set()
        for h in v:
            if isinstance(h, dict):
                out.add((h.get("is"), h.get("from"), h.get("to"),
                         tuple(sorted((a, json.dumps(b, sort_keys=True, ensure_ascii=False)) for a, b in h.items() if a not in ("is", "from", "to")))))
        return out

    def end(x, k):
        for y in [x] + T.ancestors(x):
            if k in N.get(y, {}):
                return N[y][k]
        return None

    def sub(a, b):
        if b is None or b == "any" or a == b:
            return True
        if isinstance(a, str) and isinstance(b, str):
            ra, rb = res(a), res(b)
            return ra in N and rb in N and T.is_a(ra, rb)
        return False

    shape = lambda x: tuple(frozenset(atoms(x, k)) for k in KEYS)
    nk = lambda x: end(x, "new_kind")
    DOM = {}
    for d, names in tc.LOCALS.items():
        for n in names:
            DOM.setdefault(f"{d}.{n}" if f"{d}.{n}" in N else n, d)
    dom = lambda x: DOM.get(x, x.split(".")[0] if "." in x else None)

    def reach(d, e):
        seen, todo = set(), [d]
        while todo:
            c = todo.pop()
            if c == e:
                return True
            if c in seen or c is None:
                continue
            seen.add(c)
            todo += list(tc.USES.get(c) or [])
        return False


    def count(W):
        G = res(N[W].get("extends"))
        sw = shape(W)
        s_name = {x for x in N if T.is_a(x, W)}
        s_exact = {x for x in N if T.is_a(x, G) and shape(x) == sw and sub(end(x, "from"), end(W, "from")) and sub(end(x, "to"), end(W, "to")) and sub(nk(x), nk(W)) and reach(dom(x), dom(W))} if isinstance(G, str) else set()
        missing, extra = sorted(s_name - s_exact), sorted(s_exact - s_name)
        return {"genus": G, "shape": [sorted(map(str, s)) for s in sw], "ends": [end(W, "from"), end(W, "to")], "n_name": len(s_name), "n_exact": len(s_exact),
                "dom": dom(W), "missing": len(missing), "extra": len(extra), "cross_extra": [x for x in extra if dom(x) != dom(W)], "same_extra": [x for x in extra if dom(x) == dom(W)], "missing_names": missing[:20], "extra_names": extra[:20]}

    def retarget(x, W):
        old = N[x].get("extends")
        ro = res(old) if isinstance(old, str) else None
        if not (isinstance(ro, str) and ro in N and T.is_a(W, ro)):
            return {"fit": 0, "old_extends": old, "tc_ok": None}
        short = x.split(".")[-1]
        files = [f for f in tc.files() if re.search(rf"^  {re.escape(short)}: \{{", Path(f).read_text(encoding="utf-8"), re.M)] if hasattr(tc, "files") else []
        if not files:
            files = [str(f) for f in ROOT.glob("**/*.yaml") if ".git" not in f.parts and "results" not in f.parts and re.search(rf"^  {re.escape(short)}: \{{", f.read_text(encoding="utf-8"), re.M)]
        files = [f for f in files if dom(x) in Path(f).stem or len(files) == 1] or files
        if len(files) != 1:
            return {"fit": 0, "old_extends": old, "tc_ok": None, "files": [str(f) for f in files]}
        rel = Path(files[0]).resolve().relative_to(ROOT)
        wname = W if dom(W) != dom(x) and W.split(".")[-1] not in tc.LOCALS.get(dom(x), []) else W.split(".")[-1]
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "repo"
            shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "results", "__pycache__"))
            f = dst / rel
            t = f.read_text(encoding="utf-8")
            t2 = re.sub(rf"^(  {re.escape(short)}: \{{.*?extends: )([^,}}]+)", lambda m: m.group(1) + wname, t, count=1, flags=re.M)
            f.write_text(t2, encoding="utf-8")
            p = subprocess.run([sys.executable, str(dst / "cscl/bootstrap/type_checker/type_checker.py")], cwd=dst, capture_output=True, text=True)
            ok = int("検査に成功" in p.stdout)
            return {"fit": 1, "old_extends": old, "new_extends": wname, "file": str(rel), "changed": int(t2 != t), "tc_ok": ok,
                    "tc_tail": (p.stdout + p.stderr).strip().splitlines()[-3:]}

    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    bad = rbad = 0
    pairs = []
    for kind, ws in (("word", targets), ("ref", refs)):
        for W in ws:
            r = count(W)
            rows[f"{kind} {W}"] = r
            if r["missing"] > 0:
                bad += kind == "word"
                rbad += kind == "ref"
            pairs += [(x, W) for x in r["cross_extra"]]
    n_fit = n_tc = 0
    for x, W in pairs:
        q = retarget(x, W)
        rows[f"pair {x} < {W}"] = q
        n_fit += q["fit"]
        n_tc += bool(q.get("tc_ok"))
    if not targets:
        verdict = "外れ"
    else:
        verdict = "支持" if bad == 0 and rbad == 0 and pairs and n_fit == len(pairs) and n_tc == len(pairs) else "反証"
    s = {"build_ok": 1, "n_targets": len(targets), "n_targets_off": bad, "targets": targets,
         "n_refs": len(refs), "n_refs_off": rbad, "n_cross_extra_nk": len(pairs), "n_fit": n_fit, "n_tc_ok": n_tc, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
