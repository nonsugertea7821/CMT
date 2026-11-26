"""体系の型検査（stage0。Python による最初の実装）。言語の検査だけをする。

cscl.yaml の範囲のファイル（cscl/library/, 領域のファイル）が正本。自然言語の文章は正本ではない。

cscl.yaml の root と library  概念の体系（signature → ontology → syntax → runtime → std の層）。
  検査: 表示語の一意性 / gloss を持つのは最上位の2つだけ / 動詞の式（状態の関係・両端・第三のものの種類）の一意性 /
        動詞の下位が端を狭めていること / 修飾の型（その位置に来られるか）/ 分類の軸と値 / 概念の式の一意性 /
        役割が根拠となる定義を持つこと
  grammar: 体系が、自分の書き方について述べる部分。文法の語は、すべてノードの識別子。節ごとに、使える語を並べる。
        検査は、ここに書かれた語だけを文法の語として受け付ける。logic は述語論理の語で、体系の中では定義しない。

領域のファイル（cscl.yaml の include）  種類（nodes）、個体（individuals）、事実（facts）を持つ。どの領域も同じに扱う。
  個体は is で種類に1つだけ属する。事実は動詞の個体で、位置に名前を付けて書く: {is: 動詞, from: 始点, to: 終点}。
  個体は、動詞のその位置の種類に当たらなければならない。検査は、事実を個体ごとに集めた形で読む。
  関係の数（many）、値をそのまま持つ関係（verbatim）、中身から導く比較（derive, via, opposite）は、種類と動詞に書いた宣言から読む。

領域に固有の中身の検査（例: exp の測定値・観察・仮説）は、cscl.yaml の checkers に書いたモジュールが持つ。
この検査は、言語の検査のあと、それぞれの check(T, O, Dm) を呼ぶ。

使い方:
  python cscl/bootstrap/type_checker/type_checker.py              検査
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

sys.modules.setdefault("type_checker", sys.modules[__name__])   # 領域の検査が import type_checker で同じ errors を使う

ROOT = Path(__file__).resolve().parents[3]   # リポジトリの根。cscl/bootstrap/type_checker/ の3つ上
SPEC = ROOT   # 体系のファイルの名前は、根からの相対で書く（cscl.yaml と同じ）
CONFIG = ROOT / "cscl.yaml"   # 体系の範囲（tsconfig に当たる）


def root_name():
    """本体のファイル（リポジトリの根からの相対）。"""
    return str((ROOT / config()["root"]).resolve().relative_to(SPEC))


def config():
    return yload(CONFIG.read_text(encoding="utf-8"))


def library_files():
    """言語の層のファイル（cscl.yaml の library に書いた順）。"""
    out = []
    for g in config().get("library") or []:
        out += [p.resolve() for p in sorted(ROOT.glob(g)) if p.resolve() not in out]
    return out


def scope_of(dom):
    """領域 dom の中で、領域を書かない語をノードの識別子に直す表。自分の領域、使う領域（近いものから）の順に探す。
    同じ近さの2つの領域に同じ名前があれば、その名前は解決しない（領域を書いて参照する）。"""
    if dom in _SCOPES:
        return _SCOPES[dom]
    sc, seen, level = {}, {dom}, [dom]
    while level:
        found = {}
        for d in level:
            for w in LOCALS.get(d, ()):
                found.setdefault(w, set()).add(w if d == "signature" else f"{d}.{w}")
        for w, qs in found.items():
            if w not in sc:
                sc[w] = qs.pop() if len(qs) == 1 else None
        nxt = []
        for d in level:
            for u in USES.get(d, []):
                if u not in seen:
                    seen.add(u)
                    nxt.append(u)
        level = nxt
    _SCOPES[dom] = sc
    return sc


WRITTEN = collections.defaultdict(set)   # (領域, 書かれた語) → 解決した先。法則 one_spelling が読む（syntax_facts の r_written）


def note(dom, w, r):
    if isinstance(w, str) and "." not in w:
        WRITTEN[(dom, w)].add(r)
    return r


def qn_raw(w, dom):
    if not isinstance(w, str) or w == "any" or "." in w:
        return w
    return scope_of(dom).get(w) or w


def qn(w, dom):
    """語をノードの識別子に直す。領域を書いた語（領域.名前）と any は、そのまま。"""
    return note(dom, w, qn_raw(w, dom))


def q_node(n, dom):
    """ノードの式のうち、ノードを指す位置だけを直す（of / form の位置、holds などの状態の型は直さない）。"""
    n = dict(n)
    for k in ("extends", "from", "to", "new_kind"):
        if k in n:
            n[k] = [qn(x, dom) for x in n[k]] if isinstance(n[k], list) else qn(n[k], dom)
    for k in ("of", "form"):
        if isinstance(n.get(k), list) and n[k]:
            n[k] = [qn(n[k][0], dom)] + n[k][1:]
    if "of" in n and "with" in n:   # 名前を付けた限定の、もう一方の端
        n["with"] = qn(n["with"], dom)

    def m1(m):
        if isinstance(m, dict):
            m = dict(m)
            if isinstance(m.get("of"), list) and m["of"]:
                m["of"] = [qn(m["of"][0], dom)] + m["of"][1:]
            if "with" in m:
                m["with"] = qn(m["with"], dom)
            return m
        return qn(m, dom)
    if "mod" in n:
        n["mod"] = [m1(m) for m in n["mod"]] if isinstance(n["mod"], list) else m1(n["mod"])
    if isinstance(n.get("cmp"), list):
        n["cmp"] = [{k: (qn(v, dom) if k in ("a", "b") else v) for k, v in c.items()} if isinstance(c, dict) else c for c in n["cmp"]]
    return n


RULE_VERBS = ("v_assume", "v_derive", "v_require")
RULE_ROLE = {}
# 型検査が名前で読む語（文法の節ごと）。syntax の grammar の同じ節と等しいことを確かめる（翻訳する側が知っている語は、文法に書かれている）
KEYWORDS = {"laws": {"law_rule", "law_given"}, "rule_word": set(RULE_VERBS) | {"v_govern", "variable", "law_relation"},
            "use_word": {"v_use", "v_presume"}, "world": {"world", "closed_world"}}


def qw(w, dom):
    """書き方の語（個体の種類、事実の動詞）を直す。自分の領域で解決しなければ、構文（syntax）の語として読む。
    どの層のファイルも構文で書かれる。書き方が構文に従うことは、意味が構文に依存することではない。"""
    r = qn_raw(w, dom)
    return note(dom, w, qn_raw(w, "syntax") if r == w and isinstance(w, str) and "." not in w else r)


def q_fact(f, dom, V=()):
    """事実の動詞と位置を直す。規則の文（前提・導く文・求める文）では、関係の名は直さず、項だけを直す（変数と位置の名は直さない）。"""
    if not isinstance(f, dict):
        return f
    f = dict(f)
    f["is"] = qw(f.get("is"), dom)
    rule = short(f["is"]) in RULE_ROLE
    for k in ("from", "to", "new"):
        x = f.get(k)
        if isinstance(x, dict):
            x = dict(x)
            if not rule:
                x["is"] = qn(x.get("is"), dom)
            for k2 in ("from", "to", "new"):
                a = x.get(k2)
                if isinstance(a, str) and a not in V and not (rule and x.get("is") == "position" and k2 == "to"):
                    x[k2] = qn(a, dom)
                elif isinstance(a, list):
                    x[k2] = [qn(y, dom) if isinstance(y, str) and y not in V else y for y in a]
            f[k] = x
        elif isinstance(x, str) and not (short(f["is"]) == "v_use"):   # 使う文の端は領域（個体）の名
            f[k] = qn(x, dom)
    return f


def lib_and_domain_files():
    """(ファイル, 領域) を、シグネチャ、言語の層、領域のファイルの順に。"""
    out = [(root_name(), "signature")]
    for p in library_files():
        out.append((str(p.relative_to(ROOT)), (yload(p.read_text(encoding="utf-8")) or {}).get("domain")))
    return out + [(n, d) for d, n in domain_files().items()]


def in_scope(key):
    """cscl.yaml の範囲（include から exclude を除いたもの）にあるファイル。"""
    c = config()
    excl = {p.resolve() for g in c.get("exclude") or [] for p in ROOT.glob(g)}
    return sorted({p.resolve() for g in c.get(key) or [] for p in ROOT.glob(g)} - excl)
TOPS = ()   # 最上位（持続体と生起体）。名前でなく式で決める（tops_of）。読み込みのあと load が置く
VERBATIM_TO = set()   # 終点が字そのもの（verbatim の種類）である動詞。読み込みのあと load が置く
LAYERS = []   # 言語の層。シグネチャと、cscl.yaml の library に書いたファイルの領域を、その順に。読み込みのあと load が置く
LOCALS, USES, _SCOPES = {}, {}, {}   # 領域 → その領域のノードの名前 / 使う領域 / 名前の解決表
errors = []


def atom(f):
    """状態の関係の型（{is: 基礎の関係, from: 位置, to: 位置, neg: 否定}）を (否定, 関係, 位置の並び) に直す。"""
    if not isinstance(f, dict):
        return False, None, ()
    return bool(f.get("neg")), f.get("is"), tuple(f[k] for k in ("from", "to") if k in f)


def truth_of(f):
    """状態の文が述べる真偽。val: {truth: false} なら偽と述べる文（False）、val がなければ真と述べる文（True）。
    neg（述べられていない）とは別。形が合わなければ None。"""
    v = f.get("val")
    if v is None:
        return True
    return v["truth"] if isinstance(v, dict) and set(v) == {"truth"} and isinstance(v["truth"], bool) else None


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


def uses_in(D, dom):
    """領域のファイルが宣言した、使う領域（{is: v_use, from: 自分, to: 使う領域}）。"""
    local = set(D.get("nodes") or {})
    return [f.get("to") for f in D.get("facts") or [] if isinstance(f, dict) and f.get("from") == dom
            and (f.get("is") == "syntax.v_use" or (f.get("is") == "v_use" and ("v_use" not in local or dom == "syntax")))]


def tops_of(N):
    """最上位: 上位も、位置（of・form）も、状態の関係（holds）も持たず、always か sometime を持つノード。
    always（ステップをまたいで在る）が持続体、sometime（在ることが変わる）が生起体。(持続体, 生起体) を返す。"""
    c = [x for x, n in N.items() if not ({"extends", "of", "form", "holds"} & set(n)) and "always" in n]
    o = [x for x, n in N.items() if not ({"extends", "of", "form", "holds"} & set(n)) and "sometime" in n]
    if len(c) != 1 or len(o) != 1:
        err(f"最上位が式から1つに決まらない（always: {c}、sometime: {o}）")
        return tuple(c[:1] + o[:1])
    return c[0], o[0]


def load(name):
    """公理（root）と言語の層（library）を読み、1つの体系 O にまとめる。
    ノードは「層.名前」、個体は名前のまま。層のファイルの中の語は、その層と使う層の順に解決する（scope_of）。"""
    if name != root_name():
        return yaml.load((SPEC / name).read_text(encoding="utf-8"), Loader=_Unique)
    A = yaml.load((SPEC / name).read_text(encoding="utf-8"), Loader=_Unique)
    libs = [(str(p.relative_to(ROOT)), yaml.load(p.read_text(encoding="utf-8"), Loader=_Unique) or {}) for p in library_files()]
    LOCALS["signature"], USES["signature"] = set(A.get("nodes") or {}), uses_in(A, "signature")
    for _, D in libs:
        LOCALS[D["domain"]], USES[D["domain"]] = set(D.get("nodes") or {}), uses_in(D, D["domain"])
    _SCOPES.clear()
    global RULE_ROLE
    RULE_ROLE = {}
    for _f, _D in [(name, A)] + libs:
        if _D.get("domain") != "syntax":
            continue
        for _nid, _n in (_D.get("nodes") or {}).items():
            if isinstance(_n, dict) and _n.get("from") == "law_rule":
                _has = frozenset(k for k in ("pre", "post", "holds") if _n.get(k))
                _r = {frozenset({"pre"}): "assume", frozenset({"post"}): "derive", frozenset({"holds"}): "require"}.get(_has)
                if _r:
                    RULE_ROLE[_nid] = _r
    O = {"base": {}, "axes": {}, "nodes": {}, "individuals": {}, "facts": [],
         "grammar": {}, "runtime": {}, "_idom": {}}
    V = {i for _, D in [(name, A)] + libs for i, x in (D.get("individuals") or {}).items() if short(x.get("is")) == "variable"}
    for fname, D in [(name, A)] + libs:
        dom = D.get("domain")
        for sec in ("base", "axes", "grammar", "runtime"):
            for k, v in (D.get(sec) or {}).items():
                if k in O[sec]:
                    err(f"{fname}: {sec}.{k} は、ほかの層にもある")
                O[sec][k] = v
        for k in D:
            if k not in ("domain", "base", "axes", "grammar", "runtime", "nodes", "individuals", "facts"):
                err(f"{fname}: 節 {k} は、層のファイルに書けない")
        for nid, n in (D.get("nodes") or {}).items():
            O["nodes"][nid if dom == "signature" else f"{dom}.{nid}"] = q_node(n, dom)   # シグネチャの語は領域を書かない（domain()）
        for iid, x in (D.get("individuals") or {}).items():
            if iid in O["individuals"]:
                err(f"{fname}: 個体 {iid} は、ほかの層にもある")
            O["individuals"][iid] = {k: (qw(v, dom) if k == "is" else v) for k, v in x.items()}
            O["_idom"][iid] = dom
        O["facts"] += [q_fact(f, dom, V) for f in D.get("facts") or []]
    core_sections(O)
    for fname, D in libs:
        if D.get("domain") not in O["domains"]:
            err(f"{fname}: 層 {D.get('domain')} は、領域の個体として書かれていない")
    global TOPS
    TOPS = tops_of(O["nodes"])
    VERBATIM_TO.clear()
    VERBATIM_TO.update(short(x) for x, n in O["nodes"].items() if n.get("to") in O["nodes"] and O["nodes"][n["to"]].get("verbatim"))
    LAYERS[:] = list(dict.fromkeys([A.get("domain")] + [D.get("domain") for _, D in libs]))
    return O


def core_sections(O):
    """領域と法則は、ontology.yaml の個体と事実で書く。検査と実行器が読む形に並べる（中身の検査は、ほかと同じく gather が行う）:
    domains: {領域: {display, uses: [使う領域]}}、laws: {法則: {kind, display, assume, derive, require, govern}}。"""
    I, F = O.get("individuals") or {}, O.get("facts") or []
    kinds = set((O.get("grammar") or {}).get("laws") or [])   # 法則の種類は文法が挙げる（laws の下位と等しいことは check_grammar が確かめる）
    O["domains"] = {i: {"display": x.get("display"), "uses": []} for i, x in I.items() if short(x.get("is")) == "domain"}
    O["laws"] = {i: {"kind": short(x["is"]), "display": x.get("display"), "assume": [], "derive": [], "require": [], "govern": []}
                 for i, x in I.items() if short(x.get("is")) in kinds}
    key = {**RULE_ROLE, "v_govern": "govern"}
    for f in F:
        if not isinstance(f, dict):
            continue
        if f.get("is") == "syntax.v_use" and f.get("from") in O["domains"]:
            O["domains"][f["from"]]["uses"].append(f.get("to"))
        elif short(f.get("is")) in key and f.get("from") in O["laws"]:
            t = f.get("to")
            if isinstance(t, dict):   # 規則の中の true / false は語
                t = {k: ("true" if v is True else "false" if v is False else v) if k in ("from", "to") else v for k, v in t.items()}
            O["laws"][f["from"]][key[short(f["is"])]].append(t)


def qualify(x, local, dom):
    """領域のファイルの中で、領域を書かずに書かれた語を、ノードの識別子に直す（自分の領域、使う領域の順）。語1つだけを直す。"""
    return qn(x, dom)


def merge_domain(name, O):
    """領域のファイルを読み、そのノードを体系に加える。領域のファイルは、その領域の種類（nodes）と個体（individuals）と、軸（axes）を持てる。"""
    D = load(name)
    dom = D.get("domain")
    if dom not in O["domains"]:
        err(f"{name}: 領域 {dom} が domains に書かれていない")
    local = set(D.get("nodes") or {})
    D.setdefault("individuals", {})
    for k, v in (D.get("axes") or {}).items():   # 領域の軸（単位など）。軸の名は体系の中で1つ
        if k in O["axes"]:
            err(f"{name}: axes.{k} は、ほかの層か領域にもある")
        O["axes"][k] = v
    for nid, n in (D.get("nodes") or {}).items():
        O["nodes"][f"{dom}.{nid}"] = q_node(n, dom)
    D["individuals"] = {iid: {k: (qn(v, dom) if k == "is" else v) for k, v in x.items()} for iid, x in D["individuals"].items()}
    for iid, x in D["individuals"].items():
        if set(x) - {"is", "display", "val"}:
            err(f"{name} {iid}: 個体には is, display, val だけを書く。関係は facts に書く")
    D["_local"] = local
    return D




def is_kind_fact(f, T, dom, I):
    """位置がすべて種類（個体でなく、動詞でないノード）の事実。種類についての文は「その種類のすべてについて」と読む。"""
    ps = [f.get(p) for p in ("from", "to", "new") if p in f]
    return "at" not in f and len(ps) >= 2 and all(
        isinstance(x, str) and x not in I and x not in T.I and (T.resolve(x, dom) or x) in T.N
        and not T.is_verb(T.resolve(x, dom) or x) for x in ps)


def collect_kind_facts(T):
    """種類どうしの事実を、すべての領域から集めて T.KF に置く。型を確かめる。否定は書かせない
    （書かれていない文は示されていない。否定は法則の制約（v_require）で書く）。"""
    T.KF, T.COLL = [], {}
    for name, dom in lib_and_domain_files():   # 種類の集まり（2階）
        for f in (yload((SPEC / name).read_text(encoding="utf-8")).get("facts") or []):
            if isinstance(f, dict) and T.resolve(f.get("is"), dom) == "syntax.v_collect" and f.get("from") in T.I:
                k = T.resolve(f.get("to"), dom) if isinstance(f.get("to"), str) else None
                if k not in T.N or T.is_verb(k):
                    err(f"{name} の事実 {f}: 集まりの成員は種類（ノード）")
                else:
                    T.COLL[f["from"]] = k   # 段の検査は法則 collection_level（規則）
    for name, dom in lib_and_domain_files():
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
                err(f"{where}: 種類どうしの事実は否定にしない（否定は「示されていない」で、示す文である事実には書けない。否定は法則の制約で書く）")
                continue
            x = {p: T.resolve(f[p], dom) or f[p] for p in ("from", "to", "new") if p in f}
            for p, k in x.items():
                if not T.is_a(k, T.spot_type(verb, p)):
                    err(f"{where}: {p} の種類 {k} が、動詞 {verb} のその位置（{T.spot_type(verb, p)}）に当たらない")
            T.KF.append((verb, x))


def end_word(raw, qd, verb, pos, T):
    """述べる中身の端の語。同じ名の種類と個体があるとき、動詞のその位置の種類に当たる方を取る（種類で決める）。"""
    if not isinstance(raw, str) or raw not in T.I or verb == "is_a" or not T.is_verb(verb):
        return qd
    want = T.end(verb, pos)
    if qd in T.N and not T.overlaps(qd, want) and T.is_a(T.I[raw], want):
        return raw
    return qd


def gather(D, T, name):
    """事実を、個体ごとに集める。検査は、集めた形（個体 → {関係の名: 値}）を読む。
    事実は動詞の個体: {is: 動詞, from, to, new, at, neg}。位置には名前を付ける。
    - 個体が、動詞のある位置の種類に当たるとき、その個体についての事実。関係の名は、もう一方の位置の種類。
    - at を持つ事実は、始点の種類のものがいくつ終点の部分になるか（個数）。関係の名は、始点の種類。
    - v_refer の終点が事実の形をしていれば、それは文が述べる中身（主張ではない）。s, p, o と、動詞が新しく取る位置の値 new として読む。"""
    dom, local, I = D["domain"], D["_local"], D["individuals"]
    q = lambda v: [qualify(y, local, dom) for y in v] if isinstance(v, list) else qualify(v, local, dom)
    BV = {}
    for i, f in enumerate(D.get("facts") or []):
        where = f"{name} facts[{i}]"
        if not isinstance(f, dict) or set(f) - set(T.G["facts"]) or "is" not in f:
            err(f"{where}: 事実は {{is: 動詞, from: 始点, to: 終点}} で書き、語は grammar.facts のものだけ")
            continue
        if "val" in f:   # 偽と述べる文は、いまは状態（pre・post と実行の記録）でだけ読む
            err(f"{where}: val（真偽を述べる）は、pre・post と実行の記録の文にだけ書く")
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
        elif short(verb) == "v_refer" and isinstance(f.get("to"), dict):
            P = f["to"]
            subj = f.get("from")
            if subj in I:
                I[subj]["p"] = "is_a" if P.get("is") == "extends" else q(P.get("is"))
                I[subj]["s"], I[subj]["o"] = (end_word(P.get(k), q(P.get(k)), I[subj]["p"], k, T) for k in ("from", "to"))
                if "new" in P:
                    I[subj]["new"] = P["new"]
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
            val = f.get(other) if rel in T.verbatim else q(f.get(other))
        if subj not in I:
            err(f"{where}: 始点 {subj} が個体でない")
            continue
        I[subj].setdefault(rel, []).append(val)
        BV.setdefault((subj, rel, short(verb)), []).append(val)
    for subj, x in I.items():
        for rel, vs in list(x.items()):
            if isinstance(vs, list) and rel not in T.G["individuals"] and rel not in ("o", "_at"):
                if rel not in T.many and any(len(w) > 1 for (s2, r2, _), w in BV.items() if s2 == subj and r2 == rel):
                    err(f"{name} {subj}: 関係 {rel} の事実が2つ以上ある")
                x[rel] = vs if rel in T.many else vs[0]
    for (s2, r2, v2), w in BV.items():
        I[s2][f"{r2}.{v2}"] = w if r2 in T.many else w[0]


def compare_claims(T, a, b):
    """2つの文の中身（s, p, o）を比べる。両端が同じか上位・下位の関係にあるときだけ比べられる。
    返す値: same（動詞が同じか上位・下位）、opposite（動詞が、opposite で宣言された反対の組）、other（両端は合うが動詞が別）、
    None（両端が合わない）。"""
    as_ = lambda v: v if isinstance(v, list) else [v]
    if not a.get("p") or not b.get("p"):
        return None
    if not all(any(T.overlaps(x, y) for x in as_(a.get(k)) for y in as_(b.get(k))) for k in ("s", "o")):
        return None
    if T.overlaps(a["p"], b["p"]):
        return "same"
    up = lambda v: [v, *T.ancestors(v)]
    opp = lambda x, y: any(short(T.N[u]["opposite"]) in {short(z) for z in up(y)}
                           for u in up(x) if u in T.N and T.N[u].get("opposite"))
    return "opposite" if opp(a["p"], b["p"]) or opp(b["p"], a["p"]) else "other"


def check_derived(D, T, name):
    """derive を持つ動詞の事実（始点 a から終点 h へ）を確かめる。a が via の動詞で述べる文のどれかと h の中身を比べ、
    derive の結果（same か opposite）が導けること。a が via で何も述べていなければ、導けないので誤り。"""
    dom, local, I = D["domain"], D["_local"], D["individuals"]
    q = lambda v: qualify(v, local, dom)
    facts = [f for f in D.get("facts") or [] if isinstance(f, dict) and isinstance(f.get("is"), str)]
    for f in facts:
        n = T.N.get(q(f["is"])) or {}
        want, via = n.get("derive"), n.get("via")
        if not want:
            continue
        a, h = f.get("from"), f.get("to")
        claims = [g.get("to") for g in facts if q(g["is"]) == q(via) and g.get("from") == a]
        got = [compare_claims(T, I[h], I[c]) for c in claims if c in I and h in I]
        if not claims:
            err(f"{name}: {a} → {h} は「{n.get('display')}」と書かれているが、{a} は {short(via)} で何も述べていないので、中身から導けない")
        elif want not in got:
            err(f"{name}: {a} → {h} は「{n.get('display')}」と書かれているが、{a} の述べる文の中身から導くと {got}")


def law_rules(O):
    return [(lid, l) for lid, l in O["laws"].items() if l["kind"] == "law_rule"]


def variables(O):
    return {i for i, x in (O.get("individuals") or {}).items() if short(x.get("is")) == "variable"}


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


class Count:
    """前提の原子の個数の限定（at: {count: c}）。束縛済みの変数を固定して、原子を満たす組の数が c に入ること。"""
    def __init__(self, want):
        self.want = want

    def ok(self, v):
        w = self.want
        if isinstance(w, dict):
            (op, arg), = w.items()
            return {"gt": v > arg, "ge": v >= arg, "lt": v < arg, "le": v <= arg}.get(op, True)
        return w == v


def counted(f):
    """原子が個数の限定を持てば Count を返す。"""
    c = (f.get("at") or {}).get("count") if isinstance(f, dict) and isinstance(f.get("at"), dict) else None
    return Count(c) if c is not None else None


def compile_atoms(atoms):
    """前提の並びを (否定, 関係, 位置の並び) に直し、肯定を先に並べる。個数の限定を持つ原子は、否定の位置に Count を置く。"""
    out = []
    for f in atoms:
        neg, rel, args = atom(f)
        out.append((counted(f) or neg, rel, args))
    return sorted(out, key=lambda a: 0 if a[0] is False else 1)


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
    if isinstance(neg, Count):
        if neg.ok(sum(1 for _ in F.find(rel, pat))):
            yield from _match(cs, i + 1, F, V, b, first)
        return
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
                        need = st[r] + (1 if neg or counted(p) else 0)
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
# 意味を検査が与える法則（law_given）のうち、実行の検査（cscl/bootstrap/runtime/runtime.py）が当てはめるもの
# 規則で書いた法則（law_rule）は、検査がその規則を読んで当てはめる。
LAWS_RUN = {"unique_names", "step", "frame", "halt", "no_confusion"}


class Ontology:
    def __init__(self, O):
        self.O = O
        self.B, self.AX, self.N, self.G = O["base"], O["axes"], O["nodes"], O["grammar"]
        self.I, self.Idom, self.Isubj = {}, None, {}   # 個体の識別子 → 種類、名前を解決する既定の領域（領域の検査が設定する）、個体が書かれた領域
        for nid, n in self.N.items():  # mod は単一。中では並びとして扱う（限定の数は法則 single の規則が確かめる）
            if isinstance(n.get("extends"), list):
                err(f"{nid}: extends は並べない。AND は「属する」（is）で限定して書く")
                n["extends"] = n["extends"][0]
            if "mod" in n:
                if isinstance(n["mod"], list):
                    err(f"{nid}: mod は並べない。限定は1つだけ")
                else:
                    n["mod"] = [n["mod"]]
        # 名前を付けた限定（修飾語）は、中身に展開して、その場に書いた限定と同じに扱う。名前は mod_name に残す
        self.mod_name = {}
        for nid, n in self.N.items():
            for i, m in enumerate(n.get("mod") or []):
                if isinstance(m, str) and m in self.N and "of" in self.N[m]:
                    n["mod"][i] = {k: self.N[m][k] for k in ("of", "with", "neg", "at") if k in self.N[m]}
                    self.mod_name[(nid, i)] = m
        # 真偽を返す範囲の判定式。値の一種。gt などは文法の function、between は述語論理の語
        self.funcs = {op: 1 for op in self.G["function"]} | ({"between": 2} if "between" in self.G["logic"] else {})
        self.anchor()

    def anchor(self):
        """検査が読む語を、名前でなく式から決める。どれも、条件に当たるノードがちょうど1つであることを確かめる。"""
        N = self.N
        self.top_c, self.top_o = (TOPS + (None, None))[:2]
        mods = lambda x: [m for m in N[x].get("mod") or [] if isinstance(m, dict)]
        atoms = lambda x: [(a.get("is"), a.get("from"), a.get("to"), bool(a.get("neg"))) for a in N[x].get("holds") or []]

        def one(what, xs):
            if len(xs) != 1:
                err(f"{what} が式から1つに決まらない（{sorted(xs)}）")
            return xs[0] if xs else None

        under_o = [x for x, n in N.items() if n.get("extends") == self.top_o]
        self.v_relate = one("関係づける（在るものどうしの動詞）", [x for x in under_o if N[x].get("from") == "any" and N[x].get("to") == "any"
                                                   and sorted(atoms(x)) == [("exists", "from", None, False), ("exists", "to", None, False)]])
        self.v_is = one("属する", [x for x, n in N.items() if n.get("extends") == self.v_relate and "to" in n and "holds" not in n])
        self.v_depend = one("依存する", [x for x in N if atoms(x) == [("depend", "from", "to", False)]
                                       and N[x].get("from") == self.top_c and N[x].get("to") == self.top_c])
        self.sdc = one("特定依存持続体", [x for x in N if any(m.get("of") == [self.v_depend, "from"] and (m.get("at") or {}).get("count") == 1
                                                         and not m.get("neg") and "with" not in m for m in mods(x))])
        self.quality = one("質", [x for x, n in N.items() if n.get("extends") == self.sdc and any(m.get("neg") for m in mods(x))])
        self.magnitude = one("大きさ", [x for x, n in N.items() if n.get("extends") == self.quality
                                      and any(m.get("with") == self.quality and not m.get("neg") for m in mods(x))])
        self.verb_ref = one("動詞を指すもの", [x for x in N if any(m.get("of") == [self.v_is, "to"] and m.get("with") == self.top_o
                                                          and not m.get("neg") for m in mods(x))])

    def check_grammar(self):
        """文法の語が、体系のノードに当たっていること。体系の各節が、文法に書かれた語だけを使っていること。"""
        G = self.G
        for sect, words in G.items():
            if sect not in G["grammar"]:
                err(f"grammar: 節 {sect} が、grammar.grammar に書かれていない")
            for w in words:
                if self.resolve(w, "syntax") is None:
                    err(f"grammar.{sect}: 語 {w} がノードになっていない")
        for sect, ws in KEYWORDS.items():
            if set(G.get(sect) or []) != ws:
                err(f"grammar.{sect}: 型検査が名前で読む語 {sorted(ws)} と、文法に書かれた語 {sorted(G.get(sect) or [])} が違う")
        below = {short(n) for n in self.N if n != "syntax.laws" and self.is_a(n, "syntax.laws")}
        if set(G.get("laws") or []) != below:   # 法則の種類は、体系の分類（laws の下位）と同じ
            err(f"grammar.laws: 文法に書かれた法則の種類 {sorted(G.get('laws') or [])} が、laws の下位 {sorted(below)} と違う")
        L = self.O["laws"]
        for lid, l in L.items():
            where = f"法則 {lid}"
            if l["kind"] == "law_rule":
                if not l["assume"] or not (l["derive"] or l["require"]) or l["govern"]:
                    err(f"{where}: 規則で書いた法則は、前提と、導く文か求める文を持ち、掛かる節を持たない")
                V = variables(self.O)
                rels = set(self.B) | {short(n) for n in self.N} | {i for i, x in (self.O.get("individuals") or {}).items() if short(x.get("is")) == "law_relation"}
                bound = {a for f in l["assume"] if not atom(f)[0] and not counted(f) for a in atom(f)[2] if a in V}
                for part in ("assume", "derive", "require"):
                    for f in l[part]:
                        neg, rel, args = atom(f)
                        keys = {"is", "from", "to", "neg"} | ({"at"} if part == "assume" and counted(f) and set(f["at"]) == {"count"} else set())
                        if not isinstance(f, dict) or set(f) - keys or rel not in rels or not args:
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
                if lid not in LAWS_RUN:
                    err(f"{where}: 当てはめる検査がない")
        for lid in LAWS_RUN - {k for k, l in L.items() if l["kind"] == "law_given"}:
            err(f"法則 {lid} を検査が当てはめているが、law_given の個体として書かれていない")
        for k, v in self.O["runtime"].items():
            if k not in G["runtime"]:
                err(f"runtime: 語 {k} が、grammar.runtime に書かれていない")
            elif self.resolve(v, "runtime") is None or not self.is_a(self.resolve(v, "runtime"), self.resolve(k, "runtime")) and not (k == "pre_rule" and v in G["logic"]):
                err(f"runtime.{k}: 値 {v} が、{k} の下位のノードでない")
        for k in self.O:
            if not k.startswith("_") and k not in G["system"] and k not in ("domains", "laws"):   # 個体と事実から並べた形（core_sections）
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
            up, seen = a.get("extends"), {aid}
            while up is not None:   # 上位の軸は、定義された軸で、値の種類が同じで、輪にならない
                if up not in self.AX or up in seen or self.AX[up]["value"] != a["value"]:
                    err(f"axes.{aid}: 上位の軸 {a['extends']} が、定義された同じ値の種類の軸でないか、輪になる")
                    break
                seen.add(up)
                up = self.AX[up].get("extends")

    def resolve(self, word, dom):
        """領域を書かない語を、ノードの識別子に解決する。その領域、signature、ほかの領域にただ1つ、の順に探す。"""
        if word == "any":   # シグネチャの語
            return word
        if f"{dom}.{word}" in self.N:
            return f"{dom}.{word}"
        if word in self.N:
            return word
        found = [i for i in self.N if i.split(".", 1)[-1] == word]
        return found[0] if len(found) == 1 else None

    def domain(self, nid):
        return nid.split(".", 1)[0] if "." in nid else "signature"

    def refs(self, nid):
        """ノードの式が参照しているノード。"""
        n, out = self.N[nid], set(self.parents(nid))
        for k in ("from", "to", "new_kind", "with"):
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
            if isinstance(m, dict) and m.get("of") == [self.v_is, "from"] and not m.get("neg") and m.get("with") in self.N:
                out.append(m["with"])
        return out

    def up(self, nid):
        ps = self.parents(nid)
        return ps[0] if ps else None

    @property
    def verbatim(self):
        """値をそのまま持つ関係の名（終点の種類に verbatim: true を書いたもの）。値を語として解決しない。"""
        return {short(k) for k, n in self.N.items() if isinstance(n, dict) and n.get("verbatim")}

    @property
    def many(self):
        """複数を許す関係の名（終点の種類に many: true を書いたもの）。"""
        return {short(k) for k, n in self.N.items() if isinstance(n, dict) and n.get("many")}

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
        phrases = mod_phrases(self)   # 部分の限定の句は、限定の式から作り、限定の表示語として書く
        for (dom, w), rs in WRITTEN.items():   # 法則 one_spelling が読む
            for r in rs:
                add("r_written", f"{dom}:{w}", r)
        for aid, a in self.AX.items():   # 軸の上下は「下位の軸の値は、上位の軸の上にある」と読み、axis の文に訳す（法則 entail_by_axis が読む）
            if isinstance(a.get("extends"), str):
                add("axis", aid, a["extends"])
        for nid, n in self.N.items():
            add("exists", nid)
            if "of" in n and not self.is_verb(nid):
                add("mod_content", nid, dump({k: n[k] for k in ("of", "with", "neg", "at") if k in n}))
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
            if "of" in n:   # 名前を付けた限定は、式の中の限定と同じ語で書く
                if isinstance(n.get("with"), str):
                    add("with", nid, n["with"])
                if n.get("neg"):
                    add("neg", nid, "true")
                for k in ("quant", "at"):
                    if n.get(k) is not None:
                        add(k, nid, dump(n[k]))
            for k in ("holds", "pre"):
                for i, _ in enumerate(n.get(k) or []):
                    add(k, nid, i)
            for i_m, m in enumerate(n.get("mod") or []):
                t = dump(m) if isinstance(m, dict) else m
                add("mod", nid, t)
                if (nid, i_m) in phrases:
                    add("display", t, phrases[(nid, i_m)])
                if (nid, i_m) in self.mod_name:
                    add("mod_by_name", nid, t)
                if isinstance(m, dict):
                    if isinstance(m.get("of"), list) and len(m["of"]) == 2:
                        add("of", t, m["of"][0])
                        add("position", t, m["of"][1])
                    if m.get("with") is not None:
                        add("with", t, m["with"])
                    if m.get("neg"):
                        add("neg", t, "true")
                    for k in ("quant", "at"):
                        if m.get(k) is not None:
                            add(k, t, dump(m[k]))
                    for a in (m.get("at") or {}) if isinstance(m.get("at"), dict) else ():   # 限定が値を指定する軸（法則 at_axis が読む）
                        add("axis", t, a)
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
            add("of", t, "syntax.v_collect")
            add("from", t, c)
            add("to", t, k)
        for i in self.I:
            if isinstance(self.I[i], str):
                add("is", i, self.I[i])
            add("domain", i, "signature" if i in (self.O.get("individuals") or {}) else self.Isubj.get(i, self.Idom))
        for aid, a in self.AX.items():
            add("exists", aid)
            for v in a["value"] if isinstance(a["value"], list) else []:
                add("value", aid, "true" if v is True else "false" if v is False else v)
        for v in self.N:
            if not self.is_verb(v):
                continue
            for i, h in enumerate(self.end(v, "holds") or []):
                if isinstance(h, dict) and h.get("is") == "part":
                    hp = f"holds_part {v} {i}"
                    add("part_of_verb", hp, v)
                    add("part_from", hp, hp + " from")
                    add("part_to", hp, hp + " to")
                    add("position", hp + " from", h.get("from"))
                    add("position", hp + " to", h.get("to"))
        for name, dom in lib_and_domain_files():
            for j, f in enumerate(yload((SPEC / name).read_text(encoding="utf-8")).get("facts") or []):
                if not isinstance(f, dict) or not isinstance(f.get("is"), str):
                    continue
                v = self.resolve(f["is"], dom)
                r = lambda x: (x if x in self.I else (self.resolve(x, dom) or x)) if isinstance(x, str) else None
                a, b = r(f.get("from")), r(f.get("to"))
                if v and a and b:
                    t = f"ifact {name} {j}"
                    add("fact_verb", t, v)
                    add("fact_from", t, a)
                    add("fact_to", t, b)
        for dom, ws in presumed_worlds().items():
            for w in ws:
                add("presume", dom, qn_raw(w, "syntax"))
        for lid, l in self.O.get("laws", {}).items():
            add("law_domain", lid, self.O["_idom"].get(lid))
            if any(isinstance(a, dict) and a.get("neg") for a in l.get("assume") or []):
                add("assume_neg", lid, "true")
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
        """検査が名前で参照する語を、ノードの識別子に解決する（領域を書かない語は、個体の領域、signature の順に探す）。"""
        if not isinstance(w, str) or w in self.N or w in self.I or w == "any":
            return w
        return self.resolve(w, self.Idom or "signature") or w

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
                if isinstance(f, dict) and "val" in f and (key == "holds" or truth_of(f) is None or f.get("neg")):
                    err(f"{vid}: {key} の {f}: val は pre・post にだけ、{{truth: true か false}} の形で、neg と別に書く")
                    continue
                ok = isinstance(f, dict) and not set(f) - set(self.G["facts"]) - {"at"} and f.get("is") in self.B
                args = atom(f)[2] if ok else ()
                if not ok or "at" in f or len(args) != self.B[f["is"]]["arity"] or any(a not in self.G["position"] for a in args):
                    err(f"{vid}: {key} の {f} が、基礎の関係と位置で書かれていない")

    def check_primitives(self, nid, n):
        """always（どのステップでも）・sometime（あるステップで pre から post へ）・ranges（変数の範囲）。原子の項は self だけ。"""
        def atoms_ok(key, fs):
            if not isinstance(fs, list) or not fs:
                return err(f"{nid}: {key} は原子の並びで書く")
            for f in fs:
                ok = isinstance(f, dict) and not set(f) - set(self.G["facts"]) and f.get("is") in self.B and "val" not in f
                args = atom(f)[2] if ok else ()
                if not ok or len(args) != self.B[f["is"]]["arity"] or any(a != "self" for a in args):
                    err(f"{nid}: {key} の {f} が、基礎の関係と項 self で書かれていない")
        if "always" in n:
            atoms_ok("always", n["always"])
        if "sometime" in n:
            if not isinstance(n["sometime"], list) or not n["sometime"]:
                err(f"{nid}: sometime は変化の並びで書く")
            for i, c in enumerate(n["sometime"] if isinstance(n["sometime"], list) else []):
                if not isinstance(c, dict) or set(c) != {"pre", "post"}:
                    err(f"{nid}: sometime[{i}] は pre と post の両方で書く")
                    continue
                atoms_ok(f"sometime[{i}].pre", c["pre"])
                atoms_ok(f"sometime[{i}].post", c["post"])
                if sorted(map(atom, c["pre"])) == sorted(map(atom, c["post"])):
                    err(f"{nid}: sometime[{i}] の pre と post が同じ（変化がない）")
        if "ranges" in n:
            r = n["ranges"]
            if r not in self.I or not self.is_a(self.I[r], "variable"):
                err(f"{nid}: ranges の {r} は変数でない")

    def grounding(self, nid):
        return [m["with"] for x in [nid] + self.ancestors(nid) for m in (self.N[x].get("mod") or [])
                if isinstance(m, dict) and m.get("of") == [self.v_depend, "from"] and "with" in m and not m.get("neg")
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
        seen = {}
        for nid, n in N.items():
            ja = n.get("display")
            key = (self.domain(nid), ja)  # 法則 unique_in_domain
            if not ja:
                err(f"{nid}: 表示語がない")
            seen[key] = nid
            if nid in TOPS or nid == "any":   # 最上位と、シグネチャの any
                if set(n) - {"display", "many", "mod", "always", "sometime", "ranges", "gloss"}:
                    err(f"{nid}: 最上位は display・many・mod・always・sometime・ranges・gloss だけを持つ")
                self.check_primitives(nid, n)
                continue
            if "gloss" in n:
                err(f"{nid}: gloss を持てるのは最上位の2つだけ。式で書くこと")
            self.check_primitives(nid, n)
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
                if not self.is_a(nid, self.top_o):
                    err(f"{nid}: 動詞は生起体の下に置く")
                if self.is_verb(self.up(nid)):
                    if not any(k in n for k in ("from", "to", "mod")) and len(self.parents(nid)) < 2:
                        err(f"{nid}: 上位の動詞と区別する式がない")
                else:
                    self.check_state(nid, n)
            elif "of" in n:
                self.check_spot(n["of"], nid)
                if "with" in n and n["with"] not in N and n["with"] != "any":
                    err(f"{nid}: with の {n['with']} が未定義")
                if not self.is_a(nid, self.sdc):
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
            for key in ("opposite", "via"):
                if key in n and not (self.is_verb(nid) and self.resolve(short(n[key]), nid.split(".")[0]) and self.is_verb(self.resolve(short(n[key]), nid.split(".")[0]))):
                    err(f"{nid}: {key} を書けるのは動詞だけで、値も動詞")
            if "derive" in n and (n["derive"] not in ("same", "opposite") or "via" not in n):
                err(f"{nid}: derive は same か opposite で、via と組で書く")
            if "axis" in n:
                if n["axis"] not in AX or AX[n["axis"]]["value"] != "number":
                    err(f"{nid}: axis {n['axis']} は数の軸でない")
                if not self.is_a(nid, self.quality):
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
                if "with" in m:
                    other = {"from": "to", "to": "from"}.get(pos)
                    if other is None:
                        err(f"{where}: 位置 new には with を付けられない")
                    elif verb == self.v_is and other == "to":   # 「属する」の終点は、種類そのもの（その成員ではない）
                        if m["with"] not in N or not self.is_concept(m["with"]):
                            err(f"{where}: {m['with']} は種類でない")
                    elif self.is_a(self.end(verb, other), self.verb_ref):   # 動詞を受け取る位置: 来るのは動詞そのもの
                        if not self.is_verb(m["with"]):
                            err(f"{where}: {m['with']} は動詞でない。{verb} の {other} は動詞を受け取る")
                if set(m) - set(self.G["mod"]):
                    err(f"{where}: 語 {set(m) - set(self.G['mod'])} が、grammar.mod に書かれていない")
                if m.get("quant") is not None and m["quant"] not in self.G["logic"]:
                    err(f"{where}: 数量化 {m['quant']} が、grammar.logic に書かれていない。数は at で書く")
                for axis, v in (m.get("at") or {}).items():
                    self.check_value(axis, v, where)
                    if axis in AX and AX[axis]["source"] != "any" and AX[axis]["source"] not in self.base_of(verb):
                        err(f"{where}: 軸 {axis} は基礎の関係 {AX[axis]['source']} を抽象にしたものだが、{verb} はそれを使っていない")
        self.roles = [nid for nid in N if nid != "syntax.role" and "form" not in N[nid] and self.is_a(nid, "role")]
        for nid in self.roles:
            g = self.grounding(nid)
            if not g:
                err(f"{nid}: 役割だが、根拠となる定義（依存する定義）がない")
            elif all(x == "syntax.definition" for x in g):
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

    def field_ok(self, kind, f, dom="signature"):
        """種類 kind の個体に、項目 f を書けるか。項目の表は持たず、式から決める。
        f が動詞かその位置の形（s, p, o）: kind が「について述べる」の始点に来る種類（文）であること。
        それ以外: f かその下位に、kind のものとの関係で限定されたノードがあること。または、kind の式が f のものとの関係で限定されていること。"""
        kind, f = self.q(kind), f if f in self.N else self.resolve(f, dom)
        if f is None:
            return False
        if "form" in self.N[f] or self.is_verb(f):
            return any(m["of"] == ["syntax.v_refer", "from"] for m in self.mods_of(kind))
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
            if isinstance(v, (int, float)) and not isinstance(v, bool) and f in self.N and not self.is_a(f, self.magnitude):
                for m in self.mods_of(kind):
                    want = (m.get("at") or {}).get("count")
                    if want is not None and m.get("with") in self.N and self.is_a(f, m["with"]) and not self.count_ok(want, v):
                        err(f"{where}: {f} の個数 {v} が、種類 {kind} の限定 {want} に入っていない")

    def kinds_of(self, nid):
        """nid の下位のうち、それより下を持たないノード。status や留保の値として使えるもの。"""
        nid = self.q(nid)
        has_child = {p for k in self.N for p in self.parents(k)}
        return [k for k in self.N if k not in has_child and k != nid and nid in self.ancestors(k)]

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
            body = {k: n[k] for k in ("from", "to", "new_kind", "holds", "pre", "post", "always", "sometime", "ranges", "form", "of", "neg", "mod", "val", "cmp", "axis", "gloss") if k in n}
            out.append(f"{nid}（{n['display']}） {body}")
            nid, hops = self.parent(nid), hops + 1
        return "\n  ← ".join(out)


def natural_language_only_in_ja(name, x, path=()):
    """自然言語を書けるのは、表示名 display だけ。例外は、字そのものが値であるもの:
    最上位2つの gloss、選択肢の字（val.text）、終点が字そのもの（verbatim）である動詞の事実。"""
    if isinstance(x, dict):
        if short(x.get("is")) in VERBATIM_TO:
            return
        for k, v in x.items():
            natural_language_only_in_ja(name, v, path + (str(k),))
    elif isinstance(x, list):
        for v in x:
            natural_language_only_in_ja(name, v, path)
    elif isinstance(x, str) and re.search(r"[^\x00-\x7f]", x):
        top = path[:1] == ("nodes",) and path[-1] == "gloss" and path[1] in {short(t) for t in TOPS} | {"any"}
        opt = path[:1] == ("individuals",) and path[-2:] == ("val", "text")
        if path[-1:] != ("display",) and not top and not opt:
            err(f"{name} {'.'.join(path)}: 自然言語は表示名 display にだけ書く（{x[:20]}）")


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
        O["domains"][dom] = {"display": me.get("display"), "uses": uses_in(y, dom)}
        LOCALS[dom], USES[dom] = set(y.get("nodes") or {}), uses_in(y, dom)
        _SCOPES.clear()
        for f in y.get("facts") or []:
            if isinstance(f, dict) and f.get("is") in ("v_use", "syntax.v_use") and f.get("from") != dom and f.get("to") is not None \
                    and (f.get("is") == "syntax.v_use" or "v_use" not in (y.get("nodes") or {})):
                err(f"{name}: 領域の使用は、自分の領域についてだけ書く（{f}）")
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


def mod_phrases(T):
    """部分の限定の句を、限定の式から作る: {(ノード, 限定の番号): 句}。名前で読まず、動詞の定義（holds の part・位置・new_kind・上位）から読む。
    相手は with（なければ、その位置に来る種類のどれか: new_kind か、反対の位置の種類）。助詞と語尾は日本語の文法なので、ここに書く。"""
    ind = dict(T.O.get("individuals") or {})
    for name, _ in lib_and_domain_files():
        ind |= (load(name) or {}).get("individuals") or {}

    def disp(x):
        if not isinstance(x, str):
            return None
        if (T.N.get(T.q(x)) or {}).get("display"):
            return T.N[T.q(x)]["display"]
        for k in (x, x.split(".")[-1]):
            if isinstance(ind.get(k), dict) and isinstance(ind[k].get("display"), str):
                return ind[k]["display"]
        return None

    def stem(v):
        a, hops = v, 0
        while a in T.N and hops < 50:
            if (T.N[a].get("display") or "").endswith("になる"):
                return T.N[a]["display"].removesuffix("になる")
            a, hops = T.up(a), hops + 1
        return None

    out = {}
    for nid, n in T.N.items():
        if T.is_verb(nid):
            continue
        for i, m in enumerate(n.get("mod") or []):
            if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2 or T.q(m["of"][0]) not in T.N:
                continue
            v, pos = T.q(m["of"][0]), m["of"][1]
            wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
            parts = {(h["from"], h["to"]) for h in T.end(v, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"}
            r = "part" if (pos, wpos) in parts else "whole" if (wpos, pos) in parts else None
            if r is None:
                continue
            w = m.get("with") if isinstance(m.get("with"), str) else (T.end(v, "new_kind") or T.end(v, wpos))
            s = stem(v) or "部分"
            if disp(w):
                say = (f"の{s}でない" if m.get("neg") else f"の{s}である") if r == "part" else (f"を{s}に持たない" if m.get("neg") else f"を{s}に持つ")
                out[(nid, i)] = disp(w) + say
    return out


def presumed_worlds():
    """各領域が自分について前提に置く、書かれていない文の扱い（{is: v_presume, from: 自分, to: 扱い}）。書いたままの事実から読む。"""
    out = {}
    for name, dom in lib_and_domain_files()[1:]:
        for f in (load(name) or {}).get("facts") or []:
            if isinstance(f, dict) and short(f.get("is") or "") == "v_presume":
                if f.get("from") != dom:
                    err(f"{name}: 領域 {dom} が、ほかの領域 {f.get('from')} の前提を置いている")
                    continue
                out.setdefault(dom, set()).add(short(f.get("to") or ""))
    return out


def check_domain(name, D, T):
    """領域のファイルの形と、個体の種類・値・項目の数を確かめる。どの領域にも同じ検査をする。"""
    for k in D:
        if k not in T.G["domain"] and k != "_local":
            err(f"{name}: 語 {k} が、grammar.domain に書かれていない")
    for iid, x in D["individuals"].items():
        if iid in T.N or T.resolve(iid, D["domain"]):
            err(f"{name} {iid}: 個体の識別子が、ノードの識別子と重なっている")
        kind = x.get("is")
        if kind not in T.N:
            err(f"{name} {iid}: 種類 {kind} がノードでない")
            continue
        for ax, v in (x.get("val") or {}).items():
            T.check_value(ax, v, f"{name} {iid}")
        T.check_counts(kind, {f: v for f, v in x.items() if f not in T.G["individuals"] and f != "_at"}, f"{name} {iid}")


def checkers():
    """cscl.yaml の checkers に書いた、領域に固有の検査のモジュール。{領域: モジュール}。"""
    import importlib.util
    out = {}
    for dom, path in (yaml.safe_load(CONFIG.read_text(encoding="utf-8")).get("checkers") or {}).items():
        spec = importlib.util.spec_from_file_location(f"checker_{dom}", ROOT / path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out[dom] = mod
    return out


def build():
    """体系を読み、言語の検査をする。(体系, ontology, 領域 {領域: (ファイル名, 中身)}) を返す。誤りは errors に積む。
    領域のファイルは自分で見つけ、使う領域の順に読む。どの領域も同じ扱いで読み、領域に固有の中身の検査はしない（check_all が呼ぶ）。"""
    O = load(root_name())
    natural_language_only_in_ja(root_name(), yload(open(SPEC / root_name())))
    order = register_domains(O)
    Dm = {}
    for dom, name in order:
        Dm[dom] = (name, merge_domain(name, O))
        VERBATIM_TO.update(short(x) for x, n in O["nodes"].items() if n.get("to") in O["nodes"] and O["nodes"][n["to"]].get("verbatim"))
        natural_language_only_in_ja(name, yload(open(SPEC / name)))
    T = Ontology(O)
    core = {iid: dict(x) for iid, x in (O.get("individuals") or {}).items()}
    for iid, x in core.items():
        if iid in T.N:
            err(f"ontology.yaml {iid}: 個体の識別子が、ほかの個体かノードと重なっている")
        if set(x) - set(T.G["individuals"]) or x.get("is") not in T.N:
            err(f"ontology.yaml {iid}: 個体は {{is: 種類, display}} で書き、種類はノード")
    T.I |= {iid: x.get("is") for iid, x in core.items() if x.get("is") in T.N}
    for dom, (name, X) in Dm.items():
        for iid, x in X["individuals"].items():
            if not isinstance(x.get("is"), str):
                err(f"{name} {iid}: is は種類を1つだけ書く。並べない")
                x["is"] = None
            if iid in T.I or iid in T.N or iid in core:
                err(f"{name} {iid}: 個体の識別子が、ほかの個体かノードと重なっている")
        T.I |= {iid: x.get("is") for iid, x in X["individuals"].items() if x.get("is") in T.N}
        T.Isubj |= {iid: dom for iid in X["individuals"]}
    gather({"domain": "signature", "_local": set(), "individuals": core, "facts": O.get("facts")}, T, "ontology.yaml")
    for dom, (name, X) in Dm.items():
        gather(X, T, name)
        check_derived(X, T, name)
    collect_kind_facts(T)
    T.check()
    T.check_grammar()
    T.check_domains()
    T.check_laws()
    for dom, (name, X) in Dm.items():
        check_domain(name, X, T)
    return T, O, Dm


def check_all():
    """言語の検査のあと、cscl.yaml の checkers に書いた領域ごとの検査を呼ぶ。(体系, ontology, 領域, {領域: 検査の結果}) を返す。"""
    T, O, Dm = build()
    out = {dom: mod.check(T, O, Dm) for dom, mod in checkers().items() if dom in Dm}
    return T, O, Dm, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expr")
    args = ap.parse_args()
    T, O, Dm, out = check_all()
    if args.expr:
        print(T.expr(args.expr if args.expr in T.N else next((r for d in Dm if (r := T.resolve(args.expr, d))), args.expr)))
    if errors:
        print(f"検査に失敗: {len(errors)} 件")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    N = T.N
    verbs = sum(1 for n in N.values() if "holds" in n or "pre" in n)
    print(f"検査に成功: ノード {len(N)}（うち動詞の語根 {verbs}、役割 {len(T.roles)}）、基礎の関係 {len(T.B)}、分類の軸 {len(T.AX)}、領域 {len(Dm)}")
    for dom, r in out.items():
        if r:
            print(f"  {dom}: {r}")


if __name__ == "__main__":
    main()
