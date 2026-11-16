"""体系の型検査と値の計算（stage0。Python による最初の実装）。

cscl.yaml の範囲のファイル（cscl/library/, exp/src/）が正本。自然言語の文章は正本ではない。

ontology.yaml  概念の体系。書き方はそのファイルの冒頭を見よ。
  検査: 表示語の一意性 / gloss を持つのは最上位の2つだけ / 動詞の式（状態の関係・両端・第三のものの種類）の一意性 /
        動詞の下位が端を狭めていること / 修飾の型（その位置に来られるか）/ 分類の軸と値 / 概念の式の一意性 /
        役割が根拠となる定義を持つこと
  grammar: 体系が、自分の書き方について述べる部分。文法の語は、すべてノードの識別子。節ごとに、使える語を並べる。
        検査は、ここに書かれた語だけを文法の語として受け付ける。logic は述語論理の語で、体系の中では定義しない。

exp.yaml  領域 exp。種類（nodes）、個体（individuals）、事実（facts）を持つ。
  個体は is で種類に1つだけ属する。仮説・決定・残り項目は、状態を表す下位の種類に属する（is: hyp_supported など）。
  事実は動詞の個体で、位置に名前を付けて書く: {is: 動詞, from: 始点, to: 終点}。個体は、動詞のその位置の種類に
  当たらなければならない。文が述べる中身は、同じ形を v_refer の終点に置く（主張ではない）。
  検査は、事実を個体ごとに集めた形で読む。
  測定値: 族ごとに、軸（axis）の直積で展開する。識別子は「族.軸の値....指標」。値は結果ファイルから計算する。
  観察・仮説・決定: どれも「s が、p という関係で、o に」という文。
    観察の s と o は測定値（o は数でもよい）、p は大きさを比べる動詞。真偽は、動詞の式（後ろにある、の成立と不成立）を
    数に当てはめて決める。すべて真でなければ検査は失敗する。
    仮説と決定の s と o はノード、p は動詞。s は p の始点、o は p の終点に来られるものでなければならない。
    仮説の status は、根拠（evidence, against）の有無から決まる。決まり方は、状態のノードの式から読み取る。
    決定の p が is_a のときは、体系の上位・下位の関係そのもの。採用済みなら、検査が構造から確かめる。

使い方:
  python cscl/bootstrap/type_checker/type_checker.py              検査
  python cscl/bootstrap/type_checker/type_checker.py --values     測定値をすべて表示
  python cscl/bootstrap/type_checker/type_checker.py --show ID    1つの項目を、参照を展開して表示
  python cscl/bootstrap/type_checker/type_checker.py --expr ID    ノードの式を、上位をたどって表示
"""
import argparse
import collections
import copy
import itertools
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]   # リポジトリの根。cscl/bootstrap/type_checker/ の3つ上
SPEC = ROOT   # 体系のファイルの名前は、根からの相対で書く（cscl.yaml と同じ）
CONFIG = ROOT / "cscl.yaml"   # 体系の範囲（tsconfig に当たる）


def root_name():
    """本体のファイル（リポジトリの根からの相対）。"""
    return str((ROOT / config()["root"]).resolve().relative_to(SPEC))


def config():
    return yload(CONFIG.read_text(encoding="utf-8"))


def in_scope(key):
    """cscl.yaml の範囲（include から exclude を除いたもの）にあるファイル。"""
    c = config()
    excl = {p.resolve() for g in c.get("exclude") or [] for p in ROOT.glob(g)}
    return sorted({p.resolve() for g in c.get(key) or [] for p in ROOT.glob(g)} - excl)
RESULTS = ROOT / yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["results"]
TOPS = ("continuant", "occurrent")
errors = []


def atom(f):
    """状態の関係の型（{is: 基礎の関係, from: 位置, to: 位置, neg: 否定}）を (否定, 関係, 位置の並び) に直す。"""
    if not isinstance(f, dict):
        return False, None, ()
    return bool(f.get("neg")), f.get("is"), tuple(f[k] for k in ("from", "to") if k in f)


def short(w):
    return w.split(".")[-1] if isinstance(w, str) else w


def err(msg):
    errors.append(msg)


_FAST = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class _Unique(_FAST):
    """同じ対応表の中で、同じ語を2度書いたらエラーにする。"""


def _mapping(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=True)
        if isinstance(key, (str, int, bool)) and key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"識別子 {key} が重複している", k.start_mark)
        if isinstance(key, (str, int, bool)):
            seen.add(key)
    return yaml.constructor.SafeConstructor.construct_mapping(loader, node, deep)


_Unique.construct_mapping = _mapping


_YCACHE = {}


def yload(src):
    """YAML を読む（C の読み込み）。同じ中身は一度だけ読み、写しを返す。"""
    text = src.read() if hasattr(src, "read") else src
    if text not in _YCACHE:
        _YCACHE[text] = yaml.load(text, Loader=_FAST)
    return copy.deepcopy(_YCACHE[text])


def load(name):
    O = yaml.load((SPEC / name).read_text(encoding="utf-8"), Loader=_Unique)
    if name == root_name():
        for p in in_scope("std"):   # 標準の語彙。axiom と同じ名前空間に、種類・個体・事実を加える
            D = yaml.load(p.read_text(encoding="utf-8"), Loader=_Unique) or {}
            for sec in ("nodes", "individuals"):
                O.setdefault(sec, {})
                for k, v in (D.get(sec) or {}).items():
                    if k in O[sec]:
                        err(f"{p.relative_to(ROOT)}: {k} は axiom にもある")
                    O[sec][k] = v
            O["facts"] = (O.get("facts") or []) + (D.get("facts") or [])
        core_sections(O)
    return O


def core_sections(O):
    """領域と法則は、ontology.yaml の個体と事実で書く。検査と実行器が読む形に並べる（中身の検査は、ほかと同じく gather が行う）:
    domains: {領域: {display, uses: [使う領域]}}、laws: {法則: {kind, display, assume, derive, require, govern}}。"""
    I, F = O.get("individuals") or {}, O.get("facts") or []
    O["domains"] = {i: {"display": x.get("display"), "uses": []} for i, x in I.items() if x.get("is") == "domain"}
    O["laws"] = {i: {"kind": x["is"], "display": x.get("display"), "assume": [], "derive": [], "require": [], "govern": []}
                 for i, x in I.items() if x.get("is") in ("law_rule", "law_given")}
    key = {"v_assume": "assume", "v_derive": "derive", "v_require": "require", "v_govern": "govern"}
    for f in F:
        if not isinstance(f, dict):
            continue
        if f.get("is") == "v_use" and f.get("from") in O["domains"]:
            O["domains"][f["from"]]["uses"].append(f.get("to"))
        elif f.get("is") in key and f.get("from") in O["laws"]:
            t = f.get("to")
            if isinstance(t, dict):   # 規則の中の true / false は語
                t = {k: ("true" if v is True else "false" if v is False else v) if k in ("from", "to") else v for k, v in t.items()}
            O["laws"][f["from"]][key[f["is"]]].append(t)


KINDS = {"measurement_family": "families", "observation": "observations", "hypothesis": "hypotheses",
         "decision": "decisions", "backlog_item": "backlog"}   # この検査が中身を確かめる種類


LITERAL = {"display", "holds", "pre", "post", "result_file", "row_collection", "row_filter", "pattern", "condition_entry", "passage", "val"}


def qualify(x, local, dom):
    """領域のファイルの中で、領域を書かずに書かれた識別子を「領域.名前」に直す。文字列そのものを値とする項目は直さない。"""
    if isinstance(x, str):
        if x.startswith("axiom."):   # 領域 axiom の識別子を、領域を書いて明示したもの（同じ名前が自分の領域にあるとき）
            return x[len("axiom."):]
        return f"{dom}.{x}" if x in local else x
    if isinstance(x, list):
        return [qualify(v, local, dom) for v in x]
    if isinstance(x, dict):
        return {k: (v if k in LITERAL else qualify(v, local, dom)) for k, v in x.items()}
    return x


def merge_domain(name, O):
    """領域のファイルを読み、そのノードを体系に加える。領域のファイルは、その領域の種類（nodes）と個体（individuals）を持つ。"""
    D = load(name)
    dom = D.get("domain")
    if dom not in O["domains"]:
        err(f"{name}: 領域 {dom} が domains に書かれていない")
    local = set(D.get("nodes") or {})
    D.setdefault("individuals", {})
    for nid, n in (D.get("nodes") or {}).items():
        O["nodes"][f"{dom}.{nid}"] = qualify(n, local, dom)
    D["individuals"] = {iid: qualify(x, local, dom) for iid, x in D["individuals"].items()}
    for iid, x in D["individuals"].items():
        if set(x) - {"is", "display", "val"}:
            err(f"{name} {iid}: 個体には is, display, val だけを書く。関係は facts に書く")
    D["_local"] = local
    return D


MANY = {"scope", "evidence", "against", "limitation", "supersedes", "basis", "tests", "metric", "any", "domain", "premise", "derived", "required", "information_entity"}   # 検査が並びとして読む関係


