"""h_extends_derived を確かめる: 動詞の extends は書かずに、形・端・new_kind の式の包含から導ける。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.extends, type_checker))。登録 #547（issue #548）。
  出どころ: #546（h_extends_by_shape_closed、支持）。anc + M1 + M2 の写しで、式による包含と名の is_a が揃った（outside 0）。

操作（一時の写し。体系のファイルと検査器は書き換えない）:
  写しに 4 つをあてる: #540 の patch_checker、move_m1、#546 の move_m2、
  V: exp.yaml の v_near の行の extends: occurrent を extends: v_level にする（#529 で tc が通った書き足し）。
  写しの tc が通れば、写しの上でこのスクリプトを --inner で走らせ、次を数える（読みは #533 の shape・end・sub と同じ式）:
    動詞 = occurrent の子孫で、holds・pre・post のどれかを（祖先からでも）持つもの。
    C(x) = { W 動詞, W ≠ x | shape(W) = shape(x)、端 from・to と new_kind が x のものを包含する（sub(x の値, W の値)）}。
    導いた上位 D(x) = C(x) のうち、他のすべての候補 V について端と new_kind が V のものに包含されるもの（ただ 1 つのとき）。なければ None。
    書いた上位 E(x) = x の extends（解決した名）。
  数: n_verbs、n_sub（E(x) が動詞の x）、n_sub_match（D(x) = E(x)）、n_top（E(x) = occurrent）、n_top_none（D(x) = None）。
行（sys_extends_derived.json）: "control"・"apply"・"verb <x>"（D と E が食い違う x だけ）・"summary 要約"

判定（事前に決める）:
  対照（patch_checker だけ）の tc が落ちるか、あての文字列が見つからないか、あてた写しの tc が落ちれば外れ（状態を変えない）。
  支持: n_sub_match = n_sub かつ n_top_none = n_top。
  1 つでも食い違えば反証。
開示: #546 の読みは genus の中で比べた。ここでは genus の条件を外して全動詞を候補にする。
  同じ形・同じ端の動詞の対（互いに包含し合う）は D がただ 1 つに決まらず、食い違いに数える。その数の見込みは書く前に計算していない。
使い方:
  python exp/experiments/sys_extends_derived.py
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
    below = lambda x, W: all(sub(a, b) for a, b in zip(sig(x), sig(W)))
    verbs = sorted(x for x in N if x != top_o and T.is_a(x, top_o) and any(atoms(x, k) for k in KEYS))
    vs = set(verbs)
    rows = {}
    n_sub = n_sub_match = n_top = n_top_none = 0
    for x in verbs:
        sx = shape(x)
        C = [W for W in verbs if W != x and shape(W) == sx and below(x, W)]
        D = [W for W in C if all(below(W, V) for V in C)]
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
    s = {"n_verbs": len(verbs), "n_sub": n_sub, "n_sub_match": n_sub_match, "n_top": n_top, "n_top_none": n_top_none}
    print(json.dumps({"rows": rows, "s": s}, ensure_ascii=False))


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_extends_derived.json"
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
            p = subprocess.run([sys.executable, str(dst / "exp/experiments/sys_extends_derived.py"), "--inner"], cwd=dst, capture_output=True, text=True)
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
