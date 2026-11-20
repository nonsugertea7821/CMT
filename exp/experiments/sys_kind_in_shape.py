"""h_kind_in_shape を確かめる: 形での識別には new_kind が要る（領域の条件なしで）。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, [syntax.holds, syntax.new_kind]))。登録 #530（issue #531）。
  出どころ: #529 で、new_kind を包含で比べると、#525 の領域をまたぐ extra 9 のうち 8 が消えた。

操作（静的。体系のファイルも検査器も変えない）:
  S_k(W) = { x | x is_a genus(W), shape(x) = shape(W)（holds・pre・post）, 端 from・to と new_kind が W のものに包含される }。
  領域の条件（#525 の reach）は入れない。S_name(W) = { x | x is_a W }。
  missing = S_name - S_k、extra = S_k - S_name。対象は pre/post を持つ動詞、参考は holds だけを持つ動詞（#522 と同じ）。
行（sys_kind_in_shape.json）: "word <W>"・"ref <W>"・"summary 要約"

判定（事前に決める）:
  build が失敗するか、対象 W が 0 なら外れ（状態を変えない）。
  支持: 全対象・参考で missing = 0、かつ extra の対 (x, W) がすべて次の 3 つのうちにある:
    (exp.v_near, ontology.v_level), (exp.v_ground, exp.v_rely), (exp.v_scope, exp.v_rely)。
  1 つでも外れれば反証。
開示: #529 の結果（reach の条件つき）で、残る extra がこの 3 対であることを知っている。
  この実験で新しく問うのは、領域の条件を外しても extra が増えないか（領域は new_kind の式で足りるか）。
使い方:
  python exp/experiments/sys_kind_in_shape.py
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
OUT = ROOT / "exp/experiments/results/sys_kind_in_shape.json"
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
        s_exact = {x for x in N if T.is_a(x, G) and shape(x) == sw and sub(end(x, "from"), end(W, "from")) and sub(end(x, "to"), end(W, "to")) and sub(nk(x), nk(W))} if isinstance(G, str) else set()
        missing, extra = sorted(s_name - s_exact), sorted(s_exact - s_name)
        return {"genus": G, "shape": [sorted(map(str, s)) for s in sw], "ends": [end(W, "from"), end(W, "to")], "n_name": len(s_name), "n_exact": len(s_exact),
                "dom": dom(W), "missing": len(missing), "extra": len(extra), "cross_extra": [x for x in extra if dom(x) != dom(W)], "same_extra": [x for x in extra if dom(x) == dom(W)], "missing_names": missing[:20], "extra_names": extra}

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
            pairs += [(x, W) for x in r["extra_names"]]
    allowed = {("exp.v_near", "ontology.v_level"), ("exp.v_ground", "exp.v_rely"), ("exp.v_scope", "exp.v_rely")}
    outside = [f"{x} < {W}" for x, W in pairs if (x, W) not in allowed]
    if not targets:
        verdict = "外れ"
    else:
        verdict = "支持" if bad == 0 and rbad == 0 and not outside else "反証"
    s = {"build_ok": 1, "n_targets": len(targets), "n_targets_off": bad, "targets": targets,
         "n_refs": len(refs), "n_refs_off": rbad, "n_extra": len(pairs), "n_extra_outside": len(outside),
         "n_w_with_extra": len({W for _, W in pairs}), "outside": outside, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