def is_kind_fact(f, T, dom, I):
    """位置がすべて種類（個体でなく、動詞でないノード）の事実。閉世界では、種類についての文は「その種類のすべてについて」と読む。"""
    ps = [f.get(p) for p in ("from", "to", "new") if p in f]
    return "at" not in f and len(ps) >= 2 and all(
        isinstance(x, str) and x not in I and x not in T.I and (T.resolve(x, dom) or x) in T.N
        and not T.is_verb(T.resolve(x, dom) or x) for x in ps)


def collect_kind_facts(T):
    """種類どうしの事実を、すべての領域から集めて T.KF に置く。型を確かめる。否定は書かせない
    （閉世界では書かれていない文は成り立たない。否定は法則の制約（v_require）で書く）。"""
    T.KF, T.COLL = [], {}
    for name, dom in [(root_name(), "axiom")] + [(n, d) for d, n in domain_files().items()]:   # 種類の集まり（2階）
        for f in (yload((SPEC / name).read_text(encoding="utf-8")).get("facts") or []):
            if isinstance(f, dict) and f.get("is") == "v_collect" and f.get("from") in T.I:
                k = T.resolve(f.get("to"), dom) if isinstance(f.get("to"), str) else None
                if k not in T.N or T.is_verb(k):
                    err(f"{name} の事実 {f}: 集まりの成員は種類（ノード）")
                else:
                    T.COLL[f["from"]] = k   # 段の検査は法則 collection_level（規則）
    for name, dom in [(root_name(), "axiom")] + [(n, d) for d, n in domain_files().items()]:
        D = yload((SPEC / name).read_text(encoding="utf-8"))
        for i, f in enumerate(D.get("facts") or []):
            if not isinstance(f, dict) or not isinstance(f.get("is"), str) or not is_kind_fact(f, T, dom, D.get("individuals") or {}):
                continue
            where = f"{name} facts[{i}]"
            verb = T.resolve(f["is"], dom)
            if not T.is_verb(verb):
                err(f"{where}: {f['is']} は動詞でない")
                continue
            if f.get("neg"):
                err(f"{where}: 種類どうしの事実は否定にしない（閉世界。否定は法則の制約で書く）")
                continue
            x = {p: T.resolve(f[p], dom) or f[p] for p in ("from", "to", "new") if p in f}
            for p, k in x.items():
                if not T.is_a(k, T.spot_type(verb, p)):
                    err(f"{where}: {p} の種類 {k} が、動詞 {verb} のその位置（{T.spot_type(verb, p)}）に当たらない")
            T.KF.append((verb, x))


def gather(D, T, name):
    """事実を、個体ごとに集める。検査は、集めた形（個体 → {関係の名: 値}）を読む。
    事実は動詞の個体: {is: 動詞, from, to, new, at, neg}。位置には名前を付ける。
    - 個体が、動詞のある位置の種類に当たるとき、その個体についての事実。関係の名は、もう一方の位置の種類。
    - at を持つ事実は、始点の種類のものがいくつ終点の部分になるか（個数）。関係の名は、始点の種類。
    - v_refer の終点が事実の形をしていれば、それは文が述べる中身（主張ではない）。s, p, o, tolerance として読む。"""
    dom, local, I = D["domain"], D["_local"], D["individuals"]
    q = lambda v: qualify(v, local, dom)
    for i, f in enumerate(D.get("facts") or []):
        where = f"{name} facts[{i}]"
        if not isinstance(f, dict) or set(f) - set(T.G["facts"]) or "is" not in f:
            err(f"{where}: 事実は {{is: 動詞, from: 始点, to: 終点}} で書き、語は grammar.facts のものだけ")
            continue
        verb = q(f["is"])
        if is_kind_fact(f, T, dom, I):
            continue   # 種類どうしの事実。collect_kind_facts が読む
        if not T.is_verb(verb):
            err(f"{where}: {f['is']} は動詞でない")
            continue
        if "at" in f:
            subj, rel, val = f.get("to"), f.get("from"), (f["at"] or {}).get("count")
            if subj in I:
                I[subj].setdefault("_at", []).extend({"axis": a, "s": q(rel), "o": o} for a, o in (f["at"] or {}).items())
            if val is None:
                continue
        elif verb == "v_refer" and isinstance(f.get("to"), dict):
            P = f["to"]
            subj = f.get("from")
            if subj in I:
                I[subj]["s"], I[subj]["o"] = q(P.get("from")), q(P.get("to"))
                I[subj]["p"] = "is_a" if P.get("is") == "extends" else q(P.get("is"))
                if "new" in P:
                    I[subj]["tolerance"] = P["new"]
            else:
                err(f"{where}: 始点 {subj} が個体でない")
            continue
        else:
            sides = [pos for pos in ("from", "to") if isinstance(f.get(pos), str) and f[pos] in I
                     and T.is_a(T.I.get(f[pos]), T.end(verb, pos))]
            sides = sides[:1]   # 両方の位置に個体があれば、始点についての事実
            if not sides:
                err(f"{where}: 動詞 {verb} のどちらの位置にも、その位置の種類に当たる個体がない（または両方にある）")
                continue
            other = {"from": "to", "to": "from"}[sides[0]]
            subj, rel = f[sides[0]], short(T.end(verb, other))
            ov = f.get(other)
            if isinstance(ov, str) and ov in I and not T.occupies(T.I.get(ov), T.end(verb, other), verb):
                err(f"{where}: {other} の {ov} は、動詞 {verb} のその位置（{T.end(verb, other)}）を占められない")
                continue
            val = f.get(other) if rel in LITERAL else q(f.get(other))
        if subj not in I:
            err(f"{where}: 始点 {subj} が個体でない")
            continue
        I[subj].setdefault(rel, []).append(val)
    for subj, x in I.items():
        for rel, vs in list(x.items()):
            if isinstance(vs, list) and rel not in T.G["individuals"] and rel not in ("o", "_at"):
                if rel not in MANY and len(vs) > 1:
                    err(f"{name} {subj}: 関係 {rel} の事実が2つ以上ある")
                x[rel] = vs if rel in MANY else vs[0]


def axes_of(I, T):
    """測定の族の軸と軸の値（個体）を、族ごとの形に並べる。expand が読む形:
    axis: {軸の字: [値の字] | {値の字: 書き方}}、meaning: {軸の字: {値の字: 指すもの | {identifier, value}}}。
    並びは、個体を書いた順。"""
    kind = lambda x: x.get("is")
    for aid, a in I.items():
        if not T.is_a(kind(a), "family_axis"):
            continue
        fam = I.get(a.get("measurement_family"))
        if fam is None or not T.is_a(kind(fam), "measurement_family"):
            err(f"exp {aid}: 測定の族の軸が、どの族の部分でもない")
            continue
        if "pattern" in a:
            fam["row_keys"] = {"axis": label(a), "pattern": a["pattern"]}
        vals = [(vid, v) for vid, v in I.items() if T.is_a(kind(v), "axis_value") and v.get("family_axis") == aid]
        if not vals:
            err(f"exp {aid}: 測定の族の軸に、値がない")
        label = lambda x: (x.get("val") or {}).get("text")
        al = label(a)
        if any("passage" in v for _, v in vals):
            fam.setdefault("axis", {})[al] = {label(v): v.get("passage", label(v)) for _, v in vals}
        else:
            fam.setdefault("axis", {})[al] = [label(v) for _, v in vals]
        for vid, v in vals:
            ids, at = v.get("any", []), v.get("_at", [])
            if isinstance(ids, str):
                ids = [ids]
            if ids or at:
                m = ids[0] if len(ids) == 1 and not at else {"identifier": ids} | ({"value": at} if at else {})
                fam.setdefault("meaning", {}).setdefault(al, {})[label(v)] = m


def load_domain(name, D, T):
    """領域の個体を種類ごとに分ける。個体についての関係は、事実（動詞の個体）から集める（gather）。
    仮説・決定・残り項目の個体は、状態を表す下位の種類に属する。この検査が中身を確かめない種類の個体は、種類と項目だけを確かめる。"""
    gather(D, T, name)
    axes_of(D["individuals"], T)
    for k in D:
        if k not in T.G["domain"] and k != "_local":
            err(f"{name}: 語 {k} が、grammar.domain に書かれていない")
    out = {sect: {} for sect in KINDS.values()}
    for iid, x in D["individuals"].items():
        if iid in T.N or T.resolve(iid, D["domain"]):
            err(f"{name} {iid}: 個体の識別子が、ノードの識別子と重なっている")
        kind = x.pop("is", None)
        if kind not in T.N:
            err(f"{name} {iid}: 種類 {kind} がノードでない")
            continue
        for ax, v in (x.get("val") or {}).items():
            T.check_value(ax, v, f"{name} {iid}")
        T.check_counts(kind, {f: v for f, v in x.items() if f not in T.G["individuals"] and f != "_at"}, f"{name} {iid}")
        base = [k for k in KINDS if T.is_a(kind, k)]
        if not base:
            continue
        if base[0] in ("hypothesis", "decision", "backlog_item"):
            x["status"] = kind
        out[KINDS[base[0]]][iid] = x
    out["backlog"] = [{"identifier": k, **v} for k, v in out["backlog"].items()]
    return {"families": out.pop("families")}, out


