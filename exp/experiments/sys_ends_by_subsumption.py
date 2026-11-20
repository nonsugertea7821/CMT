"""h_ends_by_subsumption を確かめる: 2 相の図（holds・pre・post の原子の全体）が同じで、端（from・to）が W の端に
含まれる動詞を集めると、名前の下を取りこぼさないか（missing = 0）。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, [syntax.from, syntax.to]))。登録 #520。
  出どころ #519（h_shape_needs_ends、反証）: 端を等しさで比べたため、端を狭める下位が外れた（missing が出た）。

操作: 体系のファイルも検査器も変えない。type_checker.build() を呼び、木と節点を読むだけ（静的）。
  shape(x) = (atoms(x, holds), atoms(x, pre), atoms(x, post))（#514 と同じ）。
  end(x, k): x と上位を近い順にたどり、最初に鍵 k を持つ節点の k の値。なければ None。
  sub(a, b): b が None か "any"、または a == b、または a・b がともに節点の名で is_a(a, b) なら真。ほかは偽。
  S_sub(W) = {x : is_a(x, G) かつ shape(x) = shape(W) かつ sub(end(x, from), end(W, from)) かつ sub(end(x, to), end(W, to))}。
  対象 W・参考・数え方は #514・#519 と同じ。missing = |S_name − S_sub|、extra = |S_sub − S_name|。
行（sys_ends_by_subsumption.json）: "word <W>": {...}、"ref <W>": {...}、"summary 要約": {...}

判定（事前に決める）:
  build が失敗するか、対象 W が 0 なら外れ（状態を変えない）。
  支持: すべての対象 W で missing = 0（extra は数えるが判定に入れない。同じ端の別名は #517 の側）。
  1 つでも missing > 0 なら反証。
開示: #514・#519 の結果（外れの名、各 W の端の値）を見ている。#514 は端を見ずに missing = 0 だったので、
  支持は「端を包含で足しても取りこぼしを生まない」ことまでしか言わない。
使い方:
  python exp/experiments/sys_ends_by_subsumption.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_ends_by_subsumption.json"
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

    def count(W):
        G = res(N[W].get("extends"))
        sw = shape(W)
        s_name = {x for x in N if T.is_a(x, W)}
        s_exact = {x for x in N if T.is_a(x, G) and shape(x) == sw and sub(end(x, "from"), end(W, "from")) and sub(end(x, "to"), end(W, "to"))} if isinstance(G, str) else set()
        missing, extra = sorted(s_name - s_exact), sorted(s_exact - s_name)
        return {"genus": G, "shape": [sorted(map(str, s)) for s in sw], "ends": [end(W, "from"), end(W, "to")], "n_name": len(s_name), "n_exact": len(s_exact),
                "missing": len(missing), "extra": len(extra), "missing_names": missing[:20], "extra_names": extra[:20]}

    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    bad = 0
    for W in targets:
        r = count(W)
        rows[f"word {W}"] = r
        bad += (r["missing"] > 0)
    rbad = 0
    for W in refs:
        r = count(W)
        rows[f"ref {W}"] = r
        rbad += (r["missing"] > 0)
    if not targets:
        verdict = "外れ"
    else:
        verdict = "支持" if bad == 0 else "反証"
    s = {"build_ok": 1, "n_targets": len(targets), "n_targets_off": bad, "targets": targets,
         "n_refs": len(refs), "n_refs_off": rbad, "n_targets_extra": sum(rows[f"word {W}"]["extra"] > 0 for W in targets), "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
