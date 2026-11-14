"""spec/ の検査と値の計算。

spec/ が正本。文章（docs/, experiments/README.md）は正本ではない。

文法（すべて YAML）:

terms.yaml
  roles: [役割の識別子, ...]
  predicates: {識別子: {ja: 表示語}}
  terms: {識別子: {ja: 表示語, genus: 上位の識別子, diff: {役割: 識別子 | "=リテラル"}, gloss: 説明}}
    - genus を持たない語（原始語）は gloss が必須。
    - ja は全体で一意（同音異義を許さない）。

measurements.yaml
  families: {族の識別子: {file, at, axes, where, keyset, cond, stats, meaning}}
    - axes の直積で測定値を展開する。識別子は「族.軸の値....統計量」。
    - 値は results のファイルから計算する。手で書いた数値は持たない。
    - stats: acc（margin>0 の割合）, both, margin（平均）, judged（judged==correct の割合）, mean（数値の平均）
    - meaning: 軸の値 → 語の識別子、または {役割: 語} の構造。

claims.yaml
  observations: {識別子: {rel, a, b, tol}}  rel は gt/lt/ge/le/approx/eq。a, b は測定値の識別子か数値。
    - すべて真でなければ検査は失敗する。
  hypotheses: {識別子: {s, p, o, scope, status, evidence, against, supersedes}}
    - status: supported / partially_supported / refuted / untested
  decisions: {識別子: {s, p, o, basis, status, supersedes}}
    - status: adopted / tentative / withdrawn
  backlog: [{id, tests, status}]  status: done / running / queued

使い方:
  python tools/check_spec.py            検査
  python tools/check_spec.py --values   測定値をすべて表示
  python tools/check_spec.py --show ID  1つの項目を、参照を展開して表示
"""
import argparse
import itertools
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


def check_terms(T):
    roles, preds, terms = set(T["roles"]), T["predicates"], T["terms"]
    seen = {}
    for tid, t in {**terms, **preds}.items():
        ja = t.get("ja")
        if not ja:
            err(f"terms: {tid} に ja がない")
        elif ja in seen:
            err(f"terms: 表示語「{ja}」が {seen[ja]} と {tid} で重複（同音異義）")
        seen[ja] = tid
    for tid, t in terms.items():
        if "genus" in t:
            if t["genus"] not in terms:
                err(f"terms: {tid} の genus {t['genus']} が未定義")
        elif "gloss" not in t:
            err(f"terms: 原始語 {tid} に gloss がない")
        for role, val in (t.get("diff") or {}).items():
            if role not in roles:
                err(f"terms: {tid} の役割 {role} が未定義")
            if not (isinstance(val, str) and val.startswith("=")) and val not in terms:
                err(f"terms: {tid} の diff 値 {val} が未定義")
    # genus の循環
    for tid in terms:
        cur, hops = tid, 0
        while cur in terms and "genus" in terms[cur]:
            cur, hops = terms[cur]["genus"], hops + 1
            if hops > 50:
                err(f"terms: {tid} の genus が循環")
                break
    return terms, preds, roles


def resolve_meaning(val, terms, roles, where):
    if isinstance(val, dict):
        for role, v in val.items():
            if role not in roles:
                err(f"{where}: 役割 {role} が未定義")
            resolve_meaning(v, terms, roles, where)
    elif isinstance(val, list):
        for v in val:
            resolve_meaning(v, terms, roles, where)
    elif isinstance(val, str) and not val.startswith("=") and val not in terms:
        err(f"{where}: 語 {val} が未定義")


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


def expand(M, terms, roles):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        axes = f["axes"]
        names = list(axes)
        keys = [list(axes[a]) if isinstance(axes[a], dict) else axes[a] for a in names]
        for a, mp in (f.get("meaning") or {}).items():
            for k, v in mp.items():
                resolve_meaning(v, terms, roles, f"measurements.{fid}.meaning.{a}.{k}")
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


def check_claims(C, values, terms, preds):
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
        for part in ("s", "o"):
            v = x[part]
            for t in v if isinstance(v, list) else [v]:
                if t not in terms:
                    err(f"{where}: 語 {t} が未定義")
        if x["p"] not in preds:
            err(f"{where}: 述語 {x['p']} が未定義")

    for hid, h in hyps.items():
        triple(h, hid)
        if h["status"] not in ("supported", "partially_supported", "refuted", "untested"):
            err(f"{hid}: status が不正")
        for t in h.get("scope", []):
            if t not in terms:
                err(f"{hid}: scope の語 {t} が未定義")
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
    args = ap.parse_args()
    T, M, C = load("terms.yaml"), load("measurements.yaml"), load("claims.yaml")
    terms, preds, roles = check_terms(T)
    values, meanings = expand(M, terms, roles)
    check_claims(C, values, terms, preds)
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
        if args.show in terms:
            print(terms[args.show])
    if errors:
        print(f"検査に失敗: {len(errors)} 件")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print(f"検査に成功: 語 {len(terms)}、述語 {len(preds)}、測定値 {len(values)}、観察 {len(C['observations'])}、"
          f"仮説 {len(C['hypotheses'])}、決定 {len(C['decisions'])}、残り項目 {len(C['backlog'])}")


if __name__ == "__main__":
    main()