# ---------------------------------------------------------------- 規則
def law_rules(O):
    return [(lid, l) for lid, l in O["laws"].items() if l["kind"] == "law_rule"]


def variables(O):
    return {i for i, x in (O.get("individuals") or {}).items() if x.get("is") == "variable"}


class Facts:
    """関係ごとの文の集まり。位置ごとの索引を持つ。"""
    def __init__(self, items=()):
        self.by, self.idx = collections.defaultdict(set), collections.defaultdict(set)
        for rel, xs in items:
            self.add(rel, xs)

    def add(self, rel, xs):
        if xs in self.by[rel]:
            return False
        self.by[rel].add(xs)
        for i, x in enumerate(xs):
            self.idx[(rel, i, x)].add(xs)
        return True

    def has(self, rel, xs):
        return xs in self.by.get(rel, ())

    def find(self, rel, pat):
        """pat: 位置ごとの値か None。"""
        cands = None
        for i, x in enumerate(pat):
            if x is not None:
                c = self.idx.get((rel, i, x), set())
                cands = c if cands is None or len(c) < len(cands) else cands
        for xs in (self.by.get(rel, ()) if cands is None else list(cands)):
            if len(xs) == len(pat) and all(p is None or p == x for p, x in zip(pat, xs)):
                yield xs


def compile_atoms(atoms):
    """前提の並びを (否定, 関係, 位置の並び) に直し、肯定を先に並べる。"""
    return sorted((atom(f) for f in atoms), key=lambda a: a[0])


def matches(atoms, F, V, b=None):
    """前提の並びを満たす束縛を挙げる。肯定の前提を先に、否定の前提をあとに見る。
    否定の前提は、書かれていない（導かれていない）こと。束縛されていない変数は「どれでも」と読む。same は名前が同じこと。"""
    yield from _match(compile_atoms(atoms), 0, F, V, dict(b or {}))


def _match(cs, i, F, V, b, first=None):
    """cs[i:] を満たす束縛。first があれば、その位置の前提は first（増えた文）の中から探す。"""
    if i == len(cs):
        yield b
        return
    neg, rel, args = cs[i]
    if rel == "same":
        x, y = (b.get(a) if a in V else a for a in args)
        if neg:
            if x is None or y is None or x != y:
                yield from _match(cs, i + 1, F, V, b, first)
        elif x is not None and y is not None:
            if x == y:
                yield from _match(cs, i + 1, F, V, b, first)
        elif x is not None or y is not None:
            known = x if x is not None else y
            yield from _match(cs, i + 1, F, V, b | {a: known for a in args if a in V and a not in b}, first)
        return
    pat = tuple(b.get(a) if a in V else a for a in args)
    src = first[1] if first is not None and first[0] == i else F
    if neg:
        if next(F.find(rel, pat), None) is None:
            yield from _match(cs, i + 1, F, V, b, first)
        return
    for xs in src.find(rel, pat):
        nb, ok = dict(b), True
        for a, x in zip(args, xs):
            if a in V:
                if nb.get(a, x) != x:
                    ok = False
                    break
                nb[a] = x
        if ok:
            yield from _match(cs, i + 1, F, V, nb, first)


def strata(rules):
    """導く関係を、否定の前提に使う関係より後の層に置く。層に分けられなければ、その関係を返す。"""
    heads = {atom(f)[1] for _, l in rules for f in l["derive"]}
    st = {h: 0 for h in heads}
    for _ in range(len(heads) + 2):
        changed = False
        for _, l in rules:
            for f in l["derive"]:
                h = atom(f)[1]
                for p in l["assume"]:
                    neg, r, _ = atom(p)
                    if r in st:
                        need = st[r] + (1 if neg else 0)
                        if need > st[h]:
                            st[h], changed = need, True
        if not changed:
            return st, None
    return st, [h for h in st if st[h] > len(heads)]


def evaluate(rules, F, V):
    """導く文を層ごとに足して閉じ、求める文が成り立たない束縛を、(法則, 束縛, 求める文) で返す。"""
    st, bad = strata(rules)
    if bad:
        return [("strata", {}, f"否定を通して循環している関係 {bad}")]
    for level in sorted(set(st.values())):
        layer = [(lid, compile_atoms(l["assume"]), [atom(f)[1:] for f in l["derive"]])
                 for lid, l in rules if l["derive"] and all(st[atom(f)[1]] == level for f in l["derive"])]
        heads = lambda cs, b, outs: [(rel, tuple(b.get(a, a) if a in V else a for a in args)) for rel, args in outs]
        delta = Facts()   # 増えた文だけを使う（semi-naive）。最初の一回は全部で当てる
        for _, cs, outs in layer:
            for b in list(_match(cs, 0, F, V, {})):
                for rel, xs in heads(cs, b, outs):
                    if not F.has(rel, xs):
                        delta.add(rel, xs)
        while delta.by:
            for rel, xss in delta.by.items():
                for xs in xss:
                    F.add(rel, xs)
            new = Facts()
            for _, cs, outs in layer:
                for i, (neg, rel, _) in enumerate(cs):
                    if neg or rel == "same" or rel not in delta.by:
                        continue
                    for b in list(_match(cs, 0, F, V, {}, (i, delta))):
                        for r, xs in heads(cs, b, outs):
                            if not F.has(r, xs):
                                new.add(r, xs)
            delta = new
    out = []
    for lid, l in rules:
        for f in l["require"]:
            for b in matches(l["assume"], F, V):
                if next(matches([f], F, V, b), None) is None:
                    out.append((lid, b, f))
    return out


# ---------------------------------------------------------------- 概念の体系
# 法則のうち、この検査が当てはめるもの / 実行の検査（cscl/bootstrap/runtime/runtime.py）が当てはめるもの
# 規則で書いた法則（law_rule）は、実行の検査がその規則を読んで当てはめる。ここには、意味を検査が与える法則（law_given）だけを挙げる。
LAWS_HERE = {"part_fact_direction", "part_display_explicit"}
LAWS_RUN = {"unique_names", "step", "frame", "halt"}


