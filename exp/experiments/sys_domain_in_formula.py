"""h_domain_in_formula を確かめる: 同じ図の動詞を名前なしで分けるのに、成り立つ状態の読みは領域に頼るか。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.holds, syntax.domain))。登録 #526（issue #528）。
  出どころ: #525（h_domain_by_refer、反証）で、図と端に領域の届き（reach）を足しても、領域をまたぐ extra が 9 残った。
  #529 の h_domain_special_extends（支持）で、new_kind を包含で比べると 9 のうち 8 が消え、
  残る 1 対（exp.v_near と ontology.v_level）は extends を書き換えれば tc が通った。
  問い: new_kind まで入れた式の読みで、領域の条件は、まだ何かを分けているか。

操作（静的。体系のファイルも検査器も変えない）:
  #529 の読み（図 holds・pre・post が等しく、端 from・to と new_kind が包含、属が W の extends の下位）を、今の main で数える。
  A: 領域の条件なし。B: 領域の条件 reach(dom(x), dom(W)) あり（#525・#529 と同じ）。
  cross_A(W) = A の extra のうち dom(x) ≠ dom(W)。cross_B(W) も同じ。miss_A(W)・miss_B(W) = 名の下位のうち読みに入らないもの。
  sep = 対 (x, W) のうち、cross_A にあって cross_B にないもの（領域の条件だけが分けた対）。
行（sys_domain_in_formula.json）: "word <W>"・"ref <W>"・"summary 要約"

判定（事前に決める）:
  build が失敗するか、対象 W が 0 なら外れ（状態を変えない）。
  前提: B の miss の合計が 0（領域の条件が名の下位を落とさない）。満たさなければ判定しない。
  支持: sep が 1 対以上（式だけでは同じに読む領域をまたぐ対を、領域の条件が分ける）。
  反証: sep が 0（領域の条件は、式の読みに何も足さない）。
開示:
  - #525 の結果（reach の読みで cross_extra 9、等しさの読みで miss のある W が 9）と、#529 の結果（new_kind で 8 が消える）を見てから書いた。
  - A の数は見ていない。ontology は exp を使わないので、ontology の W に exp の動詞が入る対は B で落ちうる、とは予想している。
  - 領域の条件の向き（下位が上位の領域を使う）は #525 の読みのまま。等しさの読みは #525 で miss が出たので使わない。
使い方:
  python exp/experiments/sys_domain_in_formula.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_domain_in_formula.json"
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
        if not isinstance(G, str):
            return None
        sA = {x for x in N if T.is_a(x, G) and shape(x) == sw and sub(end(x, "from"), end(W, "from"))
              and sub(end(x, "to"), end(W, "to")) and sub(nk(x), nk(W))}
        sB = {x for x in sA if reach(dom(x), dom(W))}
        cA = sorted(x for x in sA - s_name if dom(x) != dom(W))
        cB = sorted(x for x in sB - s_name if dom(x) != dom(W))
        return {"genus": G, "dom": dom(W), "n_name": len(s_name), "n_A": len(sA), "n_B": len(sB),
                "miss_A": sorted(s_name - sA), "miss_B": sorted(s_name - sB), "cross_A": cA, "cross_B": cB,
                "sep": [x for x in cA if x not in cB], "same_extra_A": sorted(x for x in sA - s_name if dom(x) == dom(W))}

    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    nA = nB = mA = mB = 0
    sep = []
    for kind, ws in (("word", targets), ("ref", refs)):
        for W in ws:
            r = count(W)
            if r is None:
                continue
            rows[f"{kind} {W}"] = r
            nA += len(r["cross_A"])
            nB += len(r["cross_B"])
            mA += len(r["miss_A"])
            mB += len(r["miss_B"])
            sep += [f"{x} < {W}" for x in r["sep"]]
    if not targets:
        verdict = "外れ"
    elif mB > 0:
        verdict = "判定しない"
    else:
        verdict = "支持" if sep else "反証"
    s = {"build_ok": 1, "n_targets": len(targets), "n_refs": len(refs), "n_cross_A": nA, "n_cross_B": nB,
         "n_miss_A": mA, "n_miss_B": mB, "n_sep": len(sep), "sep": sep, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
