"""仮説 h_layers_unhardcode（型検査器は識別子の選びに依存しない／層の置き場とシグネチャの類に依存する）を確かめる:
外れ 29 のうち 27 を分類どおりの層に動かした体系（#206）で、型検査器から、シグネチャ・シンタックス以外の名前の
読み（ハードコーディング）を、判定を変えずに取り除けるか。
結果を見る前に、この説明と手順と判定を登録した。

対象（事前に決める）。OLD の型検査器が、シグネチャ・シンタックス以外の名前を読んでいるところ（H）:
  ノード  ontology.continuant, ontology.occurrent（TOPS と gloss の最上位）, ontology.is（属するの終点）,
          ontology.v_depend（役割の根拠）, ontology.specifically_dependent_continuant, ontology.quality,
          ontology.magnitude, ontology.verb_ref, exp.v_spell
  個体    領域 ontology, runtime, std（LAYERS）, 法則 unique_names, step, frame, halt, no_confusion（LAWS_RUN）
  表示語  PART_WORDS・PART_VAGUE（「の部分である」「時間的な部分になる」など。v_compose・v_stage の表示語に当たる）
  syntax に動いた role・definition・v_refer・v_agree と、syntax に置かれた法則（LAWS_HERE）、文法の語（pre_rule など）、
  基礎の関係（same など）は、名前で読んでよいので H に入れない。

手順:
  1. 決まるか（determinable）: 体系を、ノードと個体を点にしたグラフにし、色を細分する（Weisfeiler-Leman、12 回）。
     初めの色は、シグネチャと syntax の点は名前、ほかの点は「?」に、式の形（キーの組、holds・pre・post の原子の
     基礎の関係と否定と位置）を添えたもの。辺は、定義の参照（T.refs と同じ範囲とその種類）と、事実（動詞の色を添える）、
     個体の is。表示語は色に入れない。H のノード・個体の色が、ほかのどの点とも違えば「決まる」: 名前を使わずに、
     式とシグネチャ・シンタックスの名前だけで、その点を指せる。
  2. 書き換え: 型検査器（cscl/bootstrap/type_checker/type_checker.py）だけを書き換え、H の読みを式からの導出に置き換える。
     体系の yaml は変えない（変えなければ取り除けないなら、それは「問題なく」でない）。
  3. 測る（HEAD の型検査器を NEW、commit OLD の型検査器を OLD とする。体系はどちらも OLD の yaml）:
     (a) 残り: NEW の文字列の定数のうち、H の名前（修飾した名前、と文法の語・基礎の関係・節の名前でない短い名前）
         に等しいもの、シグネチャ・syntax 以外の領域の修飾した名前に等しいもの、日本語を含み、文書・エラーの文・
         f 文字列の中でない定数（表示語の読み）の数。
     (b) 体系: NEW で、このリポジトリの体系を検査したエラーの数（領域の検査 checkers も含む。yaml は OLD と同じ）。
     (c) 名前の付け替え: シグネチャ・syntax・exp 以外の領域（ontology, runtime, std, lang, subj）のノード・個体の名前と、
         その領域の名前を、意味のない名前（r0001 …）に付け替えた体系を、NEW で検査したエラーの数。
         シグネチャ・syntax・exp の名前、文法の語、基礎の関係・軸の名前と同じ綴りの名前は付け替えない（数を記録する）。
         exp は領域の検査（exp_check.py）が名前を読むので付け替えない。この検査では checkers を外す。
         比べとして、OLD で同じ体系を検査したエラーの数も記録する（付け替えが名前の読みを突くことの確かめ）。
     (d) 変異: 決まった変異の組で、OLD と NEW の「弾く（エラーが 1 以上）」が同じか。checkers は外す。
         変異は、H のノードと、H のノードを直接 extends に持つノードについて、extends を消す・mod を消す（あるもの）、
         と、シグネチャ以外のノードを並べて random.Random(0) で選んだ 40 について、extends・mod・holds の
         あるものの最初を消す。
判定（ec が通るもとで）:
  H のノード・個体に、決まらないものが一つでもあれば反証（v_contradict）: 名前を使わずには指せない点が残る。
  すべて決まり、(a) が 0、(b) が 0、(c) が 0、(d) がすべて一致なら支持（v_support）。
  そのほかは mixed（決まるのに、書き換えで取り除けていない、または判定が変わった）。

開示:
  H は、OLD の型検査器を読んで手で挙げた。挙げ漏れは (a) の機械の数え方と (c) の付け替えで拾う。
  (c) で付け替えない名前（綴りがシグネチャ・syntax と同じもの）は、その分だけ確かめが弱い。
  「決まる」は、名前を使わない導出が在ることを示すだけで、型検査器の書き換えがそれを使うことは (a)〜(d) で見る。
  表示語の読み（PART_WORDS）は、グラフの色では扱わない。(a) の日本語の定数で数える。
  登録の前に、測る仕組みだけを OLD の型検査器で試した（H の「決まるか」は見ていない）:
    グラフは 920 点・849 色。OLD の (a) は、H の名前の定数 21、修飾した名前 5、日本語の定数 8（PART_WORDS・PART_VAGUE）。
    checkers を外した OLD は、OLD の体系で 0 件。付け替えた体系では OLD が 240 件で失敗する（付け替えが名前の読みを突く）。
    付け替えは 285 の名前、付け替えない名前は 22（runtime を含む。領域 runtime の名前は文法の語と同じ綴りなので、
    (c) では確かめられず、(a) でも数えない。LAYERS の runtime は、この実験の外に残りうる）。変異は 278。

行（sys_layers_unhardcode.json）:
  "hard <名前>": determinable, left（NEW に名前の定数が残る数）
  "check scan": n_left, n_qualified, n_ja
  "check system": errors_new
  "check rename": errors_new, errors_old, n_renamed, n_kept
  "check mutants": n_mutants, n_agree, old_reject, new_reject
  "summary 要約": n_hard, n_determinable, n_left, errors_system, errors_rename, n_mutants, n_agree

使い方:
  python exp/experiments/sys_layers_unhardcode.py
"""
import ast
import contextlib
import io
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
OLD = "fa18ad943f721c06a13362d7dae49623eb8dd01e"
TC = "cscl/bootstrap/type_checker/type_checker.py"
H_NODES = ["ontology.continuant", "ontology.occurrent", "ontology.is", "ontology.v_depend",
           "ontology.specifically_dependent_continuant", "ontology.quality", "ontology.magnitude",
           "ontology.verb_ref", "exp.v_spell"]
