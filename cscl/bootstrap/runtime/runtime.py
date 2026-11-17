"""実行の記録（exp/tests/*.yaml）を、体系の書き換え規則に照らして検査する。

実行器は役割で、担い手は何でもよい（LLM、プログラム、機械）。この検査は、担い手が書いた実行の記録が
体系に適合しているかを確かめる。当てはめる法則は、syntax と runtime の法則の個体のうち次のもの:
  規則で書いた法則（law_rule）  前提・導く文・求める文を読んで、状態に当てはめる
  unique_names  名前の違う個体は同じでない（same の読み方）
  step   動詞の pre がすべて成り立つときだけ適用でき、post に置き換わる
  frame  post に書かれていない文は変わらない
  halt   halted: true と書かれた記録では、当てはまる動詞がもうない

状態は「述べた文」の記録で、文ごとに、真と述べたか偽と述べたかを持つ。文の読み方は3つ:
  {is: 関係, ...}                       真である。真と述べてあれば真、偽と述べてあれば偽
  {is: 関係, ..., val: {truth: false}}  偽である。偽と述べてあれば真、真と述べてあれば偽
  {is: 関係, ..., neg: true}            述べられていない（syntax の not）。記録だけで決まるので、どの世界でも決められる
述べていない文の真偽は、領域が前提に置く世界が与える。閉世界（closed_world）は偽を与える。
世界（world）だけを置けば、真偽を与えない（開世界）。そのとき、述べていない文の真偽は決められない。
post は、真・偽の文なら、その真偽を述べる。neg の文なら、述べたことを取り消す。

記録の書き方:
  individuals: {個体: {is: 種類}}
  facts: [{is: 関係, from: 個体, to: 個体}, ...]   最初の状態。偽と述べる文は val: {truth: false} を付ける
  steps: [{is: 動詞, from: 個体, to: 個体, new: 個体}, ...]
  expect: [文, ...]                      最後の状態で成り立つこと（読み方は上の3つ）
  halted: true | false
"""
import itertools
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "type_checker"))
from type_checker import Facts, Ontology, atom, truth_of, evaluate, law_rules, in_scope, load, root_name, merge_domain, register_domains, variables, presumed_worlds  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]




UNSTATED = "unstated"   # 文の読み方: True（真である）、False（偽である）、UNSTATED（述べられていない）


def reading(f):
    """状態の文の読み方。neg は「述べられていない」、それ以外は述べる真偽（truth_of）。"""
    if f.get("neg"):
        return None if "val" in f else UNSTATED
    return truth_of(f)


def fact(d, T):
    """事実（基礎の関係の個体）を、(読み方, 関係, 端の並び) に直す。位置は名前で書く。"""
    if not isinstance(d, dict) or set(d) - set(T.G["facts"]) or d.get("is") not in T.B or reading(d) is None:
        raise ValueError(f"事実 {d} は {{is: 基礎の関係, from: 始点, to: 終点}} に、neg: true か val: {{truth: 真偽}} を付けて書く")
    return reading(d), d["is"], tuple(d[p] for p in ("from", "to") if p in d)


def show(d):
    pre = "not " if d.get("neg") else "false " if truth_of(d) is False else ""
    return f"{pre}{d.get('is')}({', '.join(str(d[p]) for p in ('from', 'to') if p in d)})"


def show_atom(r, rel, args):
    return f"{'not ' if r == UNSTATED else 'false ' if r is False else ''}{rel}{args}"


# 実行時の意味論のうち、この検査が実装している選択。体系の runtime に、ここにない選択が書かれていればエラー。
# 書かれていない文の扱いは、ここでなく、領域 runtime が置く前提（{is: v_presume, from: runtime, to: 扱い}）から読む。
WORLDS = {"closed_world": False, "world": None}   # 世界 → 述べていない文に与える真偽（None は与えない）
IMPLEMENTED = {
    "pre_rule": {"all", "any"},
    "post_rule": {"replace"},
    "law_check": {"every_step"},
    "binding": {"distinct"},
    "choice": {"recorded"},
    "progress": {"changes_state"},
}


