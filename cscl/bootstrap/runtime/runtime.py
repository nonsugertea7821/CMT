"""実行の記録（exp/tests/*.yaml）を、体系の書き換え規則に照らして検査する。

実行器は役割で、担い手は何でもよい（LLM、プログラム、機械）。この検査は、担い手が書いた実行の記録が
体系に適合しているかを確かめる。当てはめる法則は、syntax と runtime の法則の個体のうち次のもの:
  規則で書いた法則（law_rule）  前提・導く文・求める文を読んで、状態に当てはめる
  unique_names  名前の違う個体は同じでない（same の読み方）
  step   動詞の pre がすべて成り立つときだけ適用でき、post に置き換わる
  frame  post に書かれていない文は変わらない
  halt   halted: true と書かれた記録では、当てはまる動詞がもうない

記録の書き方:
  individuals: {個体: {is: 種類}}
  facts: ["関係(個体, 個体)", ...]         最初の状態。書かれていない文は示されていない（領域 runtime が閉世界を置くので偽）
  steps: [[動詞, {from: 個体, to: 個体, new: 個体}], ...]
  expect: ["関係(...)", "not 関係(...)"]   最後の状態で成り立つこと
  halted: true | false
"""
import itertools
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "type_checker"))
from type_checker import Facts, Ontology, atom, evaluate, law_rules, in_scope, load, root_name, merge_domain, register_domains, variables, presumed_worlds  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]




def fact(d, T):
    """事実（基礎の関係の個体）を、(否定, 関係, 端の並び) に直す。位置は名前で書く。"""
    if not isinstance(d, dict) or set(d) - set(T.G["facts"]) or d.get("is") not in T.B:
        raise ValueError(f"事実 {d} は {{is: 基礎の関係, from: 始点, to: 終点, neg: 否定}} で書く")
    return bool(d.get("neg")), d["is"], tuple(d[p] for p in ("from", "to") if p in d)


def show(d):
    return f"{'not ' if d.get('neg') else ''}{d.get('is')}({', '.join(str(d[p]) for p in ('from', 'to') if p in d)})"


# 実行時の意味論のうち、この検査が実装している選択。体系の runtime に、ここにない選択が書かれていればエラー。
# 書かれていない文の扱いは、ここでなく、領域 runtime が置く前提（{is: v_presume, from: runtime, to: 扱い}）から読む。
WORLDS = {"closed_world", "open_world"}
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
        self.facts = set()
        for f in run.get("facts", []):
            neg, rel, args = fact(f, T)
            f = show(f)
            if neg:
                self.err(f"最初の状態に否定 {f} は書かない（否定は「示されていない」。最初の状態には示す文だけを書く）")
            self.fact_ok(rel, args, f)
            self.facts.add((rel, args))

    def err(self, m):
        self.errors.append(f"{self.name}: {m}")

    def fact_ok(self, rel, args, f):
        if rel not in self.T.B or len(args) != self.T.B[rel]["arity"] or any(a not in self.ind for a in args):
            self.err(f"式 {f} が、基礎の関係か個体に合わない")

    def holds(self, neg, rel, args):
        """文が成り立つか。否定は「示されていない」。閉世界なら示されていない文は偽、開世界なら不明（None）。"""
        if (rel, args) in self.facts:
            return not neg
        return neg if self.world == "closed_world" else None

    def check_laws(self, where):
        """規則で書いた法則（層のファイルの law_rule）のうち、基礎の関係だけで書かれたものを、状態に当てはめる。
        導く文を足して閉じてから、求める文を確かめる。same は名前が同じであること（法則 unique_names）。"""
        T = self.T
        rules = [(lid, l) for lid, l in law_rules(T.O)
                 if all(atom(f)[1] in T.B for p in ("assume", "derive", "require") for f in l[p])
                 and (self.world == "closed_world" or not any(atom(f)[0] for f in l["assume"]))]   # 否定の前提は閉世界でだけ
        for lid, b, f in evaluate(rules, Facts(self.facts), variables(T.O)):
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
                neg, rel, args = atom(f)
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
        unknown = [f"not {rel}{args}" for neg, rel, args in r["pre"] if self.holds(neg, rel, args) is None]
        if unknown:   # 開世界では、示されていないことから偽とは言えない
            return self.err(f"{where}: pre の {unknown} は、開世界では決められない")
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
    if len(world) != 1 or not world <= WORLDS:
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
            neg, rel, args = fact(f, T)
            h = m.holds(neg, rel, args)
            if h is None and not neg:   # 示されていない肯定の文は、どちらの世界でも成り立つと言えない
                h = False
            if h is None:
                m.err(f"expect の {show(f)} は、開世界では決められない")
            elif not h:
                m.err(f"expect の {show(f)} が、最後の状態で成り立っていない")
        if "halted" in run:  # 法則 halt
            rest = m.applicable()
            if m.world != "closed_world":
                m.err("halted は、開世界では決められない（示されていない文から、当てはまらないとは言えない）")
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