H_INDS = ["ontology", "runtime", "std", "unique_names", "step", "frame", "halt", "no_confusion"]
FREE = ("signature", "syntax")
RENAME_DOMS = ("ontology", "runtime", "std", "lang", "subj")
SECTIONS = {"domain", "base", "axes", "grammar", "runtime", "nodes", "individuals", "facts"}
WL_ROUNDS = 12


def dom_of(T, O, x):
    return T.domain(x) if x in T.N else O["_idom"].get(x)


def colors(T, O):
    G = O.get("grammar") or {}
    gw = {w for v in G.values() if isinstance(v, list) for w in v}
    V = list(T.N) + list(O["individuals"])

    def label(x):
        return x if dom_of(T, O, x) in FREE else "?"

    def shape(x):
        if x not in T.N:
            return ("ind",)
        n = T.N[x]
        atoms = tuple(sorted(str((s, a.get("is"), bool(a.get("neg")), a.get("from"), a.get("to")))
                             for s in ("holds", "pre", "post", "always", "sometime") for a in n.get(s) or []
                             if isinstance(a, dict) and a.get("is") in O["base"]))
        keys = tuple(sorted(k for k in n if k not in ("display", "gloss")))
        return ("node", keys, atoms, bool(n.get("neg")), bool(n.get("many")))

    out = {x: [] for x in V}
    for x in V:
        if x in T.N:
            n = T.N[x]
            for p in T.parents(x):
                out[x].append(("ext", p))
            for k in ("from", "to", "new_kind", "with"):
                if n.get(k) in T.N:
                    out[x].append((k, n[k]))
            for k in ("of", "form"):
                if k in n and n[k][0] in T.N:
                    out[x].append((f"{k}:{n[k][1] if len(n[k]) > 1 else ''}", n[k][0]))
            for m in n.get("mod") or []:
                if isinstance(m, dict):
                    if m.get("of") and m["of"][0] in T.N:
                        out[x].append((f"mod_of:{m['of'][1] if len(m['of']) > 1 else ''}:{bool(m.get('neg'))}", m["of"][0]))
                    if m.get("with") in T.N:
                        out[x].append((f"mod_with:{bool(m.get('neg'))}", m["with"]))
                elif m in T.N:
                    out[x].append(("mod", m))
            for c in n.get("cmp") or []:
                for k in ("a", "b"):
                    if isinstance(c, dict) and c.get(k) in T.N:
                        out[x].append((f"cmp_{k}", c[k]))
        else:
            i = O["individuals"][x]
            if i.get("is") in T.N:
                out[x].append(("is", i["is"]))
    facts = []
    for f in O["facts"]:
        if isinstance(f, dict) and f.get("is") in T.N and isinstance(f.get("from"), str) and isinstance(f.get("to"), str):
            if f["from"] in out and f["to"] in out:
                facts.append((f["is"], f["from"], f["to"], bool(f.get("neg"))))
    col = {x: str((label(x), shape(x), x in gw)) for x in V}
    for _ in range(WL_ROUNDS):
        sig = {}
        for x in V:
            a = sorted((k, col[y]) for k, y in out[x])
            b = sorted(("out", col[v], col[t], ng) for v, s, t, ng in facts if s == x)
            c = sorted(("in", col[v], col[s], ng) for v, s, t, ng in facts if t == x)
            sig[x] = str((col[x], a, b, c))
        ids = {s: str(i) for i, s in enumerate(sorted(set(sig.values())))}
        new = {x: ids[sig[x]] for x in V}
        if len(set(new.values())) == len(set(col.values())):
            col = new
            break
        col = new
    return col


