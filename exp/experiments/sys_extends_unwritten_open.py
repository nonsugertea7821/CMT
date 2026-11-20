"""h_extends_unwritten_open を確かめる: 書いていない欄を比べず、極小を P の鎖で集めた端と mod で選べば、自分の欄だけから extends は導ける。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.extends, [syntax.mod, syntax.from, syntax.to]))。登録 #571（issue #573）。
  出どころ: #570（h_verbs_state_own_ends、反証、59/70。外れは受け継いだ new_kind と mod を子が書いていないこと）、
  #566（h_extends_own_fields_by_compat、反証、3/70。自分の欄どうしの適合で極小を選ぶと、書いた欄の少ない動詞に集まる）。

操作: #566 と同じ写し・導いた親 P の鎖・不動点（最大 20 巡）。違いは次の 2 つ:
  候補 cand(x, W): 次のすべて。
    - holds・pre・post の各欄 k: x が k を書いていれば、x の書いた原子の集合 = W の P の鎖で集めた k の原子の集合。
    - from・to・new_kind の各端 e: x が e を書いていれば、sub(x の書いた e, W の P の鎖で集めた e)。
    - x が mod を書いていれば、mods(W) ⊆ mods(x)。書いていなければ問わない。
  極小: below(V, W) = 各端で subo(V の P の鎖の端, W の P の鎖の端) かつ mods(W) ⊆ mods(V)。
    subo(a, b) は a が None なら真、そうでなければ sub(a, b)。
    C = {W ≠ x : cand(x, W)}、M = {m ∈ C : C に below(V, m) かつ not below(m, V) の V がない}。
    M が 1 つならそれ。2 つ以上なら U = {W ∈ C − M : すべての m ∈ M で below(m, W)} の中で、
    ほかのすべての V ∈ U に below(W, V) となる W がただ 1 つならそれ。それ以外は None。
行（sys_extends_unwritten_open.json）: #566 と同じ形。

判定（事前に決める）:
  対照の tc が落ちるか、あての文字列が見つからないか、あてた写しの tc が落ちれば外れ（状態を変えない）。
  支持: P が止まり（fixed = 1）、最後の巡で n_sub_match = n_sub かつ n_top_none = n_top。
  それ以外は反証。
開示: subo で None を包含とするので、0 巡目に端を書かない動詞は below で下に来やすい（#566 の集まりと同じ向き）。
  走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_extends_unwritten_open.py
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
    P = {}

    def chain(x, written=False):
        if written:
            return [x] + T.ancestors(x)
        out = [x]
        while P.get(out[-1]) and P[out[-1]] not in out:
            out.append(P[out[-1]])
        return out

    def eff(x, k, written=False):
        for y in chain(x, written):
            if k in N.get(y, {}):
                return N[y].get(k) or []
        return []

    def atoms(x, k, written=False):
        v = eff(x, k, written)
        v = v if isinstance(v, list) else [v]
        out = set()
        for h in v:
            if isinstance(h, dict):
                out.add((h.get("is"), h.get("from"), h.get("to"),
                         tuple(sorted((a, json.dumps(b, sort_keys=True, ensure_ascii=False)) for a, b in h.items() if a not in ("is", "from", "to")))))
        return out

    def end(x, k):
        for y in chain(x):
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

    def mods(x):
        out = set()
        for y in chain(x):
            m = N.get(y, {}).get("mod")
            for h in (m if isinstance(m, list) else [m] if m else []):
                out.add(json.dumps(h, sort_keys=True, ensure_ascii=False))
        return frozenset(out)

    ENDS = ("from", "to", "new_kind")

    def own_atoms(x, k):
        v = N[x].get(k) or []
        v = v if isinstance(v, list) else [v]
        out = set()
        for h in v:
            if isinstance(h, dict):
                out.add((h.get("is"), h.get("from"), h.get("to"),
                         tuple(sorted((a, json.dumps(b, sort_keys=True, ensure_ascii=False)) for a, b in h.items() if a not in ("is", "from", "to")))))
        return out

    def cand(x, W):
        for k in KEYS:
            if k in N[x] and own_atoms(x, k) != atoms(W, k):
                return False
        for e in ENDS:
            if e in N[x] and not sub(N[x][e], end(W, e)):
                return False
        return "mod" not in N[x] or mods(W) <= mods(x)

    subo = lambda a, b: True if a is None else sub(a, b)
    below = lambda V, W: all(subo(end(V, e), end(W, e)) for e in ENDS) and mods(W) <= mods(V)

    verbs = sorted(x for x in N if x != top_o and T.is_a(x, top_o) and any(atoms(x, k, True) for k in KEYS))
    vs = set(verbs)

    def derive():
        out = {}
        for x in verbs:
            C = [W for W in verbs if W != x and cand(x, W)]
            M = [m for m in C if not any(below(V, m) and not below(m, V) for V in C if V != m)]
            if len(M) == 1:
                D = M
            elif len(M) > 1:
                U = [W for W in C if W not in M and all(below(m, W) for m in M)]
                D = [W for W in U if all(below(W, V) for V in U)]
            else:
                D = []
            out[x] = (D[0] if len(D) == 1 else None, len(C), D[:10])
        return out

    E = {x: res(N[x].get("extends")) for x in verbs}

    def count(R):
        n_sub = n_sub_match = n_top = n_top_none = 0
        bad = {}
        for x in verbs:
            d = R[x][0]
            if E[x] in vs:
                n_sub += 1
                ok = d == E[x]
                n_sub_match += ok
            else:
                n_top += 1
                ok = d is None
                n_top_none += ok
            if not ok:
                bad[x] = d
        return n_sub, n_sub_match, n_top, n_top_none, bad

    R = derive()
    _, m0, _, t0, _ = count(R)
    rounds = 1
    fixed = 0
    while rounds < 20:
        newP = {x: R[x][0] for x in verbs}
        if newP == P:
            fixed = 1
            break
        P.clear()
        P.update(newP)
        R = derive()
        rounds += 1
    n_sub, n_sub_match, n_top, n_top_none, bad = count(R)
    rows = {f"verb {x}": {"written": E[x], "derived": d, "n_cand": R[x][1], "minimal": R[x][2]} for x, d in bad.items()}
    s = {"n_verbs": len(verbs), "n_sub": n_sub, "n_sub_match": n_sub_match, "n_top": n_top, "n_top_none": n_top_none,
         "round0_sub_match": m0, "round0_top_none": t0, "rounds": rounds, "fixed": fixed}
    print(json.dumps({"rows": rows, "s": s}, ensure_ascii=False))


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_extends_unwritten_open.json"
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
            p = subprocess.run([sys.executable, str(dst / "exp/experiments/sys_extends_unwritten_open.py"), "--inner"], cwd=dst, capture_output=True, text=True)
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
