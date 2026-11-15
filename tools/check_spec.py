"""spec/ の検査と値の計算。

spec/ が正本。文章（docs/, experiments/README.md）は正本ではない。

ontology.yaml  概念の体系。書き方はそのファイルの冒頭を見よ。
  検査: 表示語の一意性 / gloss を持つのは最上位の2つだけ / 動詞の式（状態の関係・両端・第三のものの種類）の一意性 /
        動詞の下位が端を狭めていること / 修飾の型（その位置に来られるか）/ 分類の軸と値 / 概念の式の一意性 /
        役割が根拠となる定義を持つこと
  records: 体系が、自分の記録（claims.yaml, measurements.yaml）について述べる部分。項目名はノードの識別子。
  grammar: 体系が、自分の書き方について述べる部分。文法の語は、すべてノードの識別子。節ごとに、使える語を並べる。
        検査は、ここに書かれた語だけを文法の語として受け付ける。logic は述語論理の語で、体系の中では定義しない。

measurements.yaml と claims.yaml  記録。
  項目名は、ontology.yaml のノードの識別子そのもの。どの記録がどの項目を持てるかは、ontology.yaml の records にある。
  status や留保や指標の値も、ノードの識別子。
  測定値: 族ごとに、軸（axis）の直積で展開する。識別子は「族.軸の値....指標」。値は結果ファイルから計算する。
  観察・仮説・決定: どれも「s が、p という関係で、o に」という文。
    観察の s と o は測定値（o は数でもよい）、p は大きさを比べる動詞。真偽は、動詞の式（後ろにある、の成立と不成立）を
    数に当てはめて決める。すべて真でなければ検査は失敗する。
    仮説と決定の s と o はノード、p は動詞。s は p の始点、o は p の終点に来られるものでなければならない。
    仮説の status は、根拠（evidence, against）の有無から決まる。決まり方は、状態のノードの式から読み取る。
    決定の p が is_a のときは、体系の上位・下位の関係そのもの。採用済みなら、検査が構造から確かめる。

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
errors = []


def err(msg):
    errors.append(msg)


def load(name):
    return yaml.safe_load((SPEC / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 概念の体系
# 法則のうち、この検査が当てはめるもの / 実行の検査（run_spec.py）が当てはめるもの
LAWS_HERE = {"truth_distinct", "inherit", "narrow", "acyclic", "monotone", "specific", "unique_in_domain", "layered"}
LAWS_RUN = {"transitive", "antisymmetric", "asymmetric", "end_exists", "step", "frame", "halt"}


class Ontology:
    def __init__(self, O):
        self.O = O
        self.B, self.AX, self.N, self.R, self.G = O["base"], O["axes"], O["nodes"], O["records"], O["grammar"]
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
            for k in l:
                if k not in G["laws"]:
                    err(f"laws.{lid}: 語 {k} が、grammar.laws に書かれていない")
            if self.resolve(l.get("scope"), l.get("scope")) is None or l.get("scope") not in G["grammar"]:
                err(f"laws.{lid}: 掛かる節 {l.get('scope')} が、ノードでないか、grammar.grammar に書かれていない")
            if lid not in LAWS_HERE | LAWS_RUN:
                err(f"laws.{lid}: 当てはめる検査がない")
        for lid in (LAWS_HERE | LAWS_RUN) - set(L):
            err(f"法則 {lid} を検査が当てはめているが、laws に書かれていない")
        for bid, b in self.B.items():
            for lid in b.get("laws", []):
                if lid not in L:
                    err(f"base.{bid}: 法則 {lid} が laws に書かれていない")
        # 法則 truth_distinct
        tv = self.AX["truth"]["value"]
        if not (isinstance(tv, list) and len(tv) == 2 and tv[0] != tv[1]):
            err("axes.truth: 値は2つで、互いに違うこと")
        # 法則 acyclic
        for nid in self.N:
            x, seen = nid, set()
            while x in self.N:
                if x in seen:
                    err(f"{nid}: 上位をたどると自分に戻る")
                    break
                seen.add(x)
                x = self.up(x)
        for k, v in self.O["runtime"].items():
            if k not in G["runtime"]:
                err(f"runtime: 語 {k} が、grammar.runtime に書かれていない")
            elif self.resolve(v, "run") is None or not self.is_a(self.resolve(v, "run"), self.resolve(k, "run")) and not (k == "pre_rule" and v in G["logic"]):
                err(f"runtime.{k}: 値 {v} が、{k} の下位のノードでない")
        for k, v in self.O["syntax"].items():
            if k not in G["syntax"]:
                err(f"syntax: 語 {k} が、grammar.syntax に書かれていない")
            try:
                names = set(re.compile(v["pattern"]).groupindex)
            except re.error as e:
                err(f"syntax.{k}: 書き方が読めない（{e}）")
                continue
            if names != set(v["value"]) or any(x not in self.N for x in v["value"]):
                err(f"syntax.{k}: 部分の名前 {sorted(names)} が、value と合わないか、ノードでない")
        for k in self.O:
            if k not in G["system"]:
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
        for rid, r in self.R.items():
            for k in r:
                if k not in G["records"]:
                    err(f"records.{rid}: 語 {k} が、grammar.records に書かれていない")

    def resolve(self, word, dom):
        """領域を書かない語を、ノードの識別子に解決する。その領域、core、ほかの領域にただ1つ、の順に探す。"""
        if f"{dom}.{word}" in self.N:
            return f"{dom}.{word}"
        if word in self.N:
            return word
        found = [i for i in self.N if i.split(".", 1)[-1] == word]
        return found[0] if len(found) == 1 else None

    def domain(self, nid):
        return nid.split(".", 1)[0] if "." in nid else "core"

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
            for k in d:
                if k not in self.G["domains"]:
                    err(f"domains.{did}: 語 {k} が、grammar.domains に書かれていない")
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
            ok = {dom} | set(D[dom].get("uses", []))
            for r in self.refs(nid):  # 法則 layered
                if self.domain(r) not in ok:
                    err(f"{nid}: 領域 {dom} から、使うと書かれていない領域のノード {r} を参照している")

    def parents(self, nid):
        """上位。extends に並べたものは AND（そのすべてに当てはまる）。"""
        e = self.N[nid].get("extends")
        return [] if e is None else (e if isinstance(e, list) else [e])

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

    def check_hierarchy(self):
        """法則 monotone: 階層を降りるたびに、限定が増える。
        法則 specific: 自分の限定の一部だけで書ける概念が別にあれば、その下に置く（具体的な概念を、抽象的な位置に置かない）。"""
        C = [i for i in self.N if self.is_concept(i)]
        A = {i: self.acc(i) for i in C}
        anc = {i: set(self.ancestors(i)) for i in C}
        for x in C:
            ps = self.parents(x)
            for p in ps:
                if p in A and not A[p] < A[x]:
                    err(f"{x}: 上位の {p} より限定が増えていない（法則 monotone）")
            for i, p in enumerate(ps):
                for q in ps[i + 1:]:
                    if p in anc.get(q, ()) or q in anc.get(p, ()) or p == q:
                        err(f"{x}: 上位に並べた {p} と {q} が、上下の関係にある")
            for y in C:
                if y == x or y in anc[x] or x in anc[y] or not self.own(y):
                    continue
                if anc[y] & set(ps) and A[y] <= A[x]:
                    same = "（限定が同じ。同じ概念）" if A[y] == A[x] else ""
                    err(f"{x}: より具体的な {y} があるのに、その下に置かれていない（法則 specific）{same}")

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

    def is_a(self, x, y, hops=0):
        if y == "any":
            return True
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
                return {re.search(r"(\w+)\(", f).group(1) for f in fs}
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
                m = re.fullmatch(self.O["syntax"]["formula"]["pattern"], f)
                args = [a for a in (m.group("from"), m.group("to")) if a] if m else []
                if not m or m.group("base") not in self.B or len(args) != self.B[m.group("base")]["arity"] or any(a not in ("from", "to", "new") for a in args):
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
            if a["source"] != "any" and a["source"] not in B:
                err(f"axes: {aid} のもとになる関係 {a['from']} が未定義")
        seen, forms = {}, {}
        for nid, n in N.items():
            ja = n.get("ja")
            key = (self.domain(nid), ja)  # 法則 unique_in_domain
            if not ja or key in seen:
                err(f"{nid}: 表示語がない、または {seen.get(key)} と重複（同音異義）")
            seen[key] = nid
            if nid in TOPS:
                if set(n) != {"ja", "gloss"}:
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
                    for side in ("from", "to"):
                        if side in n and not self.is_a(n[side], self.end(self.up(nid), side)):
                            err(f"{nid}: {side} の {n[side]} は、上位の {self.end(self.up(nid), side)} を狭めていない")
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
                    elif m["with"] not in N or not self.overlaps(m["with"], self.end(verb, other)):
                        err(f"{where}: {m['with']} は {verb} の {other}（{self.end(verb, other)}）に来られない")
                if set(m) - set(self.G["mod"]):
                    err(f"{where}: 語 {set(m) - set(self.G['mod'])} が、grammar.mod に書かれていない")
                if m.get("quant") is not None and m["quant"] not in self.G["logic"]:
                    err(f"{where}: 数量化 {m['quant']} が、grammar.logic に書かれていない。数は at で書く")
                for axis, v in (m.get("at") or {}).items():
                    self.check_value(axis, v, where)
                    if axis in AX and AX[axis]["source"] != "any" and AX[axis]["source"] not in self.base_of(verb):
                        err(f"{where}: 軸 {axis} は基礎の関係 {AX[axis]['from']} を抽象にしたものだが、{verb} はそれを使っていない")
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
                s = tuple(tuple(sorted(n.get(k, []))) for k in ("holds", "pre", "post")) + (n["from"], n["to"], n.get("new_kind"))
                sig[s].append(nid)
        for ids in sig.values():
            if len(ids) > 1:
                err(f"動詞の式が同じ: {ids}")

    def check_records(self):
        """記録の項目名が、体系のノードであること。"""
        for rid, r in self.R.items():
            if set(r) - {"is", "key", "fields"}:
                err(f"records.{rid}: 知らない項目 {set(r) - {'is', 'key', 'fields'}}")
            for k in ("is", "key"):
                if k in r and r[k] not in self.N:
                    err(f"records.{rid}: {k} の {r[k]} が未定義")
            for f in r["fields"]:
                if f not in self.N:
                    err(f"records.{rid}: 項目 {f} は、ノードとして定義されていない")

    def fields(self, rid):
        return self.R[rid]["fields"]

    def kinds_of(self, nid):
        """nid の直接の下位にあるノード。status や留保の値として使えるもの。"""
        return [k for k, n in self.N.items() if nid in self.parents(k)]

    def status_pattern(self, nid):
        """状態のノードの式から、「支持する観察がある / 反する観察がある」の組を読み取る。"""
        pat = {}
        for m in self.N[nid].get("mod") or []:
            if isinstance(m, dict) and m.get("of") == ["v_agree", "to"] and m.get("with") in ("evidence", "against"):
                pat[m["with"]] = not m.get("neg")
        return pat if set(pat) == {"evidence", "against"} else None

    def compare(self, verb, a, b, tol):
        """大きさを比べる動詞の式（後ろにある、の成立と不成立）を、2つの数に当てはめる。"""
        hops = 0
        while verb in self.N and "holds" not in self.N[verb] and hops < 50:
            verb, hops = self.up(verb), hops + 1
        n = self.N.get(verb, {})
        if not n.get("holds") or any(not re.fullmatch(r"(not )?after\((from|to), (from|to)\)", f) for f in n["holds"]):
            return None
        x = {"from": a, "to": b}
        out = True
        for f in n["holds"]:
            m = re.fullmatch(r"(not )?after\((\w+), (\w+)\)", f)
            later = x[m.group(2)] - x[m.group(3)] > tol
            out = out and (not later if m.group(1) else later)
        return out

    def is_strict(self, verb):
        hops = 0
        while verb in self.N and "holds" not in self.N[verb] and hops < 50:
            verb, hops = self.up(verb), hops + 1
        return any(f.startswith("after(") for f in self.N.get(verb, {}).get("holds", []))

    def expr(self, nid):
        """上位をたどって、式を並べる。"""
        out, hops = [], 0
        while nid in self.N and hops < 80:
            n = self.N[nid]
            body = {k: n[k] for k in ("from", "to", "new_kind", "holds", "pre", "post", "form", "of", "neg", "mod", "val", "cmp", "axis", "gloss") if k in n}
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
        if val not in T.N:
            err(f"{where}: ノード {val} が未定義")
        return
    for k in val:
        if k not in T.fields("meaning"):
            err(f"{where}: 項目 {k} は、体系の records.meaning に書かれていない")
    for nid in val.get("identifier", []):
        if nid not in T.N:
            err(f"{where}: ノード {nid} が未定義")
    for v in val.get("value", []):
        for k in v:
            if k not in T.fields("value"):
                err(f"{where}: 値の項目 {k} は、体系の records.value に書かれていない")
        if v.get("s") not in T.N:
            err(f"{where}: 値の s {v.get('s')} が未定義")
        T.check_value(v.get("axis"), v.get("o"), where)


def expand(M, T):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        for k in f:
            if k not in T.fields("measurements"):
                err(f"measurements.{fid}: 項目 {k} は、体系の records.measurements に書かれていない")
        for st in f["metric"]:
            if st not in T.N or not (T.is_a(st, "metric") or T.is_a(st, "magnitude")):
                err(f"measurements.{fid}: 指標 {st} は、体系の指標でも大きさでもない")
        for k in f.get("row_keys", {}):
            if k not in T.fields("row_keys"):
                err(f"measurements.{fid}: row_keys の項目 {k} は、体系の records.row_keys に書かれていない")
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
                mid = ".".join([fid] + [str(b[a]) for a in names] + [st])
                try:
                    values[mid] = stat(rows, fmt(f["condition_entry"]), st)
                except KeyError as e:
                    err(f"measurements: {mid}: {e}")
                meanings[mid] = {a: (f.get("meaning") or {}).get(a, {}).get(b[a], b[a]) for a in names} | {"metric": st}
    return values, meanings


# ---------------------------------------------------------------- 観察・仮説・決定
def check_claims(C, values, T):
    for sect in ("observations", "hypotheses", "decisions"):
        for cid, c in C[sect].items():
            for k in c:
                if k not in T.fields(sect):
                    err(f"{cid}: 項目 {k} は、体系の records.{sect} に書かれていない")
    for b in C["backlog"]:
        for k in b:
            if k not in T.fields("backlog"):
                err(f"backlog {b.get('identifier')}: 項目 {k} は、体系の records.backlog に書かれていない")

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
        near = T.end(o["p"], "new_kind") == "tolerance"
        if near != ("tolerance" in o):
            err(f"{oid}: 許容幅は、動詞 {o['p']} の第三のものが許容幅であるときにだけ、必ず書く")
            continue
        holds = T.compare(o["p"], vals[0], vals[1], o["tolerance"] + 1e-9 if near else 1e-6)
        if holds is None:
            err(f"{oid}: 動詞 {o['p']} は、大きさを比べる動詞（「後ろにある」だけで書かれた静的な動詞）でない")
        elif not holds:
            err(f"observations: {oid} が成り立たない（{T.N[o['p']]['ja']}: s={vals[0]:.3f}, o={vals[1]:.3f}）")
        ns = [values[x][1] for x in (o["s"], o["o"]) if isinstance(x, str) and x in values]
        gap[oid] = abs(vals[0] - vals[1]) * min(ns) if T.is_strict(o["p"]) else None

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
            elif x.get("status") == "dec_adopted" and not all(T.is_a(a, b) for a in ss for b in oo):
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
        if h["status"] not in patterns:
            err(f"{hid}: status の {h['status']} は、仮説の状態のノードでない")
        elif want != [h["status"]]:
            err(f"{hid}: status は {h['status']} と書かれているが、根拠の有無からは {want} になる")
        for t in h.get("scope", []):
            if t not in T.N:
                err(f"{hid}: scope のノード {t} が未定義")
        for k in ("evidence", "against"):
            for r in h.get(k, []):
                if r not in obs:
                    err(f"{hid}: {k} の観察 {r} が未定義")
        for lim in h.get("limitation", []):
            if lim not in T.kinds_of("limitation"):
                err(f"{hid}: 留保 {lim} は、留保のノードでない")
        if "lim_one_item" in h.get("limitation", []):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--values", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--expr")
    args = ap.parse_args()
    T = Ontology(load("ontology.yaml"))
    T.check()
    T.check_records()
    T.check_grammar()
    T.check_hierarchy()
    T.check_domains()
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