def scan(src, T, O):
    G = O.get("grammar") or {}
    gw = {w for v in G.values() if isinstance(v, list) for w in v} | set(G) | set(O["base"]) | set(O["axes"]) | SECTIONS
    tree = ast.parse(src)
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip |= {id(v) for v in ast.walk(node)}
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(node.body[0].value, ast.Constant):
            skip.add(id(node.body[0].value))
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("err", "print"):
            skip |= {id(v) for a in node.args for v in ast.walk(a)}
    consts = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]
    hard = {h: [h] + ([h.split(".")[-1]] if h.split(".")[-1] not in gw else []) for h in H_NODES}
    hard |= {h: [h] if h not in gw else [] for h in H_INDS}
    left = {h: sum(c in ws for c in consts) for h, ws in hard.items()}
    qual = [c for c in consts if c in T.N and T.domain(c) not in FREE and "." in c]
    ja = [c for c in consts if re.search(r"[぀-ヿ一-鿿]", c)]
    return left, qual, ja


def worktree(rev):
    d = Path(tempfile.mkdtemp(prefix="unhard_"))
    subprocess.run(f"git archive {rev} cscl exp/src cscl.yaml | tar -x -C {d}", shell=True, cwd=ROOT, check=True)
    return d


def no_checkers(d):
    c = yaml.safe_load((d / "cscl.yaml").read_text(encoding="utf-8"))
    c["checkers"] = {}
    (d / "cscl.yaml").write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")


def run_tc(d, src, tag):
    (d / f"cscl/bootstrap/type_checker/tc_{tag}.py").write_text(src, encoding="utf-8")
    r = subprocess.run([sys.executable, f"cscl/bootstrap/type_checker/tc_{tag}.py"], cwd=d, capture_output=True, text=True)
    m = re.search(r"検査に失敗: (\d+) 件", r.stdout)
    if m:
        return int(m.group(1))
    return 0 if "検査に成功" in r.stdout else -1


def yaml_files(d):
    c = yaml.safe_load((d / "cscl.yaml").read_text(encoding="utf-8"))
    pats = [c["root"]] + c.get("library", []) + c.get("include", [])
    return sorted({p for g in pats for p in d.glob(g)})


def rename(d, T, O):
    G = O.get("grammar") or {}
    keep = {w for v in G.values() if isinstance(v, list) for w in v} | set(O["base"]) | set(O["axes"]) | SECTIONS
    keep |= {x.split(".")[-1] for x in T.N if T.domain(x) in FREE + ("exp",)}
    keep |= {i for i, dm in O["_idom"].items() if dm in FREE + ("exp",)}
    names = {x.split(".")[-1] for x in T.N if T.domain(x) in RENAME_DOMS}
    names |= {i for i, dm in O["_idom"].items() if dm in RENAME_DOMS} | set(RENAME_DOMS)
    kept = sorted(names & keep)
    M = {w: f"r{i:04d}" for i, w in enumerate(sorted(names - keep))}

    def tok(s):
        return ".".join(M.get(p, p) for p in s.split(".")) if isinstance(s, str) else s

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return tok(x)

    for p in yaml_files(d):
        D = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out = {}
        for k, v in D.items():
            if k in ("nodes", "individuals"):
                out[k] = {tok(n): walk(b) for n, b in (v or {}).items()}
            elif k == "domain":
                out[k] = tok(v)
            elif k in ("grammar", "base", "axes"):
                out[k] = v
            else:
                out[k] = walk(v)
        p.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return len(M), kept


