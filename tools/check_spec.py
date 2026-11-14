"""spec/ の検査と値の計算。

spec/ が正本。文章（docs/, experiments/README.md）は正本ではない。

ontology.yaml  概念の体系。3本のツリーからなる。
  entities         実体のツリー。最上位は BFO の continuant と occurrent。
                   {識別子: {ja, is: 上位, where: {軸: 値}, gloss}}。where を持たない実体は gloss が必須。
  relations        関係のツリー。{識別子: {ja, is, domain, range, def | primitive | gloss}}。
                   def は述語論理の式。使える語は logic と、3本のツリーの識別子と、1文字の変数だけ。
  classifications  分類のツリー。{軸: {ja, is, from: 関係, values | values_from | number}}。
  検査: 表示語（ja）の一意性、上位・軸・値の解決、軸のもとになる関係の domain との型の一致、
        概念式の正規形の一意性、def の語の解決。

measurements.yaml  測定値。値は experiments/results/ から計算する。手で書いた数値は持たない。
  families: {族: {file, at, axes, where, keyset, cond, stats, meaning}}
    axes の直積で展開する。識別子は「族.軸の値....統計量」。
    stats: acc（margin>0 の割合）, both, margin（平均）, judged（judged==correct の割合）, mean（数値の平均）
    meaning: 軸の値 → 実体の識別子、または {分類の軸: 値}。

claims.yaml
  observations: {識別子: {rel, a, b, tol}}  rel は gt/lt/ge/le/approx/eq。a, b は測定値の識別子か数値。
    すべて真でなければ検査は失敗する。
  hypotheses: {識別子: {s, p, o, scope, status, evidence, against, supersedes, note}}
    s と o は実体、p は関係。s は p の domain、o は p の range の下位でなければならない。
    status: supported / partially_supported / refuted / untested
  decisions: {識別子: {s, p, o, basis, status, supersedes}}  status: adopted / tentative / withdrawn
  backlog: [{id, tests, status}]  status: done / running / queued

使い方:
  python tools/check_spec.py            検査
  python tools/check_spec.py --values   測定値をすべて表示
  python tools/check_spec.py --show ID  1つの項目を、参照を展開して表示
  python tools/check_spec.py --expr ID  実体の概念式（正規形）を表示
"""
import argparse
import itertools
import re
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"
RESULTS = ROOT / "experiments" / "results"
errors = []


def err(msg):
    errors.append(msg)


def load(name):
    return yaml.safe_load((SPEC / name).read_text(encoding="utf-8"))


def is_a(E, x, y):
    """実体 x が y と同じか、y の下位か。"""
    hops = 0
    while x is not None and hops < 100:
        if x == y:
            return True
        x, hops = E.get(x, {}).get("is"), hops + 1
    return False


def valid_value(A, E, axis, val, where):
    a = A.get(axis)
    if a is None or axis == "classification":
        err(f"{where}: 軸 {axis} が未定義")
        return
    for v in val if isinstance(val, list) else [val]:
        if "values" in a:
            if v not in a["values"]:
                err(f"{where}: 軸 {axis} に値 {v} がない")
        elif "values_from" in a:
            if v not in E or not is_a(E, v, a["values_from"]):
                err(f"{where}: 軸 {axis} の値 {v} は {a['values_from']} の下位でない")
        elif a.get("number"):
            if not isinstance(v, (int, float)):
                err(f"{where}: 軸 {axis} の値 {v} は数でない")


def canonical(E, eid):
    e = E[eid]
    if "where" not in e:
        return eid
    inner = ", ".join(f"{k}={e['where'][k]}" for k in sorted(e["where"]))
    return f"{canonical(E, e['is'])}[{inner}]"


