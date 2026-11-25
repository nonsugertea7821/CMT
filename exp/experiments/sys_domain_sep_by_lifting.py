"""h_domain_sep_by_lifting を確かめる: 領域でしか分かれない対は、一般の動詞を上流の領域へ移せば extends で分かれるか。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.domain, [syntax.extends, syntax.use_word]))。登録 #895（issue #896）。
  出どころ: #894（h_domain_sep_by_extends、反証）で、#891 の 7 対（x < W）のどれも、下流の W を上流の x の特化に書き換えられなかった。
  端の向きでは x が W の特化（narrow_from・narrow_to）で、逆に x の extends を W にすると上流が下流を指す（layered）。
  問い: W を、W の領域と x の領域の両方が使う上流の領域 U へ移せば、x の extends を W にでき、tc が通り、領域の条件なしで分かれるか。

操作（一時の写し。体系のファイルは書き換えない）:
  1. 今の main で #894 と同じ読み A・B（sys_domain_sep_by_extends.reader）を数え、sep（領域の条件だけが分けた対）を出す。
  2. sep を持つ W ごとに、写し（.git・__pycache__・.wt_* を除く）を 1 つ作り、次をまとめて行う:
     a. U を選ぶ: dom(W) とその W の sep のすべての dom(x) から reach で届き、W の extends の領域へ届く領域。
        候補が複数なら、ほかの候補のすべてへ届くもの（いちばん下流のもの）。それが 1 つに決まらなければ「不適」。
     b. W の行を dom(W) のファイルから U のファイル（nodes: の直後）へ移す。行の中の dom(W) の局所の名前は「dom(W).名」と書き直す。
        U にすでに同じ名前があれば「不適」。
     c. 名前の付け替え: 体系のファイル（yaml、results・trial・.wt_* を除く）で「dom(W).名」を「U.名」に、
        dom(W) のファイルの中の裸の「名」を「U.名」に替える。
     d. W の sep の x のうち、ほかの sep の x を上位に持たないもの（極大のもの）の extends を W（U での名、x の領域が U なら裸の名）にする。
        極大でない x は、極大の x を通して W の下位になる。
  3. 写しの上で tc を走らせ、通れば、写しの上でこのスクリプトを --probe で呼び、読み A・B と sep を数え直す。
     解けた W = tc が通り、写しの sep に、その W（U での名）を上位とする対が 1 つもなく、
     写しの sep が元の sep からその W の対を除いたものに含まれ（新しい sep が生まれない）、写しの miss_A の和が元より増えない。
  4. 対照: 書き換えない写しで tc が通り、--probe の sep が元と同じであること。
行（sys_domain_sep_by_lifting.json）: "word <W>"（元の読み）・"lift <W>"（写し）・"control 書き換えない写し"・"summary 要約"

判定（事前に決める）:
  build が失敗する、対照が落ちる、元の sep が 0 のどれかなら外れ（状態を変えない）。
  支持: sep を持つ W のすべてが解ける。
  反証: 解けない W が 1 つ以上ある（不適を含む）。
  記述: W ごとの U、移した行、書き換えた x、tc の末尾、写しの sep・miss_A・cross_A の数。
開示:
  - #894 の結果を見てから書いた。手順を書く前に、7 対の x の extends を読んだ:
    subj.v_allocate・subj.v_live・subj.v_place・syntax.v_use は ontology.v_depend を extends していて、exp.v_rely の 5 対は鎖になっている。
    ontology.v_design・ontology.v_depend・ja_basic.j_be・std.v_compute・exp.v_rely・exp.v_transfer は ontology.occurrent を extends する。
    領域の使う関係（tc.USES）: exp → runtime・std、std → syntax、syntax → ontology、subj → std、ja_basic → std・syntax、ontology → signature。
    だから 3 つの W のどれでも U は ontology になると予想し、支持に寄ると予想している。
  - 落ちうる所として、表示語の重なり（同じ領域で表示が一意であること）と、W の行が dom(W) の局所の名前に頼ることを予想している。
  - W を移すと、W の名前が変わる（exp.v_rely → ontology.v_rely）。体系の中の参照は付け替えるが、results の中の名前は付け替えない
    （結果のファイルは読みに入らない）。
使い方:
  python exp/experiments/sys_domain_sep_by_lifting.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_domain_sep_by_lifting.json"
sys.path[:0] = [str(Path(__file__).resolve().parent)]
from sys_domain_sep_by_extends import IGNORE, reader, run_tc  # noqa: E402


def yaml_files(root):
    return [f for f in root.glob("**/*.yaml")
            if not ({".git", "results", "trial"} & set(f.relative_to(root).parts))
            and not any(p.startswith(".wt_") for p in f.relative_to(root).parts)]


def dom_files(root, d):
    return [f for f in yaml_files(root) if re.search(rf"^domain: {re.escape(d)}$", f.read_text(encoding="utf-8"), re.M)]


def all_sep(tc, T, N, dom, count):
    targets = sorted(x for x in N if ("pre" in N[x] or "post" in N[x]))
    refs = sorted(x for x in N if "holds" in N[x] and x not in targets)
    sep, miss = [], 0
    for W in targets + refs:
        r = count(W)
        if r:
            sep += [[x, W] for x in r["sep"]]
            miss += len(r["miss_A"])
    return {"sep": sorted(sep), "miss_A": miss}


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--probe":
        print("PROBE " + json.dumps(all_sep(*reader()), ensure_ascii=False))
        return
    rows = {}
    try:
        tc, T, N, dom, count = reader()
    except Exception as e:
        rows["summary 要約"] = {"build_ok": 0, "error": str(e)[:300], "verdict": "外れ"}
        OUT.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(rows)
        return
    base = all_sep(tc, T, N, dom, count)
    sepW = {}
    for x, W in base["sep"]:
        sepW.setdefault(W, []).append(x)
    for W, xs in sepW.items():
        rows[f"word {W}"] = {"sep": xs, "dom": dom(W), "extends": N[W].get("extends")}

    def reach_set(d):
        seen, todo = set(), [d]
        while todo:
            c = todo.pop()
            if c in seen or c is None:
                continue
            seen.add(c)
            todo += list(tc.USES.get(c) or [])
        return seen

    def probe(dst):
        p = subprocess.run([sys.executable, str(dst / "exp/experiments/sys_domain_sep_by_lifting.py"), "--probe"], cwd=dst,
                           capture_output=True, text=True)
        lines = [l for l in p.stdout.splitlines() if l.startswith("PROBE ")]
        return json.loads(lines[-1][6:]) if lines else {"error": (p.stdout + p.stderr).strip().splitlines()[-3:]}

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "repo"
        shutil.copytree(ROOT, dst, ignore=IGNORE)
        ok, tail = run_tc(dst)
        pr = probe(dst)
        same = pr.get("sep") == base["sep"]
        rows["control 書き換えない写し"] = {"tc_ok": ok, "tc_tail": tail, "probe_same": int(same), "n_sep": len(base["sep"]),
                                       "miss_A": base["miss_A"]}
    control = bool(ok and same)

    solved = {}
    for W, xs in sepW.items():
        dW = dom(W)
        short = W.split(".")[-1]
        G = N[W].get("extends")
        rG = T.resolve(G, "signature") if isinstance(G, str) and G not in N else G
        dG = dom(rG) if isinstance(rG, str) else None
        common = set(reach_set(dW))
        for x in xs:
            common &= reach_set(dom(x))
        cand = sorted(u for u in common if dG in reach_set(u))
        low = [u for u in cand if all(v in reach_set(u) for v in cand)]
        q = {"cand": cand}
        if len(low) != 1:
            q.update(fit=0, why="U が 1 つに決まらない")
            rows[f"lift {W}"], solved[W] = q, False
            continue
        U = low[0]
        newW = f"{U}.{short}"
        q["U"] = U
        if newW in N or short in tc.LOCALS.get(U, []):
            q.update(fit=0, why="U に同じ名前がある")
            rows[f"lift {W}"], solved[W] = q, False
            continue
        top = [x for x in xs if not any(y != x and T.is_a(x, y) for y in xs)]
        q["retarget"] = top
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "repo"
            shutil.copytree(ROOT, dst, ignore=IGNORE)
            pat = re.compile(rf"^  {re.escape(short)}: \{{.*\}}\n", re.M)
            src = [f for f in dom_files(dst, dW) if pat.search(f.read_text(encoding="utf-8"))]
            ufs = dom_files(dst, U)
            if len(src) != 1 or len(ufs) != 1:
                q.update(fit=0, why="ファイルが 1 つに決まらない", src=[str(f.relative_to(dst)) for f in src],
                         ufiles=[str(f.relative_to(dst)) for f in ufs])
                rows[f"lift {W}"], solved[W] = q, False
                continue
            t = src[0].read_text(encoding="utf-8")
            line = pat.search(t).group(0)
            t = t.replace(line, "", 1)
            locs = set(tc.LOCALS.get(dW, [])) - {short}
            moved = re.sub(r"(?<![\w.])([A-Za-z_][\w]*)(?![\w.])",
                           lambda m: f"{dW}.{m.group(1)}" if m.group(1) in locs else m.group(1), line.split(":", 1)[1])
            moved = f"  {short}:{moved}"
            q["moved"] = moved.strip()
            src[0].write_text(t, encoding="utf-8")
            u = ufs[0].read_text(encoding="utf-8")
            u = re.sub(r"^nodes:\n", lambda m: m.group(0) + moved, u, count=1, flags=re.M)
            ufs[0].write_text(u, encoding="utf-8")
            n_ren = 0
            dW_files = set(dom_files(dst, dW))
            for f in yaml_files(dst):
                s = f.read_text(encoding="utf-8")
                s2 = re.sub(rf"(?<![\w.]){re.escape(dW)}\.{re.escape(short)}(?![\w])", newW, s)
                if f in dW_files:
                    s2 = re.sub(rf"(?<![\w.]){re.escape(short)}(?![\w])", newW, s2)
                if s2 != s:
                    n_ren += 1
                    f.write_text(s2, encoding="utf-8")
            q["n_files_renamed"] = n_ren
            q["x_old_extends"] = {}
            for x in top:
                dx, sx = dom(x), x.split(".")[-1]
                name = short if dx == U else newW
                xp = re.compile(rf"^(  {re.escape(sx)}: \{{.*?extends: )([^,}}]+)", re.M)
                fs = [f for f in dom_files(dst, dx) if xp.search(f.read_text(encoding="utf-8"))]
                if len(fs) != 1:
                    q["x_old_extends"][x] = None
                    continue
                s = fs[0].read_text(encoding="utf-8")
                q["x_old_extends"][x] = xp.search(s).group(2)
                fs[0].write_text(xp.sub(lambda m: m.group(1) + name, s, count=1), encoding="utf-8")
            tok, ttail = run_tc(dst)
            q.update(fit=1, tc_ok=tok, tc_tail=ttail)
            ok_w = False
            if tok:
                pr = probe(dst)
                q["probe_n_sep"] = len(pr.get("sep", [])) if "sep" in pr else None
                q["probe_miss_A"] = pr.get("miss_A")
                if "sep" in pr:
                    rest = [p for p in base["sep"] if p[1] != W]
                    left = [p for p in pr["sep"] if p[1] == newW]
                    new = [p for p in pr["sep"] if p not in rest and p[1] != newW]
                    q.update(left=left, new_sep=new)
                    ok_w = not left and not new and pr["miss_A"] <= base["miss_A"]
                else:
                    q["probe_error"] = pr.get("error")
            q["solved"] = int(ok_w)
            rows[f"lift {W}"], solved[W] = q, ok_w
    n_solved = sum(solved.values())
    if not control or not base["sep"]:
        verdict = "外れ"
    else:
        verdict = "支持" if n_solved == len(sepW) else "反証"
    s = {"build_ok": 1, "control_ok": int(control), "n_sep": len(base["sep"]), "n_w_sep": len(sepW), "n_w_solved": n_solved,
         "n_w_unsolved": len(sepW) - n_solved,
         "n_tc_fail": sum(1 for k, v in rows.items() if k.startswith("lift ") and v.get("fit") and not v.get("tc_ok")),
         "n_unfit": sum(1 for k, v in rows.items() if k.startswith("lift ") and not v.get("fit")), "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