def mutants(T):
    targets = [h for h in H_NODES if h in T.N]
    targets += sorted({x for x in T.N for h in H_NODES if h in T.parents(x) and "extends" in T.N[x]} - set(targets))
    ms = []
    for x in targets:
        for k in ("extends", "mod"):
            if k in T.N[x]:
                ms.append((x, k))
    pool = sorted(x for x in T.N if T.domain(x) != "signature" and x not in targets)
    for x in random.Random(0).sample(pool, 40):
        k = next((k for k in ("extends", "mod", "holds") if k in T.N[x]), None)
        if k:
            ms.append((x, k))
    return ms


def apply_mutant(d, T, x, k):
    dom, short = (x.split(".", 1) if "." in x else ("signature", x))
    for p in yaml_files(d):
        D = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if (D.get("domain") or "signature") == dom and short in (D.get("nodes") or {}):
            del D["nodes"][short][k]
            p.write_text(yaml.safe_dump(D, allow_unicode=True, sort_keys=False), encoding="utf-8")
            return
    raise SystemExit(f"変異の対象 {x} が見つからない")


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    new_src = (ROOT / TC).read_text(encoding="utf-8")
    old_src = subprocess.run(["git", "show", f"{OLD}:{TC}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    yaml_diff = subprocess.run(["git", "diff", "--name-only", OLD, "HEAD", "--", "cscl/library", "cscl/design", "exp/src/exp.yaml",
                                "exp/src/subj.yaml", "cscl.yaml"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    if yaml_diff:
        raise SystemExit("体系の yaml が OLD から変わっているので測らない: " + ", ".join(yaml_diff))

    col = colors(T, O)
    count = {}
    for c in col.values():
        count[c] = count.get(c, 0) + 1
    left, qual, ja = scan(new_src, T, O)
    rows = {}
    for h in H_NODES + H_INDS:
        rows[f"hard {h}"] = {"determinable": int(h in col and count[col[h]] == 1), "left": left[h]}

    r = subprocess.run([sys.executable, TC], cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"検査に失敗: (\d+) 件", r.stdout)
    sys_err = int(m.group(1)) if m else (0 if "検査に成功" in r.stdout else -1)
    base = worktree(OLD)
    no_checkers(base)
    rn = Path(tempfile.mkdtemp(prefix="unhard_rn_"))
    shutil.copytree(base, rn, dirs_exist_ok=True)
    n_ren, kept = rename(rn, T, O)
    ren_new, ren_old = run_tc(rn, new_src, "new"), run_tc(rn, old_src, "old")

    ms = mutants(T)

    def one(m):
        d = Path(tempfile.mkdtemp(prefix="unhard_m_"))
        shutil.copytree(base, d, dirs_exist_ok=True)
        apply_mutant(d, T, *m)
        o, n = run_tc(d, old_src, "old"), run_tc(d, new_src, "new")
        shutil.rmtree(d)
        return m, o, n

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, ms))
    agree = [int((o != 0) == (n != 0) and o >= 0 and n >= 0) for _, o, n in res]
    n_left = sum(left.values()) + len(qual) + len(ja)
    rows["check scan"] = {"n_left": sum(left.values()), "n_qualified": len(qual), "n_ja": len(ja)}
    rows["check system"] = {"errors_new": sys_err}
    rows["check rename"] = {"errors_new": ren_new, "errors_old": ren_old, "n_renamed": n_ren, "n_kept": len(kept)}
    rows["check mutants"] = {"n_mutants": len(ms), "n_agree": sum(agree),
                             "old_reject": sum(o != 0 for _, o, _ in res), "new_reject": sum(n != 0 for _, _, n in res)}
    n_det = sum(rows[f"hard {h}"]["determinable"] for h in H_NODES + H_INDS)
    rows["summary 要約"] = {"n_hard": len(H_NODES) + len(H_INDS), "n_determinable": n_det, "n_left": n_left,
                          "errors_system": sys_err, "errors_rename": ren_new, "n_mutants": len(ms), "n_agree": sum(agree)}
    (OUT / "sys_layers_unhardcode.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_layers_unhardcode.py", "_commit": head, "_old": OLD, "rows": rows,
         "qualified_left": qual, "ja_left": ja, "kept_names": kept,
         "mutants": [{"node": m[0], "drop": m[1], "old": o, "new": n} for m, o, n in res]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(base)
    shutil.rmtree(rn)
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    for h in H_NODES + H_INDS:
        print(h, rows[f"hard {h}"])
    if n_det < len(H_NODES) + len(H_INDS):
        print("判定: 反証")
    elif n_left == 0 and sys_err == 0 and ren_new == 0 and sum(agree) == len(ms):
        print("判定: 支持")
    else:
        print("判定: mixed")


if __name__ == "__main__":
    main()
