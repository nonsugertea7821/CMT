"""h_domain_sep_by_extends を確かめる: 領域の条件だけが分けた対は、extends の特化で分けられるか。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.domain, syntax.extends))。登録 #892（issue #893）。
  出どころ: #891（h_domain_in_formula、支持）で、式の読み（図 holds・pre・post が等しく、端 from・to と new_kind が包含、
  属が W の extends の下位）では同じに読み、領域の条件 reach(dom(x), dom(W)) だけが分けた対 (x, W) が 7 あった:
    ontology.v_design < std.v_compute、ontology.v_depend < exp.v_rely、subj.v_allocate < exp.v_rely、
    subj.v_live < exp.v_rely、subj.v_place < exp.v_rely、syntax.v_use < exp.v_rely、ja_basic.j_be < exp.v_transfer
  問い: W の側を x の特化として書けば（W の extends を x にすれば）、領域の条件なしで、x は W の「同じ読みの別の動詞」でなくなるか。

操作（一時の写し。体系のファイルは書き換えない）:
  1. 今の main で #891 の読み A（領域の条件なし）と B（あり）を数え、sep（A の領域をまたぐ extra のうち B にないもの）を出す。
  2. sep を持つ W ごとに、その W の sep の各 x を候補にし、写し（.git・__pycache__・.wt_* を除く）の上で
     W の行の extends を x に書き換える（候補ごとに 1 回。他は元のまま）。名前は領域を付けた形（例 ontology.v_depend）。
  3. 写しの上で tc を走らせ、通るかを見る。通れば、写しの上で同じ読み A を W について数え直す（このスクリプトを --probe で呼ぶ）。
     解けた対 = W の sep の x' のうち、写しの読み A で W の cross に入らなくなったもの。
     写しの読み A で miss が出る（名の下位が読みから落ちる）書き換えは、解けたと数えない。
  4. 対照: 書き換えない写しで tc が通ること、書き換えない写しの --probe が元の読み A と同じ cross を返すこと。
  読み A で、W の extends の鎖の上にある動詞（W の上位）は extra に数えない（宣言した親は「別の動詞」ではない）。
  この除外は #891 の読みには無かった。元の読みでは sep の x はどれも W の上位でないので、元の sep の数は変わらない（対照で確かめる）。
行（sys_domain_sep_by_extends.json）: "word <W>"（元の読み）・"try <x> > <W>"（書き換え）・"control 書き換えない写し"・"summary 要約"

判定（事前に決める）:
  build が失敗する、対照の tc が落ちる、対照の --probe が元と違う、元の sep が 0 のどれかなら外れ（状態を変えない）。
  支持: sep を持つ W のすべてで、1 回の書き換え（tc が通り、miss を出さない）が、その W の sep をすべて解く。
  反証: sep を持つ W のどれかで、どの 1 回の書き換えも、その W の sep をすべては解かない
        （extends は親を 1 つしか書けないので、比べられない上流の動詞が 2 つ以上あると、片方は領域でしか分かれない）。
  記述: 解けない対の数（n_unsolved: W ごとに最もよく解く書き換えで残る対の和）、tc が落ちた書き換えとその末尾。
開示:
  - #891 の sep 7 対を見てから書いた。exp.v_rely に 5 対あり、extends は親を 1 つしか書けないので、
    その 5 つの上流の動詞が互いに上位・下位の鎖になっていなければ反証に寄る、と予想している。鎖かどうかはまだ見ていない。
  - 書き換えは W の側（下流）を上流の x の特化にする向き。x の側を W の特化にする向き（#529 の操作の向き）は、
    上流が下流を指すことになるので試さない。
  - 一時の写しは #529 の手順（sys_domain_special_extends）の訂正と同じく、.git と __pycache__ を除く。
    加えて、作業用のワークツリー（.wt_*）を除く（写しが大きくなるため。体系のファイルの読みには入らない）。
使い方:
  python exp/experiments/sys_domain_sep_by_extends.py
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_domain_sep_by_extends.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
KEYS = ("holds", "pre", "post")
IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".wt_*")


def reader():
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
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
        if not isinstance(G, str):
            return None
        sw = shape(W)
        up = set(T.ancestors(W))
        s_name = {x for x in N if T.is_a(x, W)}
        sA = {x for x in N if T.is_a(x, G) and shape(x) == sw and sub(end(x, "from"), end(W, "from"))
              and sub(end(x, "to"), end(W, "to")) and sub(nk(x), nk(W))}
        sB = {x for x in sA if reach(dom(x), dom(W))}
        cA = sorted(x for x in sA - s_name - up if dom(x) != dom(W))
        cB = sorted(x for x in sB - s_name - up if dom(x) != dom(W))
        return {"genus": G, "dom": dom(W), "n_name": len(s_name), "miss_A": sorted(s_name - sA), "miss_B": sorted(s_name - sB),
                "cross_A": cA, "cross_B": cB, "sep": [x for x in cA if x not in cB], "up": sorted(up)}

    return tc, T, N, dom, count


def run_tc(dst):
    p = subprocess.run([sys.executable, str(dst / "cscl/bootstrap/type_checker/type_checker.py")], cwd=dst, capture_output=True, text=True)
    return int("検査に成功" in p.stdout), (p.stdout + p.stderr).strip().splitlines()[-3:]


def probe(dst, W):
    p = subprocess.run([sys.executable, str(dst / "exp/experiments/sys_domain_sep_by_extends.py"), "--probe", W], cwd=dst,
                       capture_output=True, text=True)
    lines = [l for l in p.stdout.splitlines() if l.startswith("PROBE ")]
    return json.loads(lines[-1][6:]) if lines else {"error": (p.stdout + p.stderr).strip().splitlines()[-3:]}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        tc, T, N, dom, count = reader()
        print("PROBE " + json.dumps(count(sys.argv[2]), ensure_ascii=False))
        return
    rows = {}
    try:
        tc, T, N, dom, count = reader()
    except Exception as e:
        rows["summary 要約"] = {"build_ok": 0, "error": str(e)[:300], "verdict": "外れ"}
        OUT.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(rows)
        return
    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    sepW = {}
    for W in targets + refs:
        r = count(W)
        if r and r["sep"]:
            rows[f"word {W}"] = r
            sepW[W] = r
    n_sep = sum(len(r["sep"]) for r in sepW.values())

    def file_of(W):
        short = W.split(".")[-1]
        pat = re.compile(rf"^  {re.escape(short)}: \{{.*?extends: ", re.M)
        fs = [f for f in ROOT.glob("**/*.yaml") if not ({".git", "results"} & set(f.parts)) and not any(p.startswith(".wt_") for p in f.relative_to(ROOT).parts)
              and pat.search(f.read_text(encoding="utf-8"))]
        fs = [f for f in fs if dom(W) in f.stem or dom(W) in f.parent.name] or fs
        return fs

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "repo"
        shutil.copytree(ROOT, dst, ignore=IGNORE)
        ok, tail = run_tc(dst)
        same = all(probe(dst, W).get("cross_A") == r["cross_A"] for W, r in sepW.items())
        rows["control 書き換えない写し"] = {"tc_ok": ok, "tc_tail": tail, "probe_same": int(same)}
    control = ok and same

    best = {}
    n_tc_fail = 0
    for W, r in sepW.items():
        fs = file_of(W)
        best[W] = []
        for x in r["sep"]:
            key = f"try {x} > {W}"
            if len(fs) != 1:
                rows[key] = {"fit": 0, "files": [str(f.relative_to(ROOT)) for f in fs]}
                continue
            rel = fs[0].relative_to(ROOT)
            short = W.split(".")[-1]
            with tempfile.TemporaryDirectory() as tmp:
                dst = Path(tmp) / "repo"
                shutil.copytree(ROOT, dst, ignore=IGNORE)
                f = dst / rel
                t = f.read_text(encoding="utf-8")
                t2 = re.sub(rf"^(  {re.escape(short)}: \{{.*?extends: )([^,}}]+)", lambda m: m.group(1) + x, t, count=1, flags=re.M)
                f.write_text(t2, encoding="utf-8")
                tok, ttail = run_tc(dst)
                q = {"fit": 1, "file": str(rel), "changed": int(t2 != t), "tc_ok": tok, "tc_tail": ttail}
                if tok:
                    pr = probe(dst, W)
                    q["probe"] = pr
                    if "cross_A" in pr and not pr.get("miss_A"):
                        q["solved"] = [y for y in r["sep"] if y not in pr["cross_A"]]
                    else:
                        q["solved"] = []
                else:
                    n_tc_fail += 1
                    q["solved"] = []
                rows[key] = q
                if len(q["solved"]) > len(best[W]):
                    best[W] = q["solved"]
    unsolved = {W: [x for x in r["sep"] if x not in best[W]] for W, r in sepW.items()}
    n_unsolved = sum(len(v) for v in unsolved.values())
    if not control or n_sep == 0:
        verdict = "外れ"
    else:
        verdict = "支持" if n_unsolved == 0 else "反証"
    s = {"build_ok": 1, "control_ok": int(bool(control)), "n_w_sep": len(sepW), "n_sep": n_sep, "n_tries": sum(1 for k in rows if k.startswith("try ")),
         "n_tc_fail": n_tc_fail, "n_unsolved": n_unsolved, "n_w_unsolved": sum(1 for v in unsolved.values() if v),
         "unsolved": {W: v for W, v in unsolved.items() if v}, "best": best, "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