class Ontology:
    def __init__(self, O):
        self.O = O
        self.B, self.AX, self.N, self.G = O["base"], O["axes"], O["nodes"], O["grammar"]
        self.I, self.Idom, self.Isubj = {}, None, {}   # 個体の識別子 → 種類、個体が書かれた領域
        for nid, n in self.N.items():  # mod は単一。中では並びとして扱う（限定の数は法則 single の規則が確かめる）
            if isinstance(n.get("extends"), list):
                err(f"{nid}: extends は並べない。AND は「属する」（is）で限定して書く")
                n["extends"] = n["extends"][0]
            if "mod" in n:
                if isinstance(n["mod"], list):
                    err(f"{nid}: mod は並べない。限定は1つだけ")
                else:
                    n["mod"] = [n["mod"]]
        # 真偽を返す範囲の判定式。値の一種。gt などは文法の function、between は述語論理の語
        self.funcs = {op: 1 for op in self.G["function"]} | ({"between": 2} if "between" in self.G["logic"] else {})

    def check_grammar(self):
        """文法の語が、体系のノードに当たっていること。体系の各節が、文法に書かれた語だけを使っていること。"""
        G = self.G
        for sect, words in G.items():
            if sect not in G["grammar"]:
                err(f"grammar: 節 {sect} が、grammar.grammar に書かれていない")
            for w in words:
                if self.resolve(w, sect) is None:
                    err(f"grammar.{sect}: 語 {w} がノードになっていない")
        L = self.O["laws"]
        for lid, l in L.items():
            where = f"法則 {lid}"
            if l["kind"] == "law_rule":
                if not l["assume"] or not (l["derive"] or l["require"]) or l["govern"]:
                    err(f"{where}: 規則で書いた法則は、前提と、導く文か求める文を持ち、掛かる節を持たない")
                V = variables(self.O)
                rels = set(self.B) | set(self.N) | {i for i, x in (self.O.get("individuals") or {}).items() if x.get("is") == "law_relation"}
                bound = {a for f in l["assume"] if not atom(f)[0] for a in atom(f)[2] if a in V}
                for part in ("assume", "derive", "require"):
                    for f in l[part]:
                        neg, rel, args = atom(f)
                        if not isinstance(f, dict) or set(f) - {"is", "from", "to", "neg"} or rel not in rels or not args:
                            err(f"{where}: {part} の {f} が、関係（基礎の関係・文法の語・導いた関係）と項で書かれていない")
                        if rel in self.B and len(args) != self.B[rel]["arity"]:
                            err(f"{where}: {part} の {f} の端の数が、{rel} と合わない")
                        if part != "assume" and {a for a in args if a in V} - bound:
                            err(f"{where}: {part} の {f} に、肯定の前提に出てこない変数がある")
                        if part == "derive" and neg:
                            err(f"{where}: 導く文は否定にしない（書かれていない文は成り立たない）")
            else:
                if l["assume"] or l["derive"] or l["require"] or not l["govern"]:
                    err(f"{where}: 意味を検査が与える法則は、規則を持たず、掛かる節を持つ")
                for t in l["govern"]:
                    if t not in self.N:
                        err(f"{where}: 掛かる先 {t} がノードでない")
                if lid not in LAWS_HERE | LAWS_RUN:
                    err(f"{where}: 当てはめる検査がない")
        for lid in (LAWS_HERE | LAWS_RUN) - {k for k, l in L.items() if l["kind"] == "law_given"}:
            err(f"法則 {lid} を検査が当てはめているが、law_given の個体として書かれていない")
        for k, v in self.O["runtime"].items():
            if k not in G["runtime"]:
                err(f"runtime: 語 {k} が、grammar.runtime に書かれていない")
            elif self.resolve(v, "run") is None or not self.is_a(self.resolve(v, "run"), self.resolve(k, "run")) and not (k == "pre_rule" and v in G["logic"]):
                err(f"runtime.{k}: 値 {v} が、{k} の下位のノードでない")
        for k in self.O:
            if k not in G["system"] and k not in ("domains", "laws"):   # 個体と事実から並べた形（core_sections）
                err(f"体系の節 {k} が、grammar.system に書かれていない")
        for bid, b in self.B.items():
            for k in b:
                if k not in G["base"]:
                    err(f"base.{bid}: 語 {k} が、grammar.base に書かれていない")
        for aid, a in self.AX.items():
            for k in a:
                if k not in G["axes"]:
                    err(f"axes.{aid}: 語 {k} が、grammar.axes に書かれていない")
            if isinstance(a["value"], str) and a["value"] not in G["value"]:
                err(f"axes.{aid}: 値の種類 {a['values']} が、grammar.values に書かれていない")

    def resolve(self, word, dom):
        """領域を書かない語を、ノードの識別子に解決する。その領域、axiom、ほかの領域にただ1つ、の順に探す。"""
        if f"{dom}.{word}" in self.N:
            return f"{dom}.{word}"
        if word in self.N:
            return word
        found = [i for i in self.N if i.split(".", 1)[-1] == word]
        return found[0] if len(found) == 1 else None

    def domain(self, nid):
        return nid.split(".", 1)[0] if "." in nid else "axiom"

    def refs(self, nid):
        """ノードの式が参照しているノード。"""
        n, out = self.N[nid], set(self.parents(nid))
        for k in ("from", "to", "new_kind"):
            out.add(n.get(k))
        for k in ("of", "form"):
            if k in n:
                out.add(n[k][0])
        for m in n.get("mod") or []:
            if isinstance(m, dict):
                out |= {m["of"][0], m.get("with")}
            else:
                out.add(m)
        for x in n.get("cmp") or []:
            out |= {x.get("a"), x.get("b")}
        return {r for r in out if r in self.N}

    def check_domains(self):
        D = self.O["domains"]
        for did, d in D.items():
            for u in d.get("uses", []):
                if u not in D:
                    err(f"domains.{did}: 使う領域 {u} が未定義")
            seen, todo = set(), list(d.get("uses", []))
            while todo:
                u = todo.pop()
                if u == did:
                    err(f"domains.{did}: uses が循環している")
                    break
                if u in D and u not in seen:
                    seen.add(u)
                    todo += D[u].get("uses", [])
        for nid in self.N:
            dom = self.domain(nid)
            if dom not in D:
                err(f"{nid}: 領域 {dom} が domains に書かれていない")
                continue

    def parents(self, nid):
        """上位。extends に書いたものと、「属する」（is）の始点として限定した種類。
        AND は並べて書かず、「A のうち、B に属するもの」と、関係を明示して書く。"""
        n = self.N[nid]
        out = [n["extends"]] if isinstance(n.get("extends"), str) else []
        for m in n.get("mod") or []:
            if isinstance(m, dict) and m.get("of") == ["is", "from"] and not m.get("neg") and m.get("with") in self.N:
                out.append(m["with"])
        return out

    def up(self, nid):
        ps = self.parents(nid)
        return ps[0] if ps else None

    def ancestors(self, nid):
        out, todo = [], self.parents(nid)
        while todo:
            x = todo.pop()
            if x in self.N and x not in out:
                out.append(x)
                todo += self.parents(x)
        return out

    def is_concept(self, nid):
        n = self.N[nid]
        return "extends" in n and "of" not in n and "form" not in n and "holds" not in n and "pre" not in n and nid not in TOPS

    def own(self, nid):
        """そのノードが自分で足している限定。"""
        n = self.N[nid]
        s = {yaml.safe_dump(m, sort_keys=True, allow_unicode=True) for m in (n.get("mod") or [])}
        s |= {"val " + yaml.safe_dump(list(x), allow_unicode=True) for x in (n.get("val") or {}).items()}
        s |= {"cmp " + yaml.safe_dump(x, sort_keys=True, allow_unicode=True) for x in (n.get("cmp") or [])}
        for k in ("axis", "from", "to", "new_kind"):
            if k in n:
                s.add(f"{k} {n[k]}")
        return s

    def acc(self, nid):
        """上位から積み上がった限定の全体。概念の同一性は、これで決まる。"""
        s = set(self.own(nid))
        for a in self.ancestors(nid):
            s |= self.own(a)
        return s

    def syntax_facts(self):
        """体系の書き方を、文法の語を関係とする文に直す。法則の規則は、この文に当てはめる。"""
        out, dump = [], lambda x: yaml.safe_dump(x, sort_keys=True, allow_unicode=True).strip()
        add = lambda rel, *xs: out.append((rel, tuple(xs)))
        for nid, n in self.N.items():
            add("exists", nid)
            add("domain", nid, self.domain(nid))
            if n.get("display"):
                add("display", nid, n["display"])
            if isinstance(n.get("extends"), str):
                add("extends", nid, n["extends"])
            for k in ("from", "to", "new_kind", "axis"):
                if isinstance(n.get(k), str):
                    add(k, nid, n[k])
            for k in ("of", "form"):
                if isinstance(n.get(k), list) and len(n[k]) == 2:
                    add(k, nid, n[k][0])
                    add("position", nid, n[k][1])
            for k in ("holds", "pre"):
                for i, _ in enumerate(n.get(k) or []):
                    add(k, nid, i)
            for m in n.get("mod") or []:
                t = dump(m) if isinstance(m, dict) else m
                add("mod", nid, t)
                if isinstance(m, dict):
                    if isinstance(m.get("of"), list) and len(m["of"]) == 2:
                        add("of", t, m["of"][0])
                        add("position", t, m["of"][1])
                    if m.get("with") is not None:
                        add("with", t, m["with"])
                    if m.get("neg"):
                        add("neg", t, "true")
                    if isinstance(m.get("with"), str) and m["with"] in self.I:
                        add("refer", nid, m["with"])
            for x in (n.get("val") or {}).items():
                add("val", nid, "val " + dump(list(x)))
            for x in n.get("cmp") or []:
                add("cmp", nid, "cmp " + dump(x))
            for r in self.refs(nid):
                add("refer", nid, r)
        for j, (verb, x) in enumerate(getattr(self, "KF", [])):   # 種類どうしの事実
            t = f"kind_fact {j}"
            add("of", t, verb)
            for p, k in x.items():
                add(p, t, k)
        for c, k in getattr(self, "COLL", {}).items():   # 種類の集まり（2階）の事実
            t = f"collect {c}"
            add("of", t, "v_collect")
            add("from", t, c)
            add("to", t, k)
        for i in self.I:
            if isinstance(self.I[i], str):
                add("is", i, self.I[i])
            add("domain", i, "axiom" if i in (self.O.get("individuals") or {}) else self.Isubj.get(i, self.Idom))
        for aid, a in self.AX.items():
            add("exists", aid)
            for v in a["value"] if isinstance(a["value"], list) else []:
                add("value", aid, "true" if v is True else "false" if v is False else v)
        for did, d in self.O["domains"].items():
            for u in d["uses"]:
                add("v_use", did, u)
        return out

    def check_laws(self):
        """規則で書いた法則を、体系の書き方の文に当てはめる。"""
        V = variables(self.O)
        for lid, b, f in evaluate(law_rules(self.O), Facts(self.syntax_facts()), V):
            where = ", ".join(f"{k}={v}" for k, v in sorted(b.items()))
            err(f"法則 {lid}（{self.O['laws'].get(lid, {}).get('display', '')}）に反する: {where}")

    def end(self, nid, side):
        """動詞の端の種類。自分になければ上位の動詞から受け継ぐ。"""
        hops = 0
        while nid in self.N and hops < 50:
            if side in self.N[nid]:
                return self.N[nid][side]
            nid, hops = self.up(nid), hops + 1
        return None

    def is_verb(self, nid):
        return nid in self.N and self.end(nid, "from") is not None and self.end(nid, "to") is not None

    def spot_type(self, verb, pos):
        return (self.end(verb, "new_kind") or "any") if pos == "new" else self.end(verb, pos)

    def parent(self, nid):
        n = self.N[nid]
        if "extends" in n:
            return self.up(nid)
        if "form" in n:
            return self.spot_type(*n["form"])
        return None

    def q(self, w):
        """検査が名前で参照する語を、ノードの識別子に解決する（領域を書かない語は、個体の領域、axiom の順に探す）。"""
        if not isinstance(w, str) or w in self.N or w in self.I or w == "any":
            return w
        return self.resolve(w, self.Idom or "axiom") or w

    def occupies(self, kind, end, verb):
        """個体（種類 kind）が、動詞 verb の端の種類 end の位置を占めてよいか。
        役割は、位置を占めることで決まる。役割でない種類は、その動詞（または上位の動詞）の位置で
        定義された分（修飾と cmp）を外し、残りの種類に属していればよい。"""
        if self.is_a(kind, end) or self.is_a(end, "role"):
            return True
        n = end
        while n in self.N:
            ms = self.N[n].get("mod")
            ms = ms if isinstance(ms, list) else [ms]
            positional = "cmp" in self.N[n] or any(isinstance(m, dict) and isinstance(m.get("of"), list)
                                                   and self.is_a(verb, self.q(m["of"][0])) for m in ms)
            if not positional:
                break
            n = self.q(self.N[n].get("extends"))
        return n is not None and self.is_a(kind, n)

    def is_a(self, x, y, hops=0):
        if hops == 0:
            x, y = self.q(x), self.q(y)
        if y == "any":
            return True
        if x in self.I:   # 個体は、成員が1つの種類。自分自身か、自分の種類の上位に当たる
            return x == y or self.is_a(self.I[x], y, hops + 1)
        if x is None or x == "any" or x not in self.N or hops > 80:
            return x == y
        if x == y:
            return True
        n = self.N[x]
        ups = self.parents(x) if "extends" in n else ([self.spot_type(*n["form"])] if "form" in n else [])
        return any(self.is_a(u, y, hops + 1) for u in ups)

    def overlaps(self, x, y):
        return x == "any" or self.is_a(x, y) or self.is_a(y, x)

    def base_of(self, verb):
        hops = 0
        while verb in self.N and hops < 50:
            fs = [f for k in ("holds", "pre", "post") for f in self.N[verb].get(k, [])]
            if fs:
                return {atom(f)[1] for f in fs}
            verb, hops = self.up(verb), hops + 1
        return set()

    def is_function(self, v):
        if not (isinstance(v, dict) and len(v) == 1):
            return False
        (op, arg), = v.items()
        args = arg if isinstance(arg, list) else [arg]
        return op in self.funcs and len(args) == self.funcs[op] and all(isinstance(a, (int, float)) for a in args)

    def check_value(self, axis, v, where):
        if axis not in self.AX:
            return err(f"{where}: 軸 {axis} が未定義")
        vals = self.AX[axis]["value"]
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
        if pos not in self.G["position"]:
            return err(f"{where}: 位置 {pos} が、grammar.position に書かれていない")
        return verb, pos

    def check_state(self, vid, n):
        if ("holds" in n) == ("pre" in n or "post" in n):
            err(f"{vid}: 静的（holds）か動的（pre / post）のどちらかで書く")
        for key in ("holds", "pre", "post"):
            for f in n.get(key, []):
                ok = isinstance(f, dict) and not set(f) - set(self.G["facts"]) - {"at"} and f.get("is") in self.B
                args = atom(f)[2] if ok else ()
                if not ok or "at" in f or len(args) != self.B[f["is"]]["arity"] or any(a not in self.G["position"] for a in args):
                    err(f"{vid}: {key} の {f} が、基礎の関係と位置で書かれていない")

    def grounding(self, nid):
        return [m["with"] for x in [nid] + self.ancestors(nid) for m in (self.N[x].get("mod") or [])
                if isinstance(m, dict) and m.get("of") == ["v_depend", "from"] and "with" in m and not m.get("neg")
                and self.is_a(m["with"], "definition")]

    def check(self):
        N, AX, B = self.N, self.AX, self.B
        for bid, b in B.items():
            ruled = any(atom(f)[1] == bid for l in self.O["laws"].values() for p in ("assume", "derive", "require") for f in l[p])
            if not ruled and not b.get("system_act") and b["arity"] != 1:
                err(f"base: {bid} に法則がない（法則を持たない基礎の関係は、体系の行為 1個だけ）")
        if sum(bool(b.get("system_act")) for b in B.values()) != 1:
            err("base: 体系そのものの行為は、ちょうど1個であること")
        for aid, a in AX.items():
            if a["source"] != "any" and a["source"] not in B:
                err(f"axes: {aid} のもとになる関係 {a['from']} が未定義")
        seen, forms = {}, {}
        for nid, n in N.items():
            ja = n.get("display")
            key = (self.domain(nid), ja)  # 法則 unique_in_domain
            if not ja:
                err(f"{nid}: 表示語がない")
            seen[key] = nid
            if nid in TOPS:
                if set(n) != {"display", "gloss"}:
                    err(f"{nid}: 最上位は gloss だけを持つ")
                continue
            if "gloss" in n:
                err(f"{nid}: gloss を持てるのは最上位の2つだけ。式で書くこと")
            extra = set(n) - set(self.G["nodes"])
            if extra:
                err(f"{nid}: 語 {extra} が、grammar.nodes に書かれていない")
            for side in ("from", "to", "new_kind"):
                if side in n and n[side] != "any" and n[side] not in N:
                    err(f"{nid}: {side} の {n[side]} が未定義")
            if "form" in n:
                self.check_spot(n["form"], nid)
                continue
            if not self.parents(nid) or any(p not in N for p in self.parents(nid)):
                err(f"{nid}: 上位がない、または未定義")
                continue
            if self.is_verb(nid):
                if not self.is_a(nid, "occurrent"):
                    err(f"{nid}: 動詞は生起体の下に置く")
                if self.is_verb(self.up(nid)):
                    if not any(k in n for k in ("from", "to", "mod")) and len(self.parents(nid)) < 2:
                        err(f"{nid}: 上位の動詞と区別する式がない")
                else:
                    self.check_state(nid, n)
            elif "of" in n:
                self.check_spot(n["of"], nid)
                if not self.is_a(nid, "specifically_dependent_continuant"):
                    err(f"{nid}: 修飾語は特定依存持続体の下に置く")
            elif not (n.get("mod") or n.get("val") or n.get("cmp") or len(self.parents(nid)) > 1):
                err(f"{nid}: 式がない")
            for axis, v in (n.get("val") or {}).items():
                self.check_value(axis, v, f"{nid}.val")
            for i, c in enumerate(n.get("cmp") or []):
                if set(c) - set(self.G["cmp"]):
                    err(f"{nid}.cmp[{i}]: 語 {set(c) - set(self.G['cmp'])} が、grammar.cmp に書かれていない")
                if c.get("axis") not in AX or c.get("a") not in N or c.get("b") not in N or c.get("rel") not in self.G["rel"]:
                    err(f"{nid}.cmp[{i}]: 軸・比べる2つ・比べた結果のどれかが正しくない")
            if "axis" in n:
                if n["axis"] not in AX or AX[n["axis"]]["value"] != "number":
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
                if not self.overlaps(self.spot_type(verb, pos), n["extends"]) and not self.overlaps(n["extends"], self.spot_type(verb, pos)):
                    err(f"{where}: {n['extends']} は {verb} の {pos}（{self.spot_type(verb, pos)}）に来られない")
                if "with" in m:
                    other = {"from": "to", "to": "from"}.get(pos)
                    if other is None:
                        err(f"{where}: 位置 new には with を付けられない")
                    elif verb == "is":   # 「属する」の終点は、種類そのもの（その成員ではない）
                        if m["with"] not in N or not self.is_concept(m["with"]):
                            err(f"{where}: {m['with']} は種類でない")
                    elif self.is_a(self.end(verb, other), "verb_ref"):   # 動詞を受け取る位置: 来るのは動詞そのもの
                        if not self.is_verb(m["with"]):
                            err(f"{where}: {m['with']} は動詞でない。{verb} の {other} は動詞を受け取る")
                    elif (m["with"] not in N and m["with"] not in self.I) or not self.overlaps(m["with"], self.end(verb, other)):
                        err(f"{where}: {m['with']} は {verb} の {other}（{self.end(verb, other)}）に来られない")
                if set(m) - set(self.G["mod"]):
                    err(f"{where}: 語 {set(m) - set(self.G['mod'])} が、grammar.mod に書かれていない")
                if m.get("quant") is not None and m["quant"] not in self.G["logic"]:
                    err(f"{where}: 数量化 {m['quant']} が、grammar.logic に書かれていない。数は at で書く")
                for axis, v in (m.get("at") or {}).items():
                    self.check_value(axis, v, where)
                    if axis in AX and AX[axis]["source"] != "any" and AX[axis]["source"] not in self.base_of(verb):
                        err(f"{where}: 軸 {axis} は基礎の関係 {AX[axis]['source']} を抽象にしたものだが、{verb} はそれを使っていない")
            if not ("holds" in n or "pre" in n):
                key = yaml.safe_dump({k: n[k] for k in ("extends", "from", "to", "of", "mod", "neg", "val", "cmp", "axis") if k in n}, sort_keys=True)
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
            if "holds" in n or "pre" in n:
                s = tuple(tuple(sorted(map(atom, n.get(k, [])))) for k in ("holds", "pre", "post")) + (n["from"], n["to"], n.get("new_kind"))
                sig[s].append(nid)
        for ids in sig.values():
            if len(ids) > 1:
                err(f"動詞の式が同じ: {ids}")

    def mods_of(self, nid):
        return [m for x in [nid] + self.ancestors(nid) for m in (self.N[x].get("mod") or []) if isinstance(m, dict)]

    def field_ok(self, kind, f, dom="axiom"):
        """種類 kind の個体に、項目 f を書けるか。項目の表は持たず、式から決める。
        f が動詞かその位置の形（s, p, o）: kind が「について述べる」の始点に来る種類（文）であること。
        それ以外: f かその下位に、kind のものとの関係で限定されたノードがあること。または、kind の式が f のものとの関係で限定されていること。"""
        kind, f = self.q(kind), f if f in self.N else self.resolve(f, dom)
        if f is None:
            return False
        if "form" in self.N[f] or self.is_verb(f):
            return any(m["of"] == ["v_refer", "from"] for m in self.mods_of(kind))
        cands = [f] + [k for k in self.N if self.is_concept(k) and f in self.ancestors(k)]
        if any(m.get("with") in self.N and self.is_a(f, m["with"]) for m in self.mods_of(kind)):   # 種類の式が、f のものとの関係で限定されている
            return True
        return any(m.get("with") in self.N and self.is_a(kind, m["with"]) for c in cands for m in self.mods_of(c))

    def count_ok(self, want, v):
        if isinstance(want, dict):
            (op, arg), = want.items()
            return {"gt": v > arg, "ge": v >= arg, "lt": v < arg, "le": v <= arg}.get(op, True) if not isinstance(arg, list) else arg[0] <= v <= arg[1]
        return want == v

    def check_counts(self, kind, x, where):
        """個数の事実が、種類の式の個数の限定に入っていること。"""
        for f, v in x.items():
            f = self.q(f)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and f in self.N and not self.is_a(f, "magnitude"):
                for m in self.mods_of(kind):
                    want = (m.get("at") or {}).get("count")
                    if want is not None and m.get("with") in self.N and self.is_a(f, m["with"]) and not self.count_ok(want, v):
                        err(f"{where}: {f} の個数 {v} が、種類 {kind} の限定 {want} に入っていない")

    def kinds_of(self, nid):
        """nid の下位のうち、それより下を持たないノード。status や留保の値として使えるもの。"""
        nid = self.q(nid)
        has_child = {p for k in self.N for p in self.parents(k)}
        return [k for k in self.N if k not in has_child and k != nid and nid in self.ancestors(k)]

    def status_pattern(self, nid):
        """状態のノードの式から、「支持する観察がある / 反する観察がある」の組を読み取る。"""
        pat = {}
        for m in [m for x in [nid] + self.ancestors(nid) for m in (self.N[x].get("mod") or [])]:
            if isinstance(m, dict) and m.get("of") == ["v_agree", "to"] and short(m.get("with")) in ("evidence", "against"):
                pat[short(m["with"])] = not m.get("neg")
        return pat if set(pat) == {"evidence", "against"} else None

    def compare(self, verb, a, b, tol):
        """大きさを比べる動詞の式（後ろにある、の成立と不成立）を、2つの数に当てはめる。"""
        hops = 0
        while verb in self.N and "holds" not in self.N[verb] and hops < 50:
            verb, hops = self.up(verb), hops + 1
        n = self.N.get(verb, {})
        fs = [atom(f) for f in n.get("holds", [])]
        if not fs or any(rel != "after" or len(args) != 2 or set(args) - {"from", "to"} for _, rel, args in fs):
            return None
        x = {"from": a, "to": b}
        out = True
        for neg, _, (p1, p2) in fs:
            later = x[p1] - x[p2] > tol
            out = out and (not later if neg else later)
        return out

    def is_strict(self, verb):
        hops = 0
        while verb in self.N and "holds" not in self.N[verb] and hops < 50:
            verb, hops = self.up(verb), hops + 1
        return any(atom(f)[1] == "after" for f in self.N.get(verb, {}).get("holds", []))

    def expr(self, nid):
        """上位をたどって、式を並べる。"""
        out, hops = [], 0
        while nid in self.N and hops < 80:
            n = self.N[nid]
            body = {k: n[k] for k in ("from", "to", "new_kind", "holds", "pre", "post", "form", "of", "neg", "mod", "val", "cmp", "axis", "gloss") if k in n}
            out.append(f"{nid}（{n['display']}） {body}")
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
    # 選択肢の順序ごとの値を並べた形（[順序1, 順序2]）は、平均と「両方とも正」に直す
    vals = [{"margin": sum(v) / len(v), "both": all(x > 0 for x in v)} if isinstance(v, list) else v for v in vals]
    n = len(vals)
    if name == "accuracy":
        return sum(v["margin"] > 0 for v in vals) / n, n
    if name == "order_robust_accuracy":
        return sum(bool(v["both"]) for v in vals) / n, n
    if name == "logit_margin":
        return sum(v["margin"] for v in vals) / n, n
    if name == "judged_accuracy":
        rs = [r for _, r in rows if cond in r]
        return sum(r[cond]["judged"] == r["correct"] for r in rs) / n, n
    if name == "mean_value":
        return sum(vals) / n, n
    raise KeyError(f"指標 {name} の計算方法が、検査ツールにない")


