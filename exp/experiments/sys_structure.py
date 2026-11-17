"""体系そのものを数える（2）。象限への分かれ方、真偽の写像についての対称性、制限（否定だけの限定）の在り方。
言語の設計の主張（cscl/design/claims.yaml）の観察のもとになる結果ファイルを書く。

  sys_quadrants.json  ノード1つが1行。各ノードが自分で足した定義の形から、象限に入るか（0 か 1）を決める。
                      継承した定義は見ない（上位の at: {count: 1} が下位すべてを量にしてしまうので）。
      rel    関係: 動詞である
      truth  真偽: 文か世界の下位である、または真偽の軸（truth）を使う
      quant  量: 大きさか値の下位である、または数の軸（count, amount, ratio, order）を使う
      qual   質: 動詞でなく、肯定の限定を足す、質の下位である、または端の形（form, of）である
      none   どの象限にも入らない
      quant_alone  量だけに入る
      rel_mixed    関係と、ほかの象限の両方に入る
      none_other   どこにも入らず、根でも「自分の定義が否定の限定だけ」でもない
      neg_only     自分の定義が否定の限定だけ（上位の指定のほかに、否定の限定しか足さない）
  sys_symmetry.json   真と偽を入れ替える写像 σ についての確かめ。1行が1回の確かめで、agree は食い違いがなければ 1。
      σ は、述べた真偽を入れ替え、述べていない文はそのままにする。文の読み方は 真 ↔ 偽、「述べられていない」はそのまま。
      世界は、閉世界 ↔ 鏡の世界（述べていない文は真。この確かめの中でだけ置く）、world だけの世界はそのまま。
      reading  ランダムな状態と世界で、すべての文と読み方の判定が、写した側の判定と一致するか
      step     動的な動詞の pre・post も写して1歩進めると、写した状態に移るか

  sys_limitation.json 自分の定義が否定の限定だけのノード（制限）が1行、と、すべての限定（mod）が1行。
      in_closed     そのノードの領域が閉世界を前提に置く（v_presume）
      has_pair      同じ動詞・同じ端・同じ相手（of, with）の肯定の限定を持つノードがある
      pair_closed / pair_open / pair_subj   has_pair を、閉世界の領域・開世界の領域（subj を除く）・subj に分けたもの
      stated_false  限定が「偽と述べる」読み方（val: {truth: false}）である
      unstated      限定が「述べられていない」読み方（neg）である

使い方:
  python exp/experiments/sys_structure.py      結果ファイルを exp/experiments/results に書く
"""
import contextlib
import io
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/runtime")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import runtime as rt  # noqa: E402

OUT = ROOT / "exp/experiments/results"
DEF_ONLY = {"display", "gloss", "extends", "verbatim", "many"}   # 種類を限定しない書き方


def own_axes(x):
    out = set(x.get("val") or {}) | {c.get("axis") for c in x.get("cmp") or []}
    for m in x.get("mod") or []:
        if isinstance(m, dict):
            out |= set(m.get("at") or {})
    return out


def quadrants(T):
    num = {a for a, x in T.AX.items() if x["value"] == "number"}
    isa = lambda n, k: k in T.N and T.is_a(n, k)
    rows = {}
    for n, x in T.N.items():
        ax, verb = own_axes(x), T.is_verb(n)
        mods = [m for m in x.get("mod") or [] if isinstance(m, dict)]
        q = {"rel": verb,
             "truth": isa(n, "ontology.sentence") or isa(n, "syntax.world") or "truth" in ax,
             "quant": isa(n, "ontology.magnitude") or isa(n, "syntax.value") or bool(ax & num),
             "qual": not verb and (isa(n, "ontology.quality") or "form" in x or "of" in x
                                   or any(not m.get("neg") for m in mods))}
        neg_only = not verb and bool(mods) and all(m.get("neg") for m in mods) and set(x) <= DEF_ONLY | {"mod"}
        none = not any(q.values())
        rows[n] = {k: int(v) for k, v in q.items()} | {
            "none": int(none), "quant_alone": int(q["quant"] and not (q["rel"] or q["truth"] or q["qual"])),
            "rel_mixed": int(q["rel"] and (q["truth"] or q["quant"] or q["qual"])),
            "neg_only": int(neg_only), "none_other": int(none and not neg_only and n not in tc.TOPS)}
    return rows


