"""仮説 h_individual_scope_by_kind（宣言の範囲は領域で決まる: v_depend(declared_scope, syntax.domain)）を確かめる:
個体は、宣言した領域の外から名指せないか。名指せないとき、名前を使わずに、種類と式を通して、その個体を指せるか。
結果を見る前に、この説明と手順と判定を登録した。

対象（事前に決める）: 領域 signature, ontology, syntax, runtime, std（library）に宣言された個体のすべて（I_all）。
外の領域としては、lang（cscl/design/claims.yaml）を使う。

手順:
  1. 名指し（P1）: I_all の各個体 i（宣言した領域 D）について、HEAD の体系を写した作業場で、claims.yaml の facts に
     次の1つだけを足した体系を、HEAD の型検査器で検査する（領域の検査 checkers は外す）。
       (a) 中身の端: {is: v_refer, from: h_individual_scope_by_kind, to: {is: v_refer, from: <i の綴り>, to: syntax.domain}}
       (b) 事実の始点: 型検査器が集めた事実（修飾した後）のうち、i を始点とし終点が文字列の最初の1つ {is: V, from: i, to: X} を、
           始点を修飾した綴り D.i にして足す（そうした事実がない個体には作らない）
     <i の綴り> は、修飾した綴り D.i と、修飾しない綴り i の2つ。弾く（エラーが 1 以上）なら「名指せない」。
     比べとして (c) 種類: (a) の端を i の種類（i の is）にしたものも検査し、通る数を記録する（判定には使わない）。
  2. 種類を通して指せるか（P2）: I_all のうち、事実（終点が文字列）の始点になるもの（I_said。(b) を作る個体と同じ）について、体系を
     ノードと個体を点にしたグラフにし、色を細分する（Weisfeiler-Leman、12 回。sys_layers_unhardcode の colors と同じ
     辺と式の形）。初めの色は、シグネチャと syntax のノードは名前、ほかのノードと、すべての個体は「?」。
     個体の色が、ほかのどの点とも違えば「指せる」: 名前を使わず、種類と式と事実の形だけで、その個体を指せる。
判定（ec が通るもとで）:
  P1 で、通る（エラーが 0）変異が一つでもあれば反証（v_contradict）: 宣言の範囲が領域で決まっていない。
  P1 がすべて弾かれ、P2 で I_said のすべてが指せるなら支持（v_support）。
  P1 がすべて弾かれ、P2 で指せない個体があれば mixed: 範囲は領域で決まるが、外からは種類で足りない個体が残る。

開示:
  外の領域は lang の1つだけ。exp・subj から名指すことは試さない。
  (b) は D の事実を lang で言い直すもので、重複や型で弾かれることもありうる。エラーの文を記録し、
  「未定義」「個体でない」を含むもの（範囲で弾かれたもの）の数を別に数える。
  P2 の「指せる」は、名前を使わない区別が在ることを示すだけで、外の領域でそれを書く語が在ることは示さない。
  登録の前に、測る仕組みだけを試した: 写した作業場（checkers なし）と、claims.yaml を yaml として読み書きし直した作業場が、
  どちらも検査に通る（変異と色は見ていない）。

行（sys_individual_scope_by_kind.json）:
  "ind <i>": domain, named_qualified, named_bare, named_fact, kind_ok, said, determinable
     named_*: 1 なら通った（名指せた）、0 なら弾かれた、-1 なら作らなかった
  "summary 要約": n_all, n_mutants, n_accepted, n_scope_msg, n_kind_ok, n_said, n_determinable

使い方:
  python exp/experiments/sys_individual_scope_by_kind.py
"""
import contextlib
import io
import json
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
LIB = ("signature", "ontology", "syntax", "runtime", "std")
FREE = ("signature", "syntax")
CLAIMS = "cscl/design/claims.yaml"
WL_ROUNDS = 12


def colors(T, O):
    V = list(T.N) + list(O["individuals"])

    def label(x):
        return x if x in T.N and T.domain(x) in FREE else "?"

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
    col = {x: str((label(x), shape(x))) for x in V}
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