def check_meaning(val, T, where):
    if isinstance(val, str):
        if val not in T.N and val not in T.I:
            err(f"{where}: ノード {val} が未定義")
        return
    for nid in val.get("identifier", []):
        if nid not in T.N:
            err(f"{where}: ノード {nid} が未定義")
    for v in val.get("value", []):
        if v.get("s") not in T.N:
            err(f"{where}: 値の s {v.get('s')} が未定義")
        T.check_value(v.get("axis"), v.get("o"), where)


def expand(M, T):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        for st in f["metric"]:
            if st not in T.N or not (T.is_a(st, "metric") or T.is_a(st, "magnitude")):
                err(f"measurements.{fid}: 指標 {st} は、体系の指標でも大きさでもない")
        axes = f["axis"]
        names = list(axes)
        keys = [list(axes[a]) if isinstance(axes[a], dict) else axes[a] for a in names]
        for a, mp in (f.get("meaning") or {}).items():
            for k, v in mp.items():
                check_meaning(v, T, f"measurements.{fid}.meaning.{a}.{k}")
        for combo in itertools.product(*keys):
            b = dict(zip(names, combo))
            sub = {a: (axes[a][b[a]] if isinstance(axes[a], dict) else b[a]) for a in names}
            fmt = lambda x: x.format(**{k: v for k, v in sub.items() if not isinstance(v, list)}) if isinstance(x, str) else x
            try:
                rows = rows_of(fmt(f["result_file"]), [fmt(x) for x in f.get("row_collection", [])])
            except (FileNotFoundError, KeyError) as e:
                err(f"measurements.{fid}: {b} のファイルまたは位置が見つからない: {e}")
                continue
            for field, want in (f.get("row_filter") or {}).items():
                want = sub[want[1:-1]] if isinstance(want, str) and want[1:-1] in sub and isinstance(sub[want[1:-1]], list) else fmt(want)
                ok = (lambda x, w=want: x in w) if isinstance(want, list) else (lambda x, w=want: x == w)
                rows = [(k, r) for k, r in rows if ok(r.get(field))]
            if "row_keys" in f:
                axis = f["row_keys"]["axis"]
                allowed = {fmt(f["row_keys"]["pattern"]).replace("#", str(x)) for x in sub[axis]}
                rows = [(k, r) for k, r in rows if k in allowed]
            for st in f["metric"]:
                mid = ".".join([fid] + [str(b[a]) for a in names] + [short(st)])
                try:
                    values[mid] = stat(rows, fmt(f["condition_entry"]), short(st))
                except KeyError as e:
                    err(f"measurements: {mid}: {e}")
                meanings[mid] = {a: (f.get("meaning") or {}).get(a, {}).get(b[a], b[a]) for a in names} | {"metric": st}
    return values, meanings


