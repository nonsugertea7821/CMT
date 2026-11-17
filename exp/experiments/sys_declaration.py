"""仮説 h_open_declaration（時間を含む実行では、宣言の範囲は開いている。各時点では、宣言 ＝ 存在で閉じている）を確かめる。
結果を見る前に、この説明と手順を登録した。

同じ歩みの並びを、2つの書き方で実行する。
  (a) 今の書き方: 生まれる個体の名前も最初にすべて宣言し、在ることは exists の文で述べる（今の実行器そのまま、閉世界）。
  (b) 宣言を歩みで足す書き方: 最初に宣言するのは、最初に在る個体だけ。exists(x) は「x がいま宣言されている」と読む。
      - pre の exists(x) の読み方: 真 ⇔ 宣言されている。述べられていない・偽 ⇔ 宣言されていない。
      - post で exists(x) を真と述べる ⇔ x を宣言する（種類は動詞の new_kind、なければその位置の端の型）。
      - post で exists(x) を述べられていない（または偽）にする ⇔ x の宣言を取り消す。
      - 歩みが名指す、まだ宣言されていない名前は、束縛のためだけに仮に名指す（宣言ではない）。
      - exists 以外の文と法則の当てはめは、今の実行器と同じ。法則には、宣言されている個体の exists を真として渡す。
  記録は、生まれる動詞と消える動詞を含むように、このファイルの RECORD に固定する（exp/tests には置かない。tc の検査に影響させない）。

判定（登録した基準）:
  支持: 次の3つがすべて成り立つ。
    1. (b) で、どの歩みもエラーなく歩める（a と同じく）。
    2. 各歩みの後で、(a) の「exists を真と述べた個体」と (b) の「宣言されている個体」が一致し、exists 以外の文がすべて一致する。
    3. 各歩みの後で、(b) の状態に、宣言されていない名前を含む文が 1 つもない（宣言されていないものについての文は文にならない）。
  反証: どれかが成り立たない。とくに、消える動詞（std.v_freeze）を宣言の取り消しとして読むと 3 が破れる場合。
  ほかに、判定には使わず観察として記録する:
    a_applicable / b_fresh_applicable  最後の状態で当てはまる歩みの数。(b) では、まだ使っていない名前を new に使える歩みも数える。

行（sys_declaration.json）: 歩みごとに 1 行。値は b_ok, same_state, dangling（宣言されていない名前を含む文の数）。
最後に summary 行: a_applicable, b_fresh_applicable, supported（0 か 1）。

使い方:
  python exp/experiments/sys_declaration.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/runtime")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import runtime as rt  # noqa: E402

OUT = ROOT / "exp/experiments/results"
FRESH = "fresh_name"

RECORD = {
    "individuals": {"sys1": {"is": "system"}, "dec1": {"is": "exp.decision"},
                    "r1": {"is": "realizable_entity"}, "q1": {"is": "quality"}},
    "facts": [{"is": "exists", "from": "sys1"}, {"is": "exists", "from": "dec1"}],
    "steps": [
        {"is": "std.v_learn", "from": "sys1", "to": "dec1", "new": "r1"},   # r1 が生まれる
        {"is": "exp.v_see", "from": "sys1", "to": "dec1", "new": "q1"},     # q1 が生まれる
        {"is": "std.v_freeze", "from": "dec1", "to": "sys1", "new": "r1"},  # r1 が消える
    ],
}


class Declared(rt.Machine):
    """(b) 宣言を歩みで足す書き方。exists は宣言の集まりから読む。"""

    def __init__(self, T, run, name):
        initial = {f["from"] for f in run["facts"] if f["is"] == "exists"}
        run = {"individuals": {i: v for i, v in run["individuals"].items() if i in initial},
               "facts": [f for f in run["facts"] if f["is"] != "exists"]}
        super().__init__(T, run, name, "closed_world")
        self.declared = set(self.ind)

    def holds(self, r, rel, args):
        if rel == "exists":
            d = args[0] in self.declared
            return d if r is True else not d
        return super().holds(r, rel, args)

    def stated_true(self):
        return super().stated_true() | {("exists", (x,)) for x in self.declared}

    def fact_ok(self, rel, args, f):
        if rel != "exists":
            super().fact_ok(rel, args, f)

    def step(self, verb, b, where):
        T = self.T
        x = verb
        while x in T.N and "pre" not in T.N[x]:
            x = T.up(x)
        for pos, name in b.items():   # まだ宣言されていない名前を、束縛のためだけに仮に名指す
            if name not in self.ind:
                self.ind[name] = T.resolve(T.N[x].get("new_kind", "any"), "exp") if pos == "new" else T.end(verb, pos)
        r, why = self.bind(verb, b)
        if r is None:
            return self.err(f"{where}: {why}")
        if len(set(b.values())) != len(b):
            return self.err(f"{where}: 別々の位置に同じ個体が割り当てられている")
        if not self.quant(self.holds(*f) for f in r["pre"]):
            return self.err(f"{where}: pre の {[rt.show_atom(*f) for f in r['pre'] if not self.holds(*f)]} が成り立っていない")
        for v, rel, args in r["post"]:
            if rel == "exists":
                (self.declared.add if v is True else self.declared.discard)(args[0])
            elif v == rt.UNSTATED:
                self.facts.pop((rel, args), None)
            else:
                self.facts[(rel, args)] = v
        self.check_laws(where)

    def dangling(self):
        return sorted(f"{rel}{args}" for (rel, args) in self.facts if any(a not in self.declared for a in args))


def state_a(m):
    return ({a[0] for (rel, a), v in m.facts.items() if rel == "exists" and v is True},
            {k: v for k, v in m.facts.items() if k[0] != "exists"})


def fresh_applicable(m):
    """(b) で、まだ使っていない名前を new に使って当てはまる歩みを数える。"""
    m.ind[FRESH] = "any"
    n = 0
    for vid, node in m.T.N.items():
        if "pre" not in node or not any("new" in rt.atom(f)[2] for f in node["pre"] + node["post"]):
            continue
        kind = m.T.resolve(node.get("new_kind", "any"), "exp")
        m.ind[FRESH] = kind
        for a in m.declared:
            for c in m.declared:
                r, _ = m.bind(vid, {"from": a, "to": c, "new": FRESH})
                if r and a != c and m.quant(m.holds(*x) is True for x in r["pre"]) \
                        and not all(m.holds(*x) is True for x in r["post"]):
                    n += 1
    del m.ind[FRESH]
    return n


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    a = rt.Machine(T, RECORD, "a", "closed_world")
    b = Declared(T, RECORD, "b")
    a.check_laws("最初の状態")
    b.check_laws("最初の状態")
    rows = {}
    for i, st in enumerate(RECORD["steps"]):
        verb, bind = st["is"], {k: v for k, v in st.items() if k != "is"}
        na, nb = len(a.errors), len(b.errors)
        a.step(verb, bind, f"steps[{i}] {verb}")
        b.step(verb, bind, f"steps[{i}] {verb}")
        if len(a.errors) > na:
            raise SystemExit(f"(a) が今の実行器で歩めない（記録の誤り）: {a.errors[na:]}")
        ex, other = state_a(a)
        rows[f"{i} {verb}"] = {"b_ok": int(len(b.errors) == nb),
                               "same_state": int(ex == b.declared and other == b.facts),
                               "dangling": len(b.dangling())}
        print(f"steps[{i}] {verb}: (a) 在る {sorted(ex)} / (b) 宣言 {sorted(b.declared)} / 宣言されていない名前を含む文 {b.dangling()}")
    if b.errors:
        print("(b) のエラー:", b.errors)
    supported = all(r["b_ok"] and r["same_state"] and r["dangling"] == 0 for r in rows.values())
    rows["summary"] = {"a_applicable": len(a.applicable()), "b_fresh_applicable": fresh_applicable(b),
                       "supported": int(supported)}
    print("summary", rows["summary"])
    (OUT / "sys_declaration.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_declaration.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("判定:", "支持" if supported else "反証")


if __name__ == "__main__":
    main()
