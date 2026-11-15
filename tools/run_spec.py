"""実行の記録（spec/runs/*.yaml）を、体系の書き換え規則に照らして検査する。

実行器は役割で、担い手は何でもよい（LLM、プログラム、機械）。この検査は、担い手が書いた実行の記録が
体系に適合しているかを確かめる。当てはめる法則は、ontology.yaml の laws のうち次のもの:
  transitive / antisymmetric / asymmetric / end_exists  状態が、基礎の関係の法則を満たす
  step   動詞の pre がすべて成り立つときだけ適用でき、post に置き換わる
  frame  post に書かれていない文は変わらない
  halt   halted: true と書かれた記録では、当てはまる動詞がもうない

記録の書き方:
  individuals: {個体: {is: 種類}}
  facts: ["関係(個体, 個体)", ...]         最初の状態。書かれていない文は成り立っていない
  steps: [[動詞, {from: 個体, to: 個体, new: 個体}], ...]
  expect: ["関係(...)", "not 関係(...)"]   最後の状態で成り立つこと
  halted: true | false
"""
import itertools
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from check_spec import Ontology, load, merge_domain  # noqa: E402

ROOT = Path(__file__).parent.parent / "spec"


FORMULA = None  # 式の書き方。体系の syntax.formula から読む


def fact(d, T):
    """事実（基礎の関係の個体）を、(否定, 関係, 端の並び) に直す。位置は名前で書く。"""
    if not isinstance(d, dict) or set(d) - set(T.G["facts"]) or d.get("is") not in T.B:
        raise ValueError(f"事実 {d} は {{is: 基礎の関係, from: 始点, to: 終点, neg: 否定}} で書く")
    return bool(d.get("neg")), d["is"], tuple(d[p] for p in ("from", "to") if p in d)


def show(d):
    return f"{'not ' if d.get('neg') else ''}{d.get('is')}({', '.join(str(d[p]) for p in ('from', 'to') if p in d)})"


def parse(f):
    m = re.fullmatch(FORMULA, f)
    if not m:
        raise ValueError(f"式 {f} が読めない")
    return bool(m.group("not")), m.group("base"), tuple(a for a in (m.group("from"), m.group("to")) if a)


# 実行時の意味論のうち、この検査が実装している選択。体系の runtime に、ここにない選択が書かれていればエラー。
IMPLEMENTED = {
    "world": {"closed_world"},
    "pre_rule": {"all", "any"},
    "post_rule": {"replace"},
    "law_check": {"every_step"},
    "binding": {"distinct"},
    "choice": {"recorded"},
    "progress": {"changes_state"},
}