# ---------------------------------------------------------------- 観察・仮説・決定
def check_claims(C, values, T):
    # 観察: 測定値どうし（または測定値と数）を、大きさを比べる動詞で結んだ文。すべて真であること
    obs = C["observations"]
    gap = {}   # 大小を述べる観察について、2つの値の差を問数に直したもの
    for oid, o in obs.items():
        vals = []
        for side in ("s", "o"):
            x = o[side]
            if isinstance(x, (int, float)) and side == "o":
                vals.append(float(x))
            elif isinstance(x, str) and x in values:
                vals.append(values[x][0])
            else:
                err(f"{oid}: {side} の {x} は、測定値でない")
        if len(vals) < 2:
            continue
        if not T.is_verb(o["p"]):
            err(f"{oid}: p の {o['p']} は動詞でない")
            continue
        near = short(T.end(o["p"], "new_kind")) == "tolerance"
        if near != ("tolerance" in o):
            err(f"{oid}: 許容幅は、動詞 {o['p']} の第三のものが許容幅であるときにだけ、必ず書く")
            continue
        holds = T.compare(o["p"], vals[0], vals[1], o["tolerance"] + 1e-9 if near else 1e-6)
        if holds is None:
            err(f"{oid}: 動詞 {o['p']} は、大きさを比べる動詞（「後ろにある」だけで書かれた静的な動詞）でない")
        elif not holds:
            err(f"observations: {oid} が成り立たない（{T.N[o['p']]['display']}: s={vals[0]:.3f}, o={vals[1]:.3f}）")
        ns = [values[x][1] for x in (o["s"], o["o"]) if isinstance(x, str) and x in values]
        gap[oid] = abs(vals[0] - vals[1]) * min(ns) if T.is_strict(o["p"]) else None

    hyps, decs = C["hypotheses"], C["decisions"]

    def triple(x, where, structural_ok=False):
        ss = x["s"] if isinstance(x["s"], list) else [x["s"]]
        oo = x["o"] if isinstance(x["o"], list) else [x["o"]]
        for t in ss + oo:
            if t not in T.N and t not in T.I:
                err(f"{where}: ノード {t} が未定義")
                return
        if x["p"] == "is_a":
            if not structural_ok:
                err(f"{where}: is_a を使えるのは決定だけ")
            elif T.is_a(x.get("status"), "dec_adopted") and not all(T.is_a(a, b) for a in ss for b in oo):
                err(f"{where}: 採用済みの決定だが、体系の上で {ss} は {oo} の下位になっていない")
            return
        if not T.is_verb(x["p"]):
            return err(f"{where}: {x['p']} は動詞でない")
        for side, ts in (("from", ss), ("to", oo)):
            bound = T.end(x["p"], side)
            for t in ts:
                if not T.overlaps(t, bound):
                    err(f"{where}: {t} は動詞 {x['p']} の {side}（{bound}）に来られない")

    patterns = {k: T.status_pattern(k) for k in T.kinds_of("hypothesis")}
    patterns = {k: v for k, v in patterns.items() if v}
    for hid, h in hyps.items():
        triple(h, hid)
        have = {"evidence": bool(h.get("evidence")), "against": bool(h.get("against"))}
        want = [k for k, v in patterns.items() if v == have]
        if short(h["status"]) not in {short(k) for k in patterns}:
            err(f"{hid}: 種類 {h["status"]} は、仮説の状態のノードでない")
        elif want != [h["status"]]:
            err(f"{hid}: 種類は {h["status"]} と書かれているが、根拠の有無からは {want} になる")
        for t in h.get("scope", []):
            if t not in T.N and t not in T.I:
                err(f"{hid}: scope のノード {t} が未定義")
        for k in ("evidence", "against"):
            for r in h.get(k, []):
                if r not in obs:
                    err(f"{hid}: {k} の観察 {r} が未定義")
        for lim in h.get("limitation", []):
            if lim not in T.kinds_of("limitation"):
                err(f"{hid}: 留保 {lim} は、留保のノードでない")
        if "lim_one_item" in [short(x) for x in h.get("limitation", [])]:
            gs = [gap.get(r) for r in h.get("evidence", []) + h.get("against", [])]
            if not any(g is not None and g <= 1.0 + 1e-6 for g in gs):
                err(f"{hid}: 留保「差が1問以内」と書かれているが、根拠のうち大小を述べる観察に、差が1問以内のものがない")
        for r in h.get("supersedes", []):
            if r not in hyps:
                err(f"{hid}: supersedes の仮説 {r} が未定義")
    for did, d in decs.items():
        if d["status"] not in T.kinds_of("decision"):
            err(f"{did}: status の {d['status']} は、決定の状態のノードでない")
        triple(d, did, structural_ok=True)
        for r in d.get("basis", []):
            if r not in hyps:
                err(f"{did}: basis の仮説 {r} が未定義")
        for r in d.get("supersedes", []):
            if r not in decs:
                err(f"{did}: supersedes の決定 {r} が未定義")
    for b in C["backlog"]:
        if b["status"] not in T.kinds_of("backlog_item"):
            err(f"backlog {b['identifier']}: status の {b['status']} は、残り項目の状態のノードでない")
        for r in b.get("tests", []):
            if r not in hyps:
                err(f"backlog {b['identifier']}: tests の仮説 {r} が未定義")


