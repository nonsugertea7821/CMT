"""h_extends_meet_of_minimal を確かめる: 最小の候補が複数あれば、それらに共通する最も下の候補を親として導けば、extends は式から導ける。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.extends, [syntax.from, syntax.mod]))。登録 #554（issue #555）。
  出どころ: #553（h_extends_derived_with_mod、反証、70 のうち 69）。残った exp.teacher_both は、
  式の包含で teacher_recite と teacher_examples の二つの下にあり、比べられない二つの最小の候補を持つ。

操作: #553 と同じ写しと同じ below（形・端・new_kind・mod）。違いは D(x) の選び方だけ:
  M(x) = C(x) のうち、C(x) の他の候補 V で below(V, m) かつ not below(m, V) となるものがない m（極小の候補）。
  |M| = 1 なら D = その 1 つ。
  |M| > 1 なら U = { W ∈ C(x) \ M | すべての m ∈ M で below(m, W) }、U の中で他のすべての U の要素の下にあるものがただ 1 つならそれを D、なければ None。
  |M| = 0 なら None。
  （#549・#553 の D は「C の他のすべての候補の下にあるもの」で、|M| = 1 かつ M の要素が C 全体の下にあるときと同じ。）
行（sys_extends_derived_meet.json）: "control"・"apply"・"verb <x>"（D と E が食い違う x だけ）・"summary 要約"（n_multi_min: |M| > 1 の x の数を足す）

判定（事前に決める）:
  対照の tc が落ちるか、あての文字列が見つからないか、あてた写しの tc が落ちれば外れ（状態を変えない）。
  支持: n_sub_match = n_sub かつ n_top_none = n_top。
  1 つでも食い違えば反証。
開示: 登録の本文で「70 すべてで揃う」と見込んだのは teacher_both の候補を読んでからで、事前の見込みは結果から独立ではない。
  この規則が他の 69 の導出を変えるか（変えて食い違いを生むか）は、走らせる前に計算していない。
使い方:
  python exp/experiments/sys_extends_derived_meet.py
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
KEYS = ("holds", "pre", "post")


def inner():
    root = Path.cwd()
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    top_o = T.top_o
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
    sig = lambda x: (end(x, "from"), end(x, "to"), end(x, "new_kind"))
    def mods(x):
        out = set()
        for y in [x] + T.ancestors(x):
            m = N.get(y, {}).get("mod")
            for h in (m if isinstance(m, list) else [m] if m else []):
                out.add(json.dumps(h, sort_keys=True, ensure_ascii=False))
        return frozenset(out)

    below = lambda x, W: all(sub(a, b) for a, b in zip(sig(x), sig(W))) and mods(W) <= mods(x)
    verbs = sorted(x for x in N if x != top_o and T.is_a(x, top_o) and any(atoms(x, k) for k in KEYS))
    vs = set(verbs)
    rows = {}
    n_sub = n_sub_match = n_top = n_top_none = n_multi_min = 0
    for x in verbs:
        sx = shape(x)
        C = [W for W in verbs if W != x and shape(W) == sx and below(x, W)]
        M = [m for m in C if not any(below(V, m) and not below(m, V) for V in C if V != m)]
        if len(M) == 1:
            D = M
        elif len(M) > 1:
            n_multi_min += 1
            U = [W for W in C if W not in M and all(below(m, W) for m in M)]
            D = [W for W in U if all(below(W, V) for V in U)]
        else:
            D = []
        d = D[0] if len(D) == 1 else None
        e = res(N[x].get("extends"))
        if e in vs:
            n_sub += 1
            ok = d == e
            n_sub_match += ok
        else:
            n_top += 1
            ok = d is None
            n_top_none += ok
        if not ok:
            rows[f"verb {x}"] = {"written": e, "derived": d, "n_cand": len(C), "minimal": D[:10]}
    s = {"n_verbs": len(verbs), "n_sub": n_sub, "n_sub_match": n_sub_match, "n_top": n_top, "n_top_none": n_top_none, "n_multi_min": n_multi_min}
    print(json.dumps({"rows": rows, "s": s}, ensure_ascii=False))


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_extends_derived_meet.json"
    sys.path[:0] = [str(root / "exp/experiments")]
    from sys_checker_find_by_ancestry import copy, tc_ok, patch_checker, move_m1, line_of
    from sys_extends_by_shape_closed import move_m2

    def fix_near(dst):
        p = dst / "exp/src/exp.yaml"
        t = p.read_text(encoding="utf-8")
        m = line_of(t, "v_near")
        if not m or "extends: occurrent" not in m.group(0):
            return 0
        p.write_text(t.replace(m.group(0), m.group(0).replace("extends: occurrent", "extends: v_level", 1), 1), encoding="utf-8")
        return 1

    rows = {}
    found = 1
    tmp, dst = copy()
    try:
        found &= patch_checker(dst)
        ok, tail = tc_ok(dst)
        rows["control"] = {"tc_ok": ok, "tail": tail}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tmp, dst = copy()
    s = {}
    try:
        f = patch_checker(dst) & move_m1(dst) & move_m2(dst) & fix_near(dst)
        found &= f
        a_ok, a_tail = tc_ok(dst) if f else (0, [])
        rows["apply"] = {"found": f, "tc_ok": a_ok, "tail": a_tail}
        if a_ok:
            p = subprocess.run([sys.executable, str(dst / "exp/experiments/sys_extends_derived_meet.py"), "--inner"], cwd=dst, capture_output=True, text=True)
            r = json.loads(p.stdout.strip().splitlines()[-1])
            rows.update(r["rows"])
            s = r["s"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    c_ok = rows["control"]["tc_ok"]
    a_ok = rows["apply"]["tc_ok"]
    if not (c_ok and found and a_ok):
        verdict = "外れ"
    else:
        verdict = "支持" if s["n_sub_match"] == s["n_sub"] and s["n_top_none"] == s["n_top"] else "反証"
    s = {"control_tc_ok": c_ok, "found": found, "apply_tc_ok": a_ok, **s, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    out.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    inner() if "--inner" in sys.argv else main()