def limitation(T, rows_q):
    closed = {d for d, ws in tc.presumed_worlds().items() if "closed_world" in ws}
    key = lambda m: (tuple(m["of"]), m.get("with"))
    pos = {key(m) for x in T.N.values() for m in x.get("mod") or [] if isinstance(m, dict) and not m.get("neg")}
    rows = {}
    for n, q in rows_q.items():
        if not q["neg_only"]:
            continue
        d, m = n.split(".")[0], T.N[n]["mod"][0]
        pair = int(key(m) in pos)
        side = "pair_closed" if d in closed else "pair_subj" if d == "subj" else "pair_open"
        rows[f"node {n}"] = {"in_closed": int(d in closed), "has_pair": pair, side: pair}
    for n, x in T.N.items():
        for i, m in enumerate(m for m in x.get("mod") or [] if isinstance(m, dict)):
            rows[f"mod {n} {i}"] = {"stated_false": int(tc.truth_of(m) is False and "val" in m),
                                    "unstated": int(bool(m.get("neg")))}
    return rows


def symmetry(T):
    U = rt.UNSTATED
    flip = lambda r: U if r == U else (not r)
    worlds = dict(rt.WORLDS) | {"co_closed_world": True}
    dual = {"closed_world": "co_closed_world", "co_closed_world": "closed_world", "world": "world"}
    saved = dict(rt.WORLDS)
    rt.WORLDS.update(worlds)
    rng, rows = random.Random(0), {}
    inds = ["a", "b", "c"]
    run = {"individuals": {i: {"is": "continuant"} for i in inds}, "facts": []}
    atoms = [("exists", (i,)) for i in inds] + [("depend", p) for p in itertools.permutations(inds, 2)]
    for i in range(300):
        st = {a: rng.choice([True, False]) for a in atoms if rng.random() < 0.5}
        for w in dual:
            m, md = rt.Machine(T, run, "x", w), rt.Machine(T, run, "x", dual[w])
            m.facts, md.facts = dict(st), {k: not v for k, v in st.items()}
            ok = all(m.holds(r, *a) == md.holds(flip(r), *a) for a in atoms for r in (True, False, U))
            rows[f"reading {i:03d} {w}"] = {"reading": int(ok)}
    run2 = {"individuals": {"a": {"is": "continuant"}, "b": {"is": "continuant"}, "k": {"is": "any"}}, "facts": []}
    rels = ("depend", "part", "refer", "after", "involve")
    space = [("exists", (i,)) for i in "abk"] + [(r, p) for r in rels for p in itertools.permutations("abk", 2)]
    for v in [v for v in T.N if "pre" in T.N[v]]:
        news = any("new" in tc.atom(f)[2] for f in T.N[v]["pre"] + T.N[v]["post"])
        b = dict(zip(["from", "to"] + (["new"] if news else []), "abk"))
        for i in range(20):
            st = {a: rng.choice([True, False]) for a in space if rng.random() < 0.4}
            for w in dual:
                m, md = rt.Machine(T, run2, "x", w), rt.Machine(T, run2, "x", dual[w])
                m.facts, md.facts = dict(st), {k: not x for k, x in st.items()}
                r, _ = m.bind(v, b)
                if r is None:
                    continue
                rd = {k: [(flip(x), rel, args) for x, rel, args in r[k]] for k in r}
                m.bind, md.bind = (lambda *a, r=r: (r, None)), (lambda *a, rd=rd: (rd, None))
                m.check_laws = md.check_laws = lambda *a: None   # 法則は真と述べた文にだけ当たる。ここでは歩みだけを比べる
                m.step(v, b, "s")
                md.step(v, b, "s")
                ok = {k: not x for k, x in m.facts.items()} == md.facts and bool(m.errors) == bool(md.errors)
                rows[f"step {tc.short(v)} {i:02d} {w}"] = {"step": int(ok)}
    rt.WORLDS.clear()
    rt.WORLDS.update(saved)
    return rows


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    with contextlib.redirect_stdout(io.StringIO()):
        O2 = tc.load(tc.root_name())
        for _, name in tc.register_domains(O2):
            tc.merge_domain(name, O2)
        T2 = tc.Ontology(O2)
    q = quadrants(T)
    for name, rows in (("sys_quadrants", q), ("sys_symmetry", symmetry(T2)), ("sys_limitation", limitation(T, q))):
        (OUT / f"{name}.json").write_text(json.dumps(
            {"_source": "exp/experiments/sys_structure.py", "_commit": commit, "rows": rows},
            ensure_ascii=False, indent=1), encoding="utf-8")
        cols = sorted({k for r in rows.values() for k in r})
        print(name, len(rows), "行", {c: sum(r.get(c, 0) for r in rows.values()) for c in cols})


if __name__ == "__main__":
    main()