def natural_language_only_in_ja(name, x, path=()):
    """自然言語を書けるのは、表示名 display だけ。例外は、字そのものが値であるもの:
    最上位2つの gloss、選択肢の字（val.text）、結果ファイルでの書き方（v_spell の終点）。"""
    if isinstance(x, dict):
        if x.get("is") == "v_spell":
            return
        for k, v in x.items():
            natural_language_only_in_ja(name, v, path + (str(k),))
    elif isinstance(x, list):
        for v in x:
            natural_language_only_in_ja(name, v, path)
    elif isinstance(x, str) and re.search(r"[^\x00-\x7f]", x):
        top = path[:1] == ("nodes",) and path[-1] == "gloss" and path[1] in ("continuant", "occurrent")
        opt = path[:1] == ("individuals",) and path[-2:] == ("val", "text")
        if path[-1:] != ("display",) and not top and not opt:
            err(f"{name} {'.'.join(path)}: 自然言語は表示名 display にだけ書く（{x[:20]}）")


CLAIM_DOMAINS = {"lang"}   # exp のほかに、仮説・決定を置く領域（言語そのものについての主張）


def check_sides(C, T):
    """主張がどちらの側のものかを、中身が参照する語で確かめる。
    lang の主張は、axiom（std を含む）と lang の語だけを参照する。exp の主張は、exp か subj の語（動詞を含む）を少なくとも1つ参照する。"""
    def words(x):
        out = []
        for k in ("s", "o", "p"):
            v = x.get(k)
            out += v if isinstance(v, list) else [v]
        return [w for w in out if isinstance(w, str) and w != "is_a"]

    def dom(w):
        if w in T.Isubj:
            return T.Isubj[w]
        if w in T.I:
            return T.Idom if w not in (T.O.get("individuals") or {}) else "axiom"
        return T.domain(w)
    for sect in ("hypotheses", "decisions"):
        for i, x in C[sect].items():
            side, ds = C["side"].get(i), {dom(w) for w in words(x)}
            if side in CLAIM_DOMAINS and ds - {"axiom", "run", side}:
                err(f"{i}: {side} の主張が、{side} と axiom 以外の語を参照している（{sorted(ds - {'axiom', 'run', side})}）")
            if side == "exp" and ds and ds <= {"axiom", "run"}:
                err(f"{i}: exp の主張が、axiom の語だけを参照している。言語についての主張なら cscl の側に置く")


def domain_files():
    """領域のファイル。cscl.yaml の範囲にあり、最上位に domain を持つ YAML。本体（root）は含めない。"""
    out, root = {}, (ROOT / config()["root"]).resolve()
    for p in in_scope("include"):
        if p == root:
            continue
        y = yload(p.read_text(encoding="utf-8")) or {}
        if isinstance(y, dict) and "domain" in y:
            out[y["domain"]] = str(p.relative_to(SPEC))
    return out


def register_domains(O):
    """各領域のファイルが自分で宣言した領域（{is: domain} の個体）と、使う領域（v_use の事実）を、体系の domains に加える。
    依存は領域ごとに宣言する（クレートが自分の依存を書くのと同じ）。使う領域の順に並べて返す。"""
    files = domain_files()
    for dom, name in files.items():
        y = yload((SPEC / name).read_text(encoding="utf-8"))
        me = (y.get("individuals") or {}).get(dom) or {}
        if me.get("is") != "domain":
            err(f"{name}: 領域 {dom} を、個体 {{is: domain}} として宣言していない")
        O["domains"][dom] = {"display": me.get("display"), "uses": []}
        for f in y.get("facts") or []:
            if isinstance(f, dict) and qualify(f.get("is"), set(y.get("nodes") or {}), dom) == "v_use":
                if f.get("from") != dom:
                    err(f"{name}: 領域の使用は、自分の領域についてだけ書く（{f}）")
                O["domains"][dom]["uses"].append(f.get("to"))
    order, seen = [], set()

    def visit(d, stack=()):
        if d in seen or d not in files:
            return
        if d in stack:
            return err(f"領域 {d}: uses が循環している")
        for u in O["domains"][d]["uses"]:
            visit(u, stack + (d,))
        seen.add(d)
        order.append(d)
    for d in files:
        visit(d)
    return [(d, files[d]) for d in order]