class Machine:
    def __init__(self, T, run, name, world):
        self.T, self.name, self.errors, self.R, self.world = T, name, [], T.O["runtime"], world
        self.quant = all if self.R["pre_rule"] == "all" else any
        self.ind = {i: T.resolve(v["is"], "exp") or v["is"] for i, v in run["individuals"].items()}
        for i, k in self.ind.items():
            if k not in T.N:
                self.err(f"個体 {i} の種類 {k} が未定義")
        self.facts = {}   # 述べた文 → 述べた真偽
        for f in run.get("facts", []):
            r, rel, args = fact(f, T)
            f = show(f)
            if r == UNSTATED:
                self.err(f"最初の状態に {f} は書かない（neg は「述べられていない」。最初の状態には述べる文だけを書く）")
            self.fact_ok(rel, args, f)
            self.facts[(rel, args)] = r

    def err(self, m):
        self.errors.append(f"{self.name}: {m}")

    def fact_ok(self, rel, args, f):
        if rel not in self.T.B or len(args) != self.T.B[rel]["arity"] or any(a not in self.ind for a in args):
            self.err(f"式 {f} が、基礎の関係か個体に合わない")

    def holds(self, r, rel, args):
        """文が成り立つか。r は読み方（True / False / UNSTATED）。決められなければ None。
        述べられていないか（UNSTATED）は、記録だけで決まる。真偽は、述べてあればそれ、なければ世界が与える値。"""
        key = (rel, args)
        if r == UNSTATED:
            return key not in self.facts
        value = self.facts.get(key, WORLDS[self.world])
        return None if value is None else value == r

    def stated_true(self):
        """真と述べた文の集まり（法則を当てはめる相手）。"""
        return {k for k, v in self.facts.items() if v is True}

    def check_laws(self, where):
        """規則で書いた法則（層のファイルの law_rule）のうち、基礎の関係だけで書かれたものを、状態に当てはめる。
        導く文を足して閉じてから、求める文を確かめる。same は名前が同じであること（法則 unique_names）。"""
        T = self.T
        rules = [(lid, l) for lid, l in law_rules(T.O)
                 if all(atom(f)[1] in T.B for p in ("assume", "derive", "require") for f in l[p])
                 and (self.world == "closed_world" or not any(atom(f)[0] for f in l["assume"]))]   # 否定の前提は閉世界でだけ
        for lid, b, f in evaluate(rules, Facts(self.stated_true()), variables(T.O)):
            self.err(f"{where}: {dict(sorted(b.items()))} が法則 {lid}（{T.O['laws'][lid]['display']}）に反する")

    def bind(self, verb, b):
        """束縛が、動詞の端の種類に合うか。合えば、before と after の式を個体で書いたものを返す。"""
        T, n = self.T, None
        x = verb
        while x in T.N and not ("pre" in T.N[x] or "holds" in T.N[x]):
            x = T.up(x)
        n = T.N.get(x)
        if n is None or "pre" not in n:
            return None, f"{verb} は動的な動詞でない"
        for pos in ("from", "to"):
            if pos not in b or b[pos] not in self.ind:
                return None, f"{pos} の個体がない"
            if not T.is_a(self.ind[b[pos]], T.end(verb, pos)):
                return None, f"{pos} の {b[pos]}（{self.ind[b[pos]]}）は {T.end(verb, pos)} でない"
        if "new" in b:
            kind = n.get("new_kind", "any")
            if b["new"] not in self.ind or not T.is_a(self.ind[b["new"]], kind):
                return None, f"new の {b.get('new')} は {kind} でない"
        out = {}
        for key in ("pre", "post"):
            out[key] = []
            for f in n.get(key, []):
                _, rel, args = atom(f)
                if any(a not in b for a in args):
                    return None, f"式 {f} の位置に個体が束縛されていない"
                out[key].append((reading(f), rel, tuple(b[a] for a in args)))
        return out, None

    def step(self, verb, b, where):
        r, why = self.bind(verb, b)
        if r is None:
            return self.err(f"{where}: {why}")
        if len(set(b.values())) != len(b):  # runtime.binding: distinct
            return self.err(f"{where}: 別々の位置に同じ個体が割り当てられている")
        unknown = [show_atom(*f) for f in r["pre"] if self.holds(*f) is None]
        if unknown:   # 述べていない文の真偽を、世界が与えない
            return self.err(f"{where}: pre の {unknown} は、述べられていない文の真偽で、この世界では決められない")
        if not self.quant(self.holds(*f) for f in r["pre"]):  # 法則 step。runtime.pre_rule
            bad = [show_atom(*f) for f in r["pre"] if not self.holds(*f)]
            return self.err(f"{where}: pre の {bad} が成り立っていない")
        for v, rel, args in r["post"]:  # 法則 frame: ここに出てこない文には触れない
            if v == UNSTATED:
                self.facts.pop((rel, args), None)   # 述べたことを取り消す
            else:
                self.facts[(rel, args)] = v          # 真か偽かを述べる
        self.check_laws(where)

    def applicable(self):
        """当てはまって、状態を変える動詞と束縛を列挙する。"""
        T, found = self.T, []
        for vid, n in T.N.items():
            if "pre" not in n:
                continue
            poss = ["from", "to"] + (["new"] if any("new" in atom(f)[2] for f in n["pre"] + n["post"]) else [])
            for combo in itertools.permutations(self.ind, len(poss)):
                b = dict(zip(poss, combo))
                r, _ = self.bind(vid, b)
                if r and self.quant(self.holds(*x) is True for x in r["pre"]) and not all(self.holds(*x) is True for x in r["post"]):
                    found.append((vid, b))
        return found


