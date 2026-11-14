"""spec/ の検査と値の計算。

spec/ が正本。文章（docs/, experiments/README.md）は正本ではない。

ontology.yaml  概念の体系。書き方はそのファイルの冒頭を見よ。
  検査: 表示語の一意性 / gloss を持つのは最上位の2つだけ / 動詞の式（状態の関係・両端・第三のものの種類）の一意性 /
        動詞の下位が端を狭めていること / 修飾の型（その位置に来られるか）/ 分類の軸と値 / 概念の式の一意性 /
        役割が根拠となる定義を持つこと

measurements.yaml  測定値。値は experiments/results/ から計算する。手で書いた数値は持たない。
  families: {族: {file, at, axes, where, keyset, cond, stats, meaning}}
    axes の直積で展開する。識別子は「族.軸の値....統計量」。
    stats: acc（margin>0 の割合）, both, margin（平均）, judged（judged==correct の割合）, mean（数値の平均）
    meaning: 軸の値 → ノードの識別子、または {nodes: [ノード], at: [{axis, of, value}]}。

claims.yaml
  observations: {識別子: {rel, a, b, tol}}  rel は gt/lt/ge/le/approx/eq。a, b は測定値の識別子か数値。
    すべて真でなければ検査は失敗する。
  hypotheses: {識別子: {s, p, o, scope, status, evidence, against, supersedes, note}}
    s と o はノード、p は動詞。s は p の始点、o は p の終点に来られるものでなければならない。
    status: supported / partially_supported / refuted / inconclusive（測ったが決められない）/ untested
  decisions: {識別子: {s, p, o, basis, status, supersedes, note}}  status: adopted / tentative / withdrawn
    p が is_a のときは、体系の上位・下位の関係そのもの。adopted なら、検査が構造から確かめる。
  backlog: [{id, tests, status}]  status: done / running / queued

使い方:
  python tools/check_spec.py              検査
  python tools/check_spec.py --values     測定値をすべて表示
  python tools/check_spec.py --show ID    1つの項目を、参照を展開して表示
  python tools/check_spec.py --expr ID    ノードの式を、上位をたどって表示
"""
import argparse
import collections
import itertools
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec"
RESULTS = ROOT / "experiments" / "results"
TOPS = ("continuant", "occurrent")
FUNCS = {"gt": 1, "ge": 1, "lt": 1, "le": 1, "between": 2}   # 真偽を返す範囲の判定式。値の一種
errors = []


def err(msg):
    errors.append(msg)