def worktree():
    d = Path(tempfile.mkdtemp(prefix="scope_"))
    subprocess.run(f"git archive HEAD cscl exp/src cscl.yaml | tar -x -C {d}", shell=True, cwd=ROOT, check=True)
    c = yaml.safe_load((d / "cscl.yaml").read_text(encoding="utf-8"))
    c["checkers"] = {}
    (d / "cscl.yaml").write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")
    return d


def run(base, fact):
    d = Path(tempfile.mkdtemp(prefix="scope_m_"))
    shutil.copytree(base, d, dirs_exist_ok=True)
    p = d / CLAIMS
    D = yaml.safe_load(p.read_text(encoding="utf-8"))
    D["facts"].append(fact)
    p.write_text(yaml.safe_dump(D, allow_unicode=True, sort_keys=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=d, capture_output=True, text=True)
    shutil.rmtree(d)
    m = re.search(r"検査に失敗: (\d+) 件", r.stdout)
    n = int(m.group(1)) if m else (0 if "検査に成功" in r.stdout else -1)
    msgs = [ln.strip() for ln in r.stdout.splitlines() if ln.startswith(" - ")]
    return n, msgs


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    I_all = sorted(i for i, dm in O["_idom"].items() if dm in LIB)
    first = {}
    for f in O["facts"]:
        if isinstance(f, dict) and f.get("from") in I_all and f["from"] not in first and isinstance(f.get("to"), str):
            first[f["from"]] = f
    said = set(first)

    jobs = []
    for i in I_all:
        dm = O["_idom"][i]
        for tag, sp in (("qualified", f"{dm}.{i}"), ("bare", i)):
            jobs.append((i, tag, {"is": "v_refer", "from": "h_individual_scope_by_kind",
                                  "to": {"is": "v_refer", "from": sp, "to": "syntax.domain"}}))
        if i in first:
            f = first[i]
            jobs.append((i, "fact", {"is": f["is"], "from": f"{dm}.{i}", "to": f["to"]}))
        k = O["individuals"][i].get("is")
        jobs.append((i, "kind", {"is": "v_refer", "from": "h_individual_scope_by_kind",
                                 "to": {"is": "v_refer", "from": k, "to": "syntax.domain"}}))
    base = worktree()
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda j: (j, run(base, j[2])), jobs))
    shutil.rmtree(base)

    col = colors(T, O)
    count = {}
    for c in col.values():
        count[c] = count.get(c, 0) + 1
    rows, detail = {}, []
    for i in I_all:
        rows[f"ind {i}"] = {"domain": O["_idom"][i], "named_qualified": -1, "named_bare": -1, "named_fact": -1,
                            "kind_ok": -1, "said": int(i in said), "determinable": int(count[col[i]] == 1)}
    scope_re = re.compile(r"未定義|個体でない")
    n_acc = n_scope = n_mut = n_kind = 0
    for (i, tag, fact), (n, msgs) in res:
        ok = int(n == 0)
        detail.append({"ind": i, "tag": tag, "fact": fact, "errors": n, "msgs": msgs[:3]})
        if tag == "kind":
            rows[f"ind {i}"]["kind_ok"] = ok
            n_kind += ok
            continue
        rows[f"ind {i}"][f"named_{tag}"] = ok
        n_mut += 1
        n_acc += ok
        n_scope += int(n > 0 and any(scope_re.search(m) for m in msgs))
    n_det = sum(rows[f"ind {i}"]["determinable"] for i in said)
    rows["summary 要約"] = {"n_all": len(I_all), "n_mutants": n_mut, "n_accepted": n_acc, "n_scope_msg": n_scope,
                          "n_kind_ok": n_kind, "n_said": len(said), "n_determinable": n_det}
    (OUT / "sys_individual_scope_by_kind.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_individual_scope_by_kind.py", "_commit": head, "rows": rows, "mutants": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    if n_acc:
        print("判定: 反証")
    elif n_det == len(said):
        print("判定: 支持")
    else:
        print("判定: mixed")


if __name__ == "__main__":
    main()