def check_ontology(O):
    E, R, A, logic = O["entities"], O["relations"], O["classifications"], O["logic"]
    seen = {}

    def label(kind, key, ja):
        if not ja:
            err(f"{kind}: {key} に ja がない")
        elif ja in seen:
            err(f"表示語「{ja}」が {seen[ja]} と {kind}.{key} で重複（同音異義）")
        else:
            seen[ja] = f"{kind}.{key}"

    ids = {}
    for kind, tree in (("entities", E), ("relations", R), ("classifications", A)):
        for key in tree:
            if key in ids:
                err(f"識別子 {key} が {ids[key]} と {kind} で重複")
            ids[key] = kind
    # 分類
    for aid, a in A.items():
        label("classifications", aid, a.get("ja"))
        if aid == "classification":
            continue
        if a.get("is") not in A:
            err(f"classifications: {aid} の上位 {a.get('is')} が未定義")
        if a.get("from") not in R:
            err(f"classifications: {aid} のもとになる関係 {a.get('from')} が未定義")
        if sum(k in a for k in ("values", "values_from", "number")) != 1:
            err(f"classifications: {aid} は values / values_from / number のどれか1つを持つこと")
        for vid, v in (a.get("values") or {}).items():
            label(f"classifications.{aid}", vid, v.get("ja"))
        if "values_from" in a and a["values_from"] not in E:
            err(f"classifications: {aid} の values_from {a['values_from']} が未定義")
    # 実体
    forms = {}
    for eid, e in E.items():
        label("entities", eid, e.get("ja"))
        if eid == "entity":
            continue
        if e.get("is") not in E:
            err(f"entities: {eid} の上位 {e.get('is')} が未定義")
            continue
        if "where" not in e and "gloss" not in e:
            err(f"entities: 原始概念 {eid} に gloss がない")
        for axis, val in (e.get("where") or {}).items():
            valid_value(A, E, axis, val, f"entities.{eid}")
            rel = R.get(A.get(axis, {}).get("from"), {})
            if rel.get("domain") in E and not is_a(E, e["is"], rel["domain"]):
                err(f"entities: {eid} は軸 {axis} を使えない（上位 {e['is']} が、関係 {A[axis]['from']} の domain {rel['domain']} の下位でない）")
    for eid in E:
        if all(E.get(x, {}).get("is") in E or x == "entity" for x in [eid]) and "where" in E[eid] and E[eid].get("is") in E:
            f = canonical(E, eid)
            if f in forms:
                err(f"entities: {eid} と {forms[f]} の概念式が同じ（{f}）")
            forms[f] = eid
    # 関係
    allowed = set(logic["connectives"]) | set(logic["primitive_predicates"]) | set(E) | set(R) | set(A)
    for rid, r in R.items():
        label("relations", rid, r.get("ja"))
        if rid == "relation":
            continue
        if r.get("is") not in R:
            err(f"relations: {rid} の上位 {r.get('is')} が未定義")
        if "domain" in r or "range" in r:
            for k in ("domain", "range"):
                if r.get(k) not in E:
                    err(f"relations: {rid} の {k} {r.get(k)} が未定義")
            if "def" in r:
                for tok in re.findall(r"[A-Za-z_]+", r["def"]):
                    if len(tok) > 1 and tok not in allowed:
                        err(f"relations: {rid} の def の語 {tok} が未定義")
            elif not r.get("primitive"):
                err(f"relations: {rid} に def も primitive もない")
        elif "gloss" not in r:
            err(f"relations: 分類用の節 {rid} に gloss がない")
    return E, R, A


def resolve_meaning(val, E, A, where):
    if isinstance(val, dict):
        for axis, v in val.items():
            valid_value(A, E, axis, v, where)
    elif isinstance(val, list):
        for v in val:
            resolve_meaning(v, E, A, where)
    elif isinstance(val, str) and val not in E:
        err(f"{where}: 実体 {val} が未定義")


_cache = {}


def rows_of(file, at):
    key = (file, tuple(at))
    if key not in _cache:
        d = json.loads((RESULTS / file).read_text(encoding="utf-8"))
        for k in at:
            d = d[k]
        _cache[key] = list(d.items()) if isinstance(d, dict) else [(str(i), r) for i, r in enumerate(d)]
    return _cache[key]


def stat(rows, cond, name):
    vals = [r[cond] for _, r in rows if cond in r]
    if not vals:
        raise KeyError(f"条件 {cond} の行がない")
    n = len(vals)
    if name == "acc":
        return sum(v["margin"] > 0 for v in vals) / n, n
    if name == "both":
        return sum(bool(v["both"]) for v in vals) / n, n
    if name == "margin":
        return sum(v["margin"] for v in vals) / n, n
    if name == "judged":
        rs = [r for _, r in rows if cond in r]
        return sum(r[cond]["judged"] == r["correct"] for r in rs) / n, n
    if name == "mean":
        return sum(vals) / n, n
    raise KeyError(f"統計量 {name} は未定義")


def expand(M, E, A):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        axes = f["axes"]
        names = list(axes)
        keys = [list(axes[a]) if isinstance(axes[a], dict) else axes[a] for a in names]
        for a, mp in (f.get("meaning") or {}).items():
            for k, v in mp.items():
                resolve_meaning(v, E, A, f"measurements.{fid}.meaning.{a}.{k}")
        for combo in itertools.product(*keys):
            b = dict(zip(names, combo))
            sub = {a: (axes[a][b[a]] if isinstance(axes[a], dict) else b[a]) for a in names}
            fmt = lambda s: s.format(**{k: v for k, v in sub.items() if not isinstance(v, list)}) if isinstance(s, str) else s
            try:
                rows = rows_of(fmt(f["file"]), [fmt(x) for x in f.get("at", [])])
            except (FileNotFoundError, KeyError) as e:
                err(f"measurements.{fid}: {b} のファイルまたは位置が見つからない: {e}")
                continue
            for field, want in (f.get("where") or {}).items():
                want = sub[want[1:-1]] if isinstance(want, str) and want[1:-1] in sub and isinstance(sub[want[1:-1]], list) else fmt(want)
                ok = (lambda x: x in want) if isinstance(want, list) else (lambda x: x == want)
                rows = [(k, r) for k, r in rows if ok(r.get(field))]
            if "keyset" in f:
                axis = f["keyset"]["axis"]
                allowed = {fmt(f["keyset"]["pattern"]).replace("#", str(x)) for x in sub[axis]}
                rows = [(k, r) for k, r in rows if k in allowed]
            for st in f["stats"]:
                mid = ".".join([fid] + [str(b[a]) for a in names] + [st])
                try:
                    values[mid] = stat(rows, fmt(f["cond"]), st)
                except KeyError as e:
                    err(f"measurements: {mid}: {e}")
                meanings[mid] = {a: (f.get("meaning") or {}).get(a, {}).get(b[a], b[a]) for a in names} | {"stat": st}
    return values, meanings


