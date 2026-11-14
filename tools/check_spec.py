"""spec/ の検査と値の計算。

spec/ が正本。文章（docs/, experiments/README.md）は正本ではない。

ontology.yaml  概念の体系。3本のツリーからなる。
  entities         実体のツリー。最上位は BFO の continuant と occurrent。
                   原始概念はこの2つだけで、gloss を持てるのもこの2つだけ。
                   他のすべての実体は {ja, is: 上位, where: {軸: 値}} という概念式で記述する。
  relations        関係のツリー。原子関係は from_to（向きを持つ結び付き）だけ。
                   他のすべての関係は {ja, is: 上位, from, to, where: {軸: 値}, def} という式で記述する。
                   from と to は両端の種類で、上位から受け継ぐ。any はすべての実体、value は分類の値、number は数。
                   def は、式だけで書けない合成関係に添える述語論理の定義。
                   def は述語論理の式。使える語は logic と、3本のツリーの識別子と、1文字の変数だけ。
  classifications  分類のツリー。{軸: {ja, is, from: 関係, values | values_from | number}}。
                   of: relation の軸は関係を分類する軸で、値は述語論理の法則（law）を持てる。
  検査: 表示語（ja）の一意性、上位・軸・値の解決、軸のもとになる関係の from との型の一致、
        実体と関係それぞれの式の正規形の一意性、関係の端が上位を狭めていること、def と law の語の解決。

measurements.yaml  測定値。値は experiments/results/ から計算する。手で書いた数値は持たない。
  families: {族: {file, at, axes, where, keyset, cond, stats, meaning}}
    axes の直積で展開する。識別子は「族.軸の値....統計量」。
    stats: acc（margin>0 の割合）, both, margin（平均）, judged（judged==correct の割合）, mean（数値の平均）
    meaning: 軸の値 → 実体の識別子、または {分類の軸: 値}。

claims.yaml
  observations: {識別子: {rel, a, b, tol}}  rel は gt/lt/ge/le/approx/eq。a, b は測定値の識別子か数値。
    すべて真でなければ検査は失敗する。
  hypotheses: {識別子: {s, p, o, scope, status, evidence, against, supersedes, note}}
    s と o は実体、p は関係。s は p の from、o は p の to の下位でなければならない。
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


KEYWORDS = ("any", "value", "number")


def is_a(E, x, y):
    """実体 x が y と同じか、y の下位か。any はすべての実体。"""
    if y == "any":
        return True
    hops = 0
    while x is not None and hops < 100:
        if x == y:
            return True
        x, hops = E.get(x, {}).get("is"), hops + 1
    return False


def end(R, rid, side):
    """関係の端（from / to）の種類。自分になければ上位から受け継ぐ。"""
    hops = 0
    while rid in R and hops < 100:
        if side in R[rid]:
            return R[rid][side]
        rid, hops = R[rid].get("is"), hops + 1
    return None


def valid_value(A, E, R, axis, val, where, for_relation=False):
    a = A.get(axis)
    if a is None or axis == "classification":
        err(f"{where}: 軸 {axis} が未定義")
        return
    if bool(a.get("of") == "relation") != for_relation:
        err(f"{where}: 軸 {axis} は{'関係' if a.get('of') == 'relation' else '実体'}を分類する軸である")
        return
    for v in val if isinstance(val, list) else [val]:
        if "values" in a:
            if v not in a["values"]:
                err(f"{where}: 軸 {axis} に値 {v} がない")
        elif "values_from" in a:
            src = a["values_from"]
            ok = (v in R) if src == "relation" else (v in A and v != "classification") if src == "classification" else (v in E and is_a(E, v, src))
            if not ok:
                err(f"{where}: 軸 {axis} の値 {v} は {src} でない")
        elif a.get("number"):
            if not isinstance(v, (int, float)):
                err(f"{where}: 軸 {axis} の値 {v} は数でない")


def _fmt(v):
    return "+".join(sorted(map(str, v))) if isinstance(v, list) else str(v)


def canonical(E, eid):
    e = E[eid]
    if "where" not in e:
        return eid
    inner = ", ".join(f"{k}={_fmt(e['where'][k])}" for k in sorted(e["where"]))
    return f"{canonical(E, e['is'])}[{inner}]"


def canonical_rel(R, rid):
    r = R[rid]
    if r.get("primitive") or rid == "relation":
        return rid
    parts = [f"{k}={r[k]}" for k in ("from", "to") if k in r]
    parts += [f"{k}={_fmt(r['where'][k])}" for k in sorted(r.get("where") or {})]
    return f"{canonical_rel(R, r['is'])}[{', '.join(parts)}]" if parts else canonical_rel(R, r["is"])


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
            if key in ids or key in KEYWORDS:
                err(f"識別子 {key} が {ids.get(key, '予約語')} と {kind} で重複")
            ids[key] = kind
    allowed = set(logic["connectives"]) | set(logic["primitive_predicates"]) | set(E) | set(R) | set(A)

    def formula(text, where, extra=()):
        for tok in re.findall(r"[A-Za-z_]+", text):
            if len(tok) > 1 and tok not in allowed and tok not in extra:
                err(f"{where}: 式の語 {tok} が未定義")

    # 分類
    for aid, a in A.items():
        label("classifications", aid, a.get("ja"))
        if aid == "classification":
            continue
        if "gloss" in a:
            err(f"classifications: {aid} が gloss を持つ（gloss を持てるのは最上位 classification だけ）")
        if a.get("is") not in A:
            err(f"classifications: {aid} の上位 {a.get('is')} が未定義")
        if a.get("from") not in R:
            err(f"classifications: {aid} のもとになる関係 {a.get('from')} が未定義")
        if sum(k in a for k in ("values", "values_from", "number")) != 1:
            err(f"classifications: {aid} は values / values_from / number のどれか1つを持つこと")
        for vid, v in (a.get("values") or {}).items():
            label(f"classifications.{aid}", vid, v.get("ja"))
            if "law" in v:
                if a.get("of") != "relation":
                    err(f"classifications: {aid}.{vid} の law は、関係を分類する軸でしか持てない")
                formula(v["law"], f"classifications.{aid}.{vid}", ("r",))
        if "law" in a:
            formula(a["law"], f"classifications.{aid}", ("r", "V"))
        src = a.get("values_from")
        if src is not None and src not in ("any", "relation", "classification") and src not in E:
            err(f"classifications: {aid} の values_from {src} が未定義")
    # 実体。原始概念は continuant と occurrent だけ
    TOPS = ("continuant", "occurrent")
    forms = {}
    for eid, e in E.items():
        label("entities", eid, e.get("ja"))
        if eid in TOPS:
            if "gloss" not in e or "is" in e or "where" in e:
                err(f"entities: 最上位 {eid} は gloss だけを持つこと")
            continue
        if "gloss" in e:
            err(f"entities: {eid} が gloss を持つ（gloss を持てるのは {TOPS} だけ。概念式で記述すること）")
        if e.get("is") not in E:
            err(f"entities: {eid} の上位 {e.get('is')} が未定義")
            continue
        if not e.get("where"):
            err(f"entities: {eid} に概念式（where）がない")
        for axis, val in (e.get("where") or {}).items():
            valid_value(A, E, R, axis, val, f"entities.{eid}")
            frm = end(R, A.get(axis, {}).get("from"), "from")
            if frm is not None and frm not in KEYWORDS and not is_a(E, e["is"], frm):
                err(f"entities: {eid} は軸 {axis} を使えない（上位 {e['is']} が、関係 {A[axis]['from']} の from {frm} の下位でない）")
    for eid, e in E.items():
        if eid not in TOPS and e.get("is") in E and e.get("where"):
            f = canonical(E, eid)
            if f in forms:
                err(f"entities: {eid} と {forms[f]} の概念式が同じ（{f}）")
            forms[f] = eid
    # 関係。原子関係は from_to だけ
    rforms = {}
    for rid, r in R.items():
        label("relations", rid, r.get("ja"))
        if rid == "relation":
            continue
        if "gloss" in r:
            err(f"relations: {rid} が gloss を持つ（gloss を持てるのは最上位 relation だけ）")
        if r.get("is") not in R:
            err(f"relations: {rid} の上位 {r.get('is')} が未定義")
            continue
        if r.get("primitive"):
            if rid != "from_to":
                err(f"relations: {rid} が原子関係になっている（原子関係は from_to だけ）")
            continue
        if not any(k in r for k in ("where", "def", "from", "to")):
            err(f"relations: {rid} に式も定義もない（上位と区別できない）")
        for side in ("from", "to"):
            if side in r:
                mine, up = r[side], end(R, r["is"], side)
                if mine not in KEYWORDS and mine not in E:
                    err(f"relations: {rid} の {side} {mine} が未定義")
                elif up not in (None, "any") and mine != up and not (mine in E and up in E and is_a(E, mine, up)):
                    err(f"relations: {rid} の {side} {mine} は、上位の {side} {up} を狭めていない")
        for axis, val in (r.get("where") or {}).items():
            valid_value(A, E, R, axis, val, f"relations.{rid}", for_relation=True)
        if "def" in r:
            formula(r["def"], f"relations.{rid}")
        else:
            f = canonical_rel(R, rid)
            if f in rforms:
                err(f"relations: {rid} と {rforms[f]} の式が同じ（{f}）")
            rforms[f] = rid
    if not R.get("from_to", {}).get("primitive"):
        err("relations: 原子関係 from_to がない")
    return E, R, A


def resolve_meaning(val, E, A, R, where):
    if isinstance(val, dict):
        for axis, v in val.items():
            valid_value(A, E, R, axis, v, where)
    elif isinstance(val, list):
        for v in val:
            resolve_meaning(v, E, A, R, where)
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


def expand(M, E, A, R):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        axes = f["axes"]
        names = list(axes)
        keys = [list(axes[a]) if isinstance(axes[a], dict) else axes[a] for a in names]
        for a, mp in (f.get("meaning") or {}).items():
            for k, v in mp.items():
                resolve_meaning(v, E, A, R, f"measurements.{fid}.meaning.{a}.{k}")
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
        if x["p"] not in R or x["p"] in ("relation", "from_to"):
            err(f"{where}: 関係 {x['p']} が未定義")
            return
        for part, side in (("s", "from"), ("o", "to")):
            bound = end(R, x["p"], side)
            v = x[part]
            for t in v if isinstance(v, list) else [v]:
                if t not in E:
                    err(f"{where}: 実体 {t} が未定義")
                elif bound in ("value", "number") or not is_a(E, t, bound):
                    err(f"{where}: {t} は関係 {x['p']} の {side} {bound} の下位でない")

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
    values, meanings = expand(M, E, A, R)
    check_claims(C, values, E, R)
    if args.expr:
        print(canonical(E, args.expr) if args.expr in E else canonical_rel(R, args.expr))
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