def main():
    O = load(root_name())
    for _, name in register_domains(O):   # 実行の記録は、領域の種類と動詞を「領域.名前」で使える
        merge_domain(name, O)
    T = Ontology(O)
    G = T.G["run"]
    for k, v in T.O["runtime"].items():
        if v not in IMPLEMENTED.get(k, ()):
            print(f"実行の検査に失敗: runtime.{k} の選択 {v} は、この検査に実装がない")
            sys.exit(1)
    world = presumed_worlds().get("runtime", set())
    if len(world) != 1 or not world <= set(WORLDS):
        print(f"実行の検査に失敗: 領域 runtime が置く、書かれていない文の扱い {sorted(world)} は、1つでないか、この検査に実装がない")
        sys.exit(1)
    world = next(iter(world))
    errors, n_steps, files = [], 0, in_scope("runs")
    for path in files:
        run = yaml.safe_load(path.read_text(encoding="utf-8"))
        for k in run:
            if k not in G:
                errors.append(f"{path.name}: 語 {k} が、grammar.run に書かれていない")
        m = Machine(T, run, path.name, world)
        m.check_laws("最初の状態")
        for i, st in enumerate(run.get("steps", [])):
            if not isinstance(st, dict) or set(st) - set(T.G["facts"]) or "is" not in st:
                m.err(f"steps[{i}]: 歩みは {{is: 動的な動詞, from, to, new}} で書く")
                continue
            verb, b = st["is"], {k: v for k, v in st.items() if k != "is"}
            m.step(verb, b, f"steps[{i}] {verb}")
            n_steps += 1
        for f in run.get("expect", []):
            h = m.holds(*fact(f, T))
            if h is None:
                m.err(f"expect の {show(f)} は、述べられていない文の真偽で、この世界では決められない")
            elif not h:
                m.err(f"expect の {show(f)} が、最後の状態で成り立っていない")
        if "halted" in run:  # 法則 halt
            rest = m.applicable()
            if WORLDS[m.world] is None:
                m.err("halted は、世界が述べていない文に真偽を与えないので決められない（当てはまらないとは言えない）")
            elif run["halted"] != (not rest):
                m.err(f"halted: {run['halted']} と書かれているが、当てはまる動詞は {len(rest)} 個（例: {rest[:1]}）")
        errors += m.errors
    if errors:
        print(f"実行の検査に失敗: {len(errors)} 件")
        for e in errors[:40]:
            print(" -", e)
        sys.exit(1)
    print(f"実行の検査に成功: 実行の記録 {len(files)}、歩数 {n_steps}")


if __name__ == "__main__":
    main()