PART_WORDS = {"from": ("の部分である", "の時間的な部分である"), "to": ("を部分に持つ", "を時間的な部分に持つ")}
PART_VAGUE = ("から部分になる", "へ部分になる", "から時間的な部分になる", "へ時間的な部分になる")


def check_parts(T):
    """法則 part_fact_direction と part_display_explicit。
    - 事実「a は b の部分」に対し、b の種類が「a の種類の部分である」と限定されている（または a の種類が「b の種類を部分に持つ」）なら、向きが逆。
    - 部分の限定（holds に部分の文を持つ動詞による限定）を持つ種類の表示名は、どちらが部分かを曖昧な言い方で書かず、明示した言い方なら限定の向きと合う。"""
    kind = lambda x: T.I.get(x, x if x in T.N else None)
    isa = lambda a, b: a is not None and (a == b or T.is_a(a, b))

    def parts(verb):
        """動詞の holds のうち部分の文を、(部分の位置, 全体の位置) で。動詞の名前でなく、定義から読む。"""
        return {(h["from"], h["to"]) for h in T.end(verb, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"} if verb in T.N else set()

    def role(m):
        """限定 {of: [V, p], with: X} で、限定される種類が X の部分なら "part"、X を部分に持つなら "whole"。
        X の位置は、第三のものを作る動詞なら new、そうでなければ p の反対の位置。"""
        if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2:
            return None
        v, pos = T.q(m["of"][0]), m["of"][1]
        wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
        P = parts(v)
        return "part" if (pos, wpos) in P else "whole" if (wpos, pos) in P else None

    def mods(k, r):
        out, hops = [], 0
        while k in T.N and hops < 50:
            out += [m["with"] for m in T.N[k].get("mod") or [] if m_ok(m) and role(m) == r]
            k, hops = T.up(k), hops + 1
        return out
    m_ok = lambda m: isinstance(m, dict) and m.get("with") and not m.get("neg")
    files = [(root_name(), "axiom")] + [(name, dom) for dom, name in domain_files().items()]
    for name, dom in files:
        for f in yload((SPEC / name).read_text(encoding="utf-8")).get("facts") or []:
            if not isinstance(f, dict) or not isinstance(f.get("is"), str):
                continue
            v = T.resolve(f["is"], dom)
            if not v or ("from", "to") not in parts(v):
                continue
            r = lambda x: (x if x in T.I else (T.resolve(x, dom) or x)) if isinstance(x, str) else None
            a, b = r(f.get("from")), r(f.get("to"))
            for X in mods(kind(b), "part"):
                if isa(kind(a), X):
                    err(f"法則 part_fact_direction に反する: {name} の事実 {a} は {b} の部分だが、{b} の種類は {X} の部分と限定されている")
            for X in mods(kind(a), "whole"):
                if isa(kind(b), X):
                    err(f"法則 part_fact_direction に反する: {name} の事実 {a} は {b} の部分だが、{a} の種類は {X} を部分に持つと限定されている")
    for nid, n in T.N.items():
        disp = n.get("display") or ""
        if T.is_verb(nid):
            continue
        for m in n.get("mod") or []:
            r = role(m)
            if r is None:
                continue
            if any(w in disp for w in PART_VAGUE):
                err(f"法則 part_display_explicit に反する: {nid} の表示名「{disp}」は、どちらが部分かが曖昧")
            if any(w in disp for w in PART_WORDS["to" if r == "part" else "from"]) and not m.get("neg"):
                err(f"法則 part_display_explicit に反する: {nid} の表示名「{disp}」が、限定の向き（{m['of'][1]}）と逆")


def build():
    """体系を読み、検査して、(体系, ontology, 領域 subj, 測定の族, 文) を返す。誤りは errors に積む。
    領域のファイルは自分で見つけ、使う領域の順に読む。領域 exp の個体（測定・観察・仮説など）は、中身まで検査する。"""
    O = load(root_name())
    natural_language_only_in_ja(root_name(), yload(open(SPEC / root_name())))
    for p in in_scope("std"):
        natural_language_only_in_ja(str(p.relative_to(ROOT)), yload(open(p)))
    order = register_domains(O)
    Dm = {}
    for dom, name in order:
        natural_language_only_in_ja(name, yload(open(SPEC / name)))
        Dm[dom] = (name, merge_domain(name, O))
    T = Ontology(O)
    _, D = Dm["exp"]
    T.Idom = "exp"
    for iid, x in D["individuals"].items():
        if not isinstance(x.get("is"), str):
            err(f"exp.yaml {iid}: is は種類を1つだけ書く。並べない")
            x["is"] = None
    T.I = {iid: x.get("is") for iid, x in D["individuals"].items() if x.get("is") in O["nodes"]}
    core = {iid: dict(x) for iid, x in (O.get("individuals") or {}).items()}
    for iid, x in core.items():
        if iid in T.I or iid in T.N:
            err(f"ontology.yaml {iid}: 個体の識別子が、ほかの個体かノードと重なっている")
        if set(x) - set(T.G["individuals"]) or x.get("is") not in T.N:
            err(f"ontology.yaml {iid}: 個体は {{is: 種類, display}} で書き、種類はノード")
    T.I |= {iid: x.get("is") for iid, x in core.items() if x.get("is") in T.N}
    gather({"domain": "axiom", "_local": set(), "individuals": core, "facts": O.get("facts")}, T, "ontology.yaml")
    others, claims = {}, {}
    for dom, (name, X) in Dm.items():
        if dom == "exp":
            continue
        if dom in CLAIM_DOMAINS:   # 主張（仮説・決定）の領域。中身まで検査する
            for iid, x in X["individuals"].items():
                if iid in T.I or iid in T.N or iid in core:
                    err(f"{name} {iid}: 個体の識別子が、ほかの個体かノードと重なっている")
            T.I |= {iid: x.get("is") for iid, x in X["individuals"].items() if x.get("is") in T.N}
            T.Isubj |= {iid: dom for iid in X["individuals"]}
            claims[dom] = (name, X)
            continue
        ind = {iid: dict(x) for iid, x in X["individuals"].items()}
        for iid in ind:
            if iid in T.I or iid in T.N or iid in core:
                err(f"{name} {iid}: 個体の識別子が、ほかの個体かノードと重なっている")
        T.I |= {iid: x.get("is") for iid, x in ind.items() if x.get("is") in T.N}
        T.Isubj |= {iid: dom for iid in ind}
        others[dom] = (name, X, ind)
    for dom, (name, X, ind) in others.items():
        gather({"domain": dom, "_local": X["_local"], "individuals": ind, "facts": X.get("facts")}, T, name)
    collect_kind_facts(T)
    T.check()
    T.check_grammar()
    T.check_domains()
    T.check_laws()
    check_parts(T)
    M, C = load_domain("exp.yaml", D, T)
    C["side"] = {i: "exp" for sect in ("hypotheses", "decisions") for i in C[sect]}
    for dom, (name, X) in claims.items():
        _, C2 = load_domain(name, X, T)
        for sect in ("hypotheses", "decisions", "observations"):
            for i, x in C2[sect].items():
                C[sect][i] = x
                if sect != "observations":
                    C["side"][i] = dom
        C["backlog"] += C2["backlog"]
    check_sides(C, T)
    S = others.get("subj", (None, {"individuals": {}, "facts": [], "_local": set()}))[1]
    return T, O, S, M, C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--values", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--expr")
    args = ap.parse_args()
    T, O, S, M, C = build()
    values, meanings = expand(M, T)
    check_claims(C, values, T)
    if args.expr:
        print(T.expr(args.expr if args.expr in T.N else T.resolve(args.expr, "axiom") or args.expr))
    if args.values:
        for mid, (v, n) in sorted(values.items()):
            print(f"{mid} = {v:.2f} (n={n})")
    if args.show:
        for sect in ("observations", "hypotheses", "decisions"):
            if args.show in C[sect]:
                x = C[sect][args.show]
                print(yaml.safe_dump({args.show: x}, allow_unicode=True, sort_keys=False))
                for k in ("s", "o"):
                    if isinstance(x.get(k), str) and x[k] in values:
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
    verbs = sum(1 for n in N.values() if "holds" in n or "pre" in n)
    print(f"検査に成功: ノード {len(N)}（うち動詞の語根 {verbs}、役割 {len(T.roles)}）、基礎の関係 {len(T.B)}、分類の軸 {len(T.AX)}、"
          f"測定値 {len(values)}、観察 {len(C['observations'])}、仮説 {len(C['hypotheses'])}、決定 {len(C['decisions'])}、残り項目 {len(C['backlog'])}")


if __name__ == "__main__":
    main()