class Machine:
    def __init__(self, T, run, name):
        self.T, self.name, self.errors, self.R = T, name, [], T.O["runtime"]
        self.quant = all if self.R["pre_rule"] == "all" else any
        self.ind = {i: v["is"] for i, v in run["individuals"].items()}
        for i, k in self.ind.items():
            if k not in T.N:
                self.err(f"個体 {i} の種類 {k} が未定義")
        self.facts = set()
        for f in run.get("facts", []):
            neg, rel, args = fact(f, T)
            f = show(f)
            if neg:
                self.err(f"最初の状態に否定 {f} は書かない（書かれていない文は成り立っていない）")
            self.fact_ok(rel, args, f)
            self.facts.add((rel, args))

    def err(self, m):
        self.errors.append(f"{self.name}: {m}")

    def fact_ok(self, rel, args, f):
        if rel not in self.T.B or len(args) != self.T.B[rel]["arity"] or any(a not in self.ind for a in args):
            self.err(f"式 {f} が、基礎の関係か個体に合わない")

    def holds(self, neg, rel, args):
        return ((rel, args) in self.facts) != neg

    def check_laws(self, where):
        for rel, b in self.T.B.items():
            pairs = {a for r, a in self.facts if r == rel}
            laws = b.get("laws", [])
            if "transitive" in laws:  # 推移的に閉じてから見る
                changed = True
                while changed:
                    new = {(a, d) for a, b2 in pairs for c, d in pairs if b2 == c} - pairs
                    pairs |= new
                    changed = bool(new)
            if "asymmetric" in laws:
                for a, b2 in pairs:
                    if (b2, a) in pairs:
                        self.err(f"{where}: {rel}({a}, {b2}) が法則 asymmetric に反する")
            if "antisymmetric" in laws:
                for a, b2 in pairs:
                    if a != b2 and (b2, a) in pairs:
                        self.err(f"{where}: {rel}({a}, {b2}) が法則 antisymmetric に反する")
            if "end_exists" in laws:
                for a, b2 in pairs:
                    if ("exists", (a,)) in self.facts and ("exists", (b2,)) not in self.facts:
                        self.err(f"{where}: {rel}({a}, {b2}) が法則 end_exists に反する（{b2} が在らない）")

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
                neg, rel, args = parse(f)
                if any(a not in b for a in args):
                    return None, f"式 {f} の位置に個体が束縛されていない"
                out[key].append((neg, rel, tuple(b[a] for a in args)))
        return out, None

    def step(self, verb, b, where):
        r, why = self.bind(verb, b)
        if r is None:
            return self.err(f"{where}: {why}")
        if len(set(b.values())) != len(b):  # runtime.binding: distinct
            return self.err(f"{where}: 別々の位置に同じ個体が割り当てられている")
        if not self.quant(self.holds(*f) for f in r["pre"]):  # 法則 step。runtime.pre_rule
            bad = [f"{'not ' if neg else ''}{rel}{args}" for neg, rel, args in r["pre"] if not self.holds(neg, rel, args)]
            return self.err(f"{where}: pre の {bad} が成り立っていない")
        for neg, rel, args in r["post"]:  # 法則 frame: ここに出てこない文には触れない
            (self.facts.discard if neg else self.facts.add)((rel, args))
        self.check_laws(where)

    def applicable(self):
        """当てはまって、状態を変える動詞と束縛を列挙する。"""
        T, found = self.T, []
        for vid, n in T.N.items():
            if "pre" not in n:
                continue
            poss = ["from", "to"] + (["new"] if any("new" in f for f in n["pre"] + n["post"]) else [])
            for combo in itertools.permutations(self.ind, len(poss)):
                b = dict(zip(poss, combo))
                r, _ = self.bind(vid, b)
                if r and self.quant(self.holds(*x) for x in r["pre"]) and not all(self.holds(*x) for x in r["post"]):
                    found.append((vid, b))
        return found


def main():
    global FORMULA
    O = load("ontology.yaml")
    merge_domain("exp.yaml", O)   # 実行の記録は、領域 exp の種類と動詞を「exp.名前」で使える
    T = Ontology(O)
    G = T.G["run"]
    FORMULA = T.O["syntax"]["formula"]["pattern"]
    for k, v in T.O["runtime"].items():
        if v not in IMPLEMENTED.get(k, ()):
            print(f"実行の検査に失敗: runtime.{k} の選択 {v} は、この検査に実装がない")
            sys.exit(1)
    errors, n_steps, files = [], 0, sorted((ROOT / "runs").glob("*.yaml"))
    for path in files:
        run = yaml.safe_load(path.read_text(encoding="utf-8"))
        for k in run:
            if k not in G:
                errors.append(f"{path.name}: 語 {k} が、grammar.run に書かれていない")
        m = Machine(T, run, path.name)
        m.check_laws("最初の状態")
        for i, st in enumerate(run.get("steps", [])):
            if not isinstance(st, dict) or set(st) - set(T.G["facts"]) or "is" not in st:
                m.err(f"steps[{i}]: 歩みは {{is: 動的な動詞, from, to, new}} で書く")
                continue
            verb, b = st["is"], {k: v for k, v in st.items() if k != "is"}
            m.step(verb, b, f"steps[{i}] {verb}")
            n_steps += 1
        for f in run.get("expect", []):
            if not m.holds(*fact(f, T)):
                m.err(f"expect の {show(f)} が、最後の状態で成り立っていない")
        if "halted" in run:  # 法則 halt
            rest = m.applicable()
            if run["halted"] != (not rest):
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
