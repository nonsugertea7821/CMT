"""h_domain_by_refer を確かめる: 同じ図（holds・pre・post）・包含する端の動詞の対は、refer する領域で区別されるか。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, [syntax.holds, syntax.domain]))。登録 #523。
  出どころ: 利用者の指摘「同じなのではなく領域で区別されている。領域は v_refer される対象では」。
  #522（h_ends_by_subsumption、支持）で、図と端だけでは extra が対象 16 のうち 6 に残った。

操作: 体系のファイルも検査器も変えない（静的）。動詞が属す領域を「領域への refer」として式に書いたときを、
  検査器の表 LOCALS（領域 → その領域のファイルが宣言した節点）と USES（領域 → 使う領域）で模す。
  dom(x): LOCALS で x を宣言した領域。
  reach(d, e): d = e か、USES をたどって d から e に届く。
  #522 の S_sub(W) に、条件 reach(dom(x), dom(W)) を足す（下位は、上位の領域を使う領域にあってよい）。
  参考（判定の外）: 条件を dom(x) = dom(W)（等しさ）にした読みも数える。
  cross_extra(W) = extra のうち dom(x) ≠ dom(W) のもの。same_extra(W) = extra のうち dom(x) = dom(W) のもの。
行（sys_domain_by_refer.json）: "word <W>"・"ref <W>"・"eq <W>"（等しさの読み）・"summary 要約"

判定（事前に決める）:
  build が失敗するか、対象 W が 0 なら外れ（状態を変えない）。
  支持: 対象と参考のすべての W で missing = 0、かつ cross_extra の合計が 0。
  1 つでも外れれば反証。same_extra（同じ領域の中の群）は数えるが判定に入れない（#523 で残ると予想した側）。
開示: #522 の extra の名と、その領域の前置きを見ている。USES の値（exp は std・runtime を使う、std は syntax を使う など）を、
  この手順を書く前に見た。したがって reach の読みでは、std の動詞の extra に exp の動詞が残りうることを知って書いている。
使い方:
  python exp/experiments/sys_domain_by_refer.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_domain_by_refer.json"
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


    def count(W, eq=False):
        G = res(N[W].get("extends"))
        sw = shape(W)
        s_name = {x for x in N if T.is_a(x, W)}
        s_exact = {x for x in N if T.is_a(x, G) and shape(x) == sw and sub(end(x, "from"), end(W, "from")) and sub(end(x, "to"), end(W, "to")) and (dom(x) == dom(W) if eq else reach(dom(x), dom(W)))} if isinstance(G, str) else set()
        missing, extra = sorted(s_name - s_exact), sorted(s_exact - s_name)
        return {"genus": G, "shape": [sorted(map(str, s)) for s in sw], "ends": [end(W, "from"), end(W, "to")], "n_name": len(s_name), "n_exact": len(s_exact),
                "dom": dom(W), "missing": len(missing), "extra": len(extra), "cross_extra": [x for x in extra if dom(x) != dom(W)], "same_extra": [x for x in extra if dom(x) == dom(W)], "missing_names": missing[:20], "extra_names": extra[:20]}

    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    bad = 0
    cross = same = eq_missing = 0
    for W in targets:
        r = count(W)
        rows[f"word {W}"] = r
        bad += (r["missing"] > 0)
        cross += len(r["cross_extra"])
        same += len(r["same_extra"])
        e = count(W, eq=True)
        rows[f"eq {W}"] = e
        eq_missing += (e["missing"] > 0)
    rbad = 0
    for W in refs:
        r = count(W)
        rows[f"ref {W}"] = r
        rbad += (r["missing"] > 0)
        cross += len(r["cross_extra"])
        same += len(r["same_extra"])
        e = count(W, eq=True)
        rows[f"eq {W}"] = e
        eq_missing += (e["missing"] > 0)
    if not targets:
        verdict = "外れ"
    else:
        verdict = "支持" if bad == 0 and rbad == 0 and cross == 0 else "反証"
    s = {"build_ok": 1, "n_targets": len(targets), "n_targets_off": bad, "targets": targets,
         "n_refs": len(refs), "n_refs_off": rbad, "n_cross_extra": cross, "n_same_extra": same, "n_eq_missing": eq_missing, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