def load(name):
    return yaml.safe_load((SPEC / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 概念の体系
class Ontology:
    def __init__(self, O):
        self.B, self.AX, self.N = O["base"], O["axes"], O["nodes"]

    def end(self, nid, side):
        """動詞の端の種類。自分になければ上位の動詞から受け継ぐ。"""
        hops = 0
        while nid in self.N and hops < 50:
            if side in self.N[nid]:
                return self.N[nid][side]
            nid, hops = self.N[nid].get("is"), hops + 1
        return None

    def is_verb(self, nid):
        return nid in self.N and self.end(nid, "from") is not None and self.end(nid, "to") is not None

    def spot_type(self, verb, pos):
        return (self.end(verb, "new_kind") or "any") if pos == "new" else self.end(verb, pos)

    def parent(self, nid):
        n = self.N[nid]
        if "is" in n:
            return n["is"]
        if "form" in n:
            return self.spot_type(*n["form"])
        return None

    def is_a(self, x, y):
        if y == "any":
            return True
        hops = 0
        while x is not None and x != "any" and hops < 80:
            if x == y:
                return True
            x, hops = self.parent(x), hops + 1
        return False

    def overlaps(self, x, y):
        return x == "any" or self.is_a(x, y) or self.is_a(y, x)

    def base_of(self, verb):
        hops = 0
        while verb in self.N and hops < 50:
            fs = [f for k in ("holds", "before", "after") for f in self.N[verb].get(k, [])]
            if fs:
                return {re.search(r"(\w+)\(", f).group(1) for f in fs}
            verb, hops = self.N[verb].get("is"), hops + 1
        return set()

    def is_function(self, v):
        if not (isinstance(v, dict) and len(v) == 1):
            return False
        (op, arg), = v.items()
        args = arg if isinstance(arg, list) else [arg]
        return op in FUNCS and len(args) == FUNCS[op] and all(isinstance(a, (int, float)) for a in args)

    def check_value(self, axis, v, where):
        if axis not in self.AX:
            return err(f"{where}: 軸 {axis} が未定義")
        vals = self.AX[axis]["values"]
        if vals == "number":
            if not (isinstance(v, (int, float)) and not isinstance(v, bool) or self.is_function(v)):
                err(f"{where}: 軸 {axis} の値 {v} は、数でも範囲の判定式でもない")
        elif vals == "literal":
            if not isinstance(v, str):
                err(f"{where}: 軸 {axis} の値 {v} は文字列でない")
        elif v not in vals:
            err(f"{where}: 軸 {axis} に値 {v} がない")

    def check_spot(self, spec, where):
        if not (isinstance(spec, list) and len(spec) == 2):
            return err(f"{where}: of / form は [動詞, 位置] で書く")
        verb, pos = spec
        if not self.is_verb(verb):
            return err(f"{where}: {verb} は動詞でない")
        if pos not in ("from", "to", "new"):
            return err(f"{where}: 位置 {pos} は from / to / new")
        return verb, pos

    def check_state(self, vid, n):
        if ("holds" in n) == ("before" in n or "after" in n):
            err(f"{vid}: 静的（holds）か動的（before / after）のどちらかで書く")
        for key in ("holds", "before", "after"):
            for f in n.get(key, []):
                m = re.fullmatch(r"(not )?(\w+)\((\w+)(?:, (\w+))?\)", f)
                args = [a for a in m.groups()[2:] if a] if m else []
                if not m or m.group(2) not in self.B or len(args) != self.B[m.group(2)]["arity"] or any(a not in ("from", "to", "new") for a in args):
                    err(f"{vid}: 式 {f} が基礎の関係に合わない")

    def grounding(self, nid):
        return [m["with"] for m in (self.N[nid].get("mod") or [])
                if isinstance(m, dict) and m.get("of") == ["v_depend", "from"] and "with" in m and not m.get("neg")
                and self.is_a(m["with"], "definition")]

    def check(self):
        N, AX, B = self.N, self.AX, self.B
        for bid, b in B.items():
            if not b.get("laws") and not b.get("system_act") and b["arity"] != 1:
                err(f"base: {bid} に法則がない（法則を持たない基礎の関係は、体系の行為 1個だけ）")
        if sum(bool(b.get("system_act")) for b in B.values()) != 1:
            err("base: 体系そのものの行為は、ちょうど1個であること")
        for aid, a in AX.items():
            if a["from"] != "any" and a["from"] not in B:
                err(f"axes: {aid} のもとになる関係 {a['from']} が未定義")
        seen, forms = {}, {}
        for nid, n in N.items():
            ja = n.get("ja")
            if not ja or ja in seen:
                err(f"{nid}: 表示語がない、または {seen.get(ja)} と重複（同音異義）")
            seen[ja] = nid
            if nid in TOPS:
                if set(n) != {"ja", "gloss"}:
                    err(f"{nid}: 最上位は gloss だけを持つ")
                continue
            if "gloss" in n:
                err(f"{nid}: gloss を持てるのは最上位の2つだけ。式で書くこと")
            extra = set(n) - {"ja", "is", "from", "to", "new_kind", "holds", "before", "after", "form", "of", "neg", "mod", "val", "cmp", "axis"}
            if extra:
                err(f"{nid}: 知らない項目 {extra}")
            for side in ("from", "to", "new_kind"):
                if side in n and n[side] != "any" and n[side] not in N:
                    err(f"{nid}: {side} の {n[side]} が未定義")
            if "form" in n:
                self.check_spot(n["form"], nid)
                continue
            if n.get("is") not in N:
                err(f"{nid}: 上位がない、または未定義")
                continue
            if self.is_verb(nid):
                if not self.is_a(nid, "occurrent"):
                    err(f"{nid}: 動詞は生起体の下に置く")
                if self.is_verb(n["is"]):
                    for side in ("from", "to"):
                        if side in n and not self.is_a(n[side], self.end(n["is"], side)):
                            err(f"{nid}: {side} の {n[side]} は、上位の {self.end(n['is'], side)} を狭めていない")
                    if not any(k in n for k in ("from", "to", "mod")):
                        err(f"{nid}: 上位の動詞と区別する式がない")
                else:
                    self.check_state(nid, n)
            elif "of" in n:
                self.check_spot(n["of"], nid)
                if not self.is_a(nid, "specifically_dependent_continuant"):
                    err(f"{nid}: 修飾語は特定依存持続体の下に置く")
            elif not (n.get("mod") or n.get("val") or n.get("cmp")):
                err(f"{nid}: 式がない")
            for axis, v in (n.get("val") or {}).items():
                self.check_value(axis, v, f"{nid}.val")
            for i, c in enumerate(n.get("cmp") or []):
                if c.get("axis") not in AX or c.get("a") not in N or c.get("b") not in N or c.get("rel") not in ("same", "differ"):
                    err(f"{nid}.cmp[{i}]: 軸・比べる2つ・関係（same / differ）のどれかが正しくない")
            if "axis" in n:
                if n["axis"] not in AX or AX[n["axis"]]["values"] != "number":
                    err(f"{nid}: axis {n['axis']} は数の軸でない")
                if not self.is_a(nid, "quality"):
                    err(f"{nid}: axis を持てるのは質だけ")
            for i, m in enumerate(n.get("mod") or []):
                where = f"{nid}.mod[{i}]"
                if isinstance(m, str):
                    if m not in N or "of" not in N[m]:
                        err(f"{where}: {m} は修飾語でない")
                    continue
                spot = self.check_spot(m.get("of"), where)
                if not spot:
                    continue
                verb, pos = spot
                if not self.overlaps(self.spot_type(verb, pos), n["is"]) and not self.overlaps(n["is"], self.spot_type(verb, pos)):
                    err(f"{where}: {n['is']} は {verb} の {pos}（{self.spot_type(verb, pos)}）に来られない")
                if "with" in m:
                    other = {"from": "to", "to": "from"}.get(pos)
                    if other is None:
                        err(f"{where}: 位置 new には with を付けられない")
                    elif m["with"] not in N or not self.overlaps(m["with"], self.end(verb, other)):
                        err(f"{where}: {m['with']} は {verb} の {other}（{self.end(verb, other)}）に来られない")
                if set(m) - {"of", "with", "neg", "quant", "at"}:
                    err(f"{where}: 知らない項目")
                if m.get("quant") not in (None, "all", "any"):
                    err(f"{where}: quant は all か any。数は at で書く")
                for axis, v in (m.get("at") or {}).items():
                    self.check_value(axis, v, where)
                    if axis in AX and AX[axis]["from"] != "any" and AX[axis]["from"] not in self.base_of(verb):
                        err(f"{where}: 軸 {axis} は基礎の関係 {AX[axis]['from']} を抽象にしたものだが、{verb} はそれを使っていない")
            if not ("holds" in n or "before" in n):
                key = yaml.safe_dump({k: n[k] for k in ("is", "from", "to", "of", "mod", "neg", "val", "cmp", "axis") if k in n}, sort_keys=True)
                if key in forms:
                    err(f"{nid}: 式が {forms[key]} と同じ")
                forms.setdefault(key, nid)
        self.roles = [nid for nid in N if nid != "role" and "form" not in N[nid] and self.is_a(nid, "role")]
        for nid in self.roles:
            g = self.grounding(nid)
            if not g:
                err(f"{nid}: 役割だが、根拠となる定義（依存する定義）がない")
            elif all(x == "definition" for x in g):
                err(f"{nid}: 根拠となる定義が特定されていない")
        sig = collections.defaultdict(list)
        for nid, n in N.items():
            if "holds" in n or "before" in n:
                s = tuple(tuple(sorted(n.get(k, []))) for k in ("holds", "before", "after")) + (n["from"], n["to"], n.get("new_kind"))
                sig[s].append(nid)
        for ids in sig.values():
            if len(ids) > 1:
                err(f"動詞の式が同じ: {ids}")

    def expr(self, nid):
        """上位をたどって、式を並べる。"""
        out, hops = [], 0
        while nid in self.N and hops < 80:
            n = self.N[nid]
            body = {k: n[k] for k in ("from", "to", "new_kind", "holds", "before", "after", "form", "of", "neg", "mod", "val", "cmp", "axis", "gloss") if k in n}
            out.append(f"{nid}（{n['ja']}） {body}")
            nid, hops = self.parent(nid), hops + 1
        return "\n  ← ".join(out)


# ---------------------------------------------------------------- 測定値
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


def check_meaning(val, T, where):
    if isinstance(val, str):
        if val not in T.N:
            err(f"{where}: ノード {val} が未定義")
        return
    for nid in val.get("nodes", []):
        if nid not in T.N:
            err(f"{where}: ノード {nid} が未定義")
    for a in val.get("at", []):
        if a.get("of") not in T.N:
            err(f"{where}: at の of {a.get('of')} が未定義")
        T.check_value(a.get("axis"), a.get("value"), where)


def expand(M, T):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        axes = f["axes"]
        names = list(axes)
        keys = [list(axes[a]) if isinstance(axes[a], dict) else axes[a] for a in names]
        for a, mp in (f.get("meaning") or {}).items():
            for k, v in mp.items():
                check_meaning(v, T, f"measurements.{fid}.meaning.{a}.{k}")
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
                ok = (lambda x, w=want: x in w) if isinstance(want, list) else (lambda x, w=want: x == w)
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


# ---------------------------------------------------------------- 観察・仮説・決定
def val_of(x, values, where):
    if isinstance(x, (int, float)):
        return float(x)
    if x not in values:
        err(f"{where}: 測定値 {x} が未定義")
        return None
    return values[x][0]


def check_claims(C, values, T):
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

    def triple(x, where, structural_ok=False):
        ss = x["s"] if isinstance(x["s"], list) else [x["s"]]
        oo = x["o"] if isinstance(x["o"], list) else [x["o"]]
        for t in ss + oo:
            if t not in T.N:
                err(f"{where}: ノード {t} が未定義")
                return
        if x["p"] == "is_a":
            if not structural_ok:
                err(f"{where}: is_a を使えるのは決定だけ")
            elif x.get("status") == "adopted" and not all(T.is_a(s, o) for s in ss for o in oo):
                err(f"{where}: 採用済みの決定だが、体系の上で {ss} は {oo} の下位になっていない")
            return
        if not T.is_verb(x["p"]):
            return err(f"{where}: {x['p']} は動詞でない")
        for part, side, ts in (("s", "from", ss), ("o", "to", oo)):
            bound = T.end(x["p"], side)
            for t in ts:
                if not T.overlaps(t, bound):
                    err(f"{where}: {t} は動詞 {x['p']} の {side}（{bound}）に来られない")

    for hid, h in hyps.items():
        triple(h, hid)
        if h["status"] not in ("supported", "partially_supported", "refuted", "inconclusive", "untested"):
            err(f"{hid}: status が不正")
        for t in h.get("scope", []):
            if t not in T.N:
                err(f"{hid}: scope のノード {t} が未定義")
        for k in ("evidence", "against"):
            for r in h.get(k, []):
                if r not in obs:
                    err(f"{hid}: {k} の観察 {r} が未定義")
        for r in h.get("supersedes", []):
            if r not in hyps:
                err(f"{hid}: supersedes の仮説 {r} が未定義")
        if h["status"] in ("supported", "partially_supported", "refuted", "inconclusive") and not (h.get("evidence") or h.get("against")):
            err(f"{hid}: 根拠の観察がない")
    for did, d in decs.items():
        if d["status"] not in ("adopted", "tentative", "withdrawn"):
            err(f"{did}: status が不正")
        triple(d, did, structural_ok=True)
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
    T = Ontology(load("ontology.yaml"))
    T.check()
    M, C = load("measurements.yaml"), load("claims.yaml")
    values, meanings = expand(M, T)
    check_claims(C, values, T)
    if args.expr:
        print(T.expr(args.expr))
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
    if errors:
        print(f"検査に失敗: {len(errors)} 件")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    N = T.N
    verbs = sum(1 for n in N.values() if "holds" in n or "before" in n)
    print(f"検査に成功: ノード {len(N)}（うち動詞の語根 {verbs}、役割 {len(T.roles)}）、基礎の関係 {len(T.B)}、分類の軸 {len(T.AX)}、"
          f"測定値 {len(values)}、観察 {len(C['observations'])}、仮説 {len(C['hypotheses'])}、決定 {len(C['decisions'])}、残り項目 {len(C['backlog'])}")


if __name__ == "__main__":
    main()