def val_of(x, values, where):
    if isinstance(x, (int, float)):
        return float(x)
    if x not in values:
        err(f"{where}: 測定値 {x} が未定義")
        return None
    return values[x][0]


def check_claims(C, values, E, R):
    obs = C["observations"]
    for oid, o in obs.items():
        a, b = val_of(o["a"], values, oid), val_of(o["b"], values, oid)
        if a is None or b is None:
            continue
        tol = o.get("tol", 0.005)
        holds = {"gt": a > b, "lt": a < b, "ge": a >= b - 1e-9, "le": a <= b + 1e-9,
                 "approx": abs(a - b) <= tol + 1e-9, "eq": abs(a - b) <= 0.005}[o["rel"]]
        if not holds:
            err(f"observations: {oid} が成り立たない（{o['rel']}: a={a:.3f}, b={b:.3f}）")
    hyps, decs = C["hypotheses"], C["decisions"]

    def triple(x, where):
        rel = R.get(x["p"])
        if rel is None or "domain" not in rel:
            err(f"{where}: 関係 {x['p']} が未定義")
            return
        for part, bound in (("s", rel["domain"]), ("o", rel["range"])):
            v = x[part]
            for t in v if isinstance(v, list) else [v]:
                if t not in E:
                    err(f"{where}: 実体 {t} が未定義")
                elif not is_a(E, t, bound):
                    err(f"{where}: {t} は関係 {x['p']} の{'domain' if part == 's' else 'range'} {bound} の下位でない")

    for hid, h in hyps.items():
        triple(h, hid)
        if h["status"] not in ("supported", "partially_supported", "refuted", "untested"):
            err(f"{hid}: status が不正")
        for t in h.get("scope", []):
            if t not in E:
                err(f"{hid}: scope の実体 {t} が未定義")
        for k in ("evidence", "against"):
            for r in h.get(k, []):
                if r not in obs:
                    err(f"{hid}: {k} の観察 {r} が未定義")
        for r in h.get("supersedes", []):
            if r not in hyps:
                err(f"{hid}: supersedes の仮説 {r} が未定義")
        if h["status"] in ("supported", "partially_supported", "refuted") and not (h.get("evidence") or h.get("against")):
            err(f"{hid}: 根拠の観察がない")
    for did, d in decs.items():
        triple(d, did)
        if d["status"] not in ("adopted", "tentative", "withdrawn"):
            err(f"{did}: status が不正")
        for r in d.get("basis", []):
            if r not in hyps:
                err(f"{did}: basis の仮説 {r} が未定義")
        for r in d.get("supersedes", []):
            if r not in decs:
                err(f"{did}: supersedes の決定 {r} が未定義")
    for b in C["backlog"]:
        if b["status"] not in ("done", "running", "queued"):
            err(f"backlog {b['id']}: status が不正")
        for r in b.get("tests", []):
            if r not in hyps:
                err(f"backlog {b['id']}: tests の仮説 {r} が未定義")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--values", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--expr")
    args = ap.parse_args()
    O, M, C = load("ontology.yaml"), load("measurements.yaml"), load("claims.yaml")
    E, R, A = check_ontology(O)
    values, meanings = expand(M, E, A)
    check_claims(C, values, E, R)
    if args.expr:
        print(canonical(E, args.expr))
    if args.values:
        for mid, (v, n) in sorted(values.items()):
            print(f"{mid} = {v:.2f} (n={n})")
    if args.show:
        for sect in ("observations", "hypotheses", "decisions"):
            if args.show in C[sect]:
                x = C[sect][args.show]
                print(yaml.safe_dump({args.show: x}, allow_unicode=True, sort_keys=False))
                for k in ("a", "b"):
                    if isinstance(x.get(k), str):
                        v, n = values[x[k]]
                        print(f"{x[k]} = {v:.2f} (n={n})  {meanings[x[k]]}")
        if args.show in values:
            print(values[args.show], meanings[args.show])
        for tree in (E, R, A):
            if args.show in tree:
                print(tree[args.show])
    if errors:
        print(f"検査に失敗: {len(errors)} 件")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print(f"検査に成功: 実体 {len(E)}、関係 {len(R)}、分類の軸 {len(A) - 1}、測定値 {len(values)}、観察 {len(C['observations'])}、"
          f"仮説 {len(C['hypotheses'])}、決定 {len(C['decisions'])}、残り項目 {len(C['backlog'])}")


if __name__ == "__main__":
    main()
