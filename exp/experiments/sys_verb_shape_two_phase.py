"""h_verb_shape_two_phase を確かめる: pre・post を持つ動詞（変位）も、2 相の図（holds・pre・post の原子の全体）の
一致で、名前の区別と同じ集合を読めるか。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, [syntax.holds, syntax.pre, syntax.post]))。登録 #505。
  出どころ #503（h_refer_by_exact_holds、支持）: v_refer の下は holds の原子の全体の一致で読めた（19 = 19）。

操作: 体系のファイルも検査器も変えない。type_checker.build() を呼び、木と節点を読むだけ（静的）。
  eff(x, k): x と x の上位を近い順にたどり、最初に鍵 k を持つ節点の k の値。なければ空。k ごとに別々にたどる。
  atoms(x, k): eff(x, k) の各要素（dict）を、(is, from, to) とほかの鍵の (鍵, 値) の組の tuple にした集合。
  shape(x) = (atoms(x, holds), atoms(x, pre), atoms(x, post))。
  対象 W: 節点の定義に pre か post を直に持つ節点すべて（変位の根）。
  各 W について G = W の extends、S_name = {x : is_a(x, W)}、S_exact = {x : is_a(x, G) かつ shape(x) = shape(W)}。
  数える: n_name、n_exact、missing、extra と名（先頭 20）。
  参考（判定の外）: holds だけを直に持つ節点（pre・post を直に持たない）についても同じく数える。
行（sys_verb_shape_two_phase.json）: "word <W>": {...}、"ref <W>": {...}、"summary 要約": {...}

判定（事前に決める）:
  build が失敗するか、対象 W が 0 なら外れ（状態を変えない）。
  支持: すべての W で missing = 0 かつ extra = 0。
  1 つでも外れれば反証。
開示: どの節点が pre・post を持つかは、この手順を書く前に見ていない。#503 の結果（v_refer の 19）は見ている。
使い方:
  python exp/experiments/sys_verb_shape_two_phase.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_verb_shape_two_phase.json"
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

    shape = lambda x: tuple(frozenset(atoms(x, k)) for k in KEYS)

    def count(W):
        G = res(N[W].get("extends"))
        sw = shape(W)
        s_name = {x for x in N if T.is_a(x, W)}
        s_exact = {x for x in N if G and T.is_a(x, G) and shape(x) == sw} if isinstance(G, str) else set()
        missing, extra = sorted(s_name - s_exact), sorted(s_exact - s_name)
        return {"genus": G, "shape": [sorted(map(str, s)) for s in sw], "n_name": len(s_name), "n_exact": len(s_exact),
                "missing": len(missing), "extra": len(extra), "missing_names": missing[:20], "extra_names": extra[:20]}

    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    bad = 0
    for W in targets:
        r = count(W)
        rows[f"word {W}"] = r
        bad += (r["missing"] > 0 or r["extra"] > 0)
    rbad = 0
    for W in refs:
        r = count(W)
        rows[f"ref {W}"] = r
        rbad += (r["missing"] > 0 or r["extra"] > 0)
    if not targets:
        verdict = "外れ"
    else:
        verdict = "支持" if bad == 0 else "反証"
    s = {"build_ok": 1, "n_targets": len(targets), "n_targets_off": bad, "targets": targets,
         "n_refs": len(refs), "n_refs_off": rbad, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
