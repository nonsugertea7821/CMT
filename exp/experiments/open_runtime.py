"""名前を最初に全部宣言しない実行器（開世界）と、仮説 h_open_runtime の確かめ。結果を見る前に、この説明と手順を登録した。

実行器（OpenMachine）:
  - 世界は world（開世界）。述べていない文に真偽を与えない。真を要する pre が述べられていなければ、決められずに止まる。
  - 最初に宣言するのは、記録の individuals に書いた個体だけ。記録には、最初に在る個体だけを書く。
  - 歩みが、まだ宣言されていない名前を名指したとき、その位置が「在るようにする位置」なら、その歩みで宣言する。
    在るようにする位置: pre で exists をその位置について「述べられていない」とし、post で真と述べる位置。
    種類は、new なら動詞の new_kind、ほかの位置ならその端の型。それ以外の位置なら誤り（宣言されていない名前の文は文にならない）。
  - 宣言は取り消さない。exists は真偽の軸の文で、post で述べたり取り除いたりする（std.v_freeze は exists を取り除くだけ）。
  - フレームは1歩ごと。各フレームの宣言の集まりを記録する。巻き戻しは、この実行器では扱わない。
  - halted: 当てはまる歩みが1つでも見つかれば halted: false と決まる。まだ使っていない名前を在るようにする位置に使う歩みも数える。
    見つからなくても、開世界で名前も開いているので halted: true とは決められない。

仮説 h_open_runtime: 宣言を歩みで足す開世界の実行器で、実行の記録は歩める。その実行で、宣言は減らず、増えるのは在るようにする歩みだけである。
記録: exp/tests の実行の記録すべてと、sys_declaration.py の RECORD。どれも individuals を「最初の facts で在ると述べた個体」だけにして実行する。
判定（登録した基準）: 支持は、次のすべてが成り立つとき。
  1. どの記録も、エラーなく歩める（決められずに止まる歩みがない）。expect がどれも成り立つ（決められないものがない）。
  2. どの歩みでも宣言は減らない。
  3. 宣言が増えた歩みは、どれも在るようにする位置に新しい名前を使った歩みである。
  4. halted: false と書いた記録では、halted: false と決まる。
  どれかが成り立たなければ反証。2 と 3 は実行器の作りからほぼ決まる。経験的な中身は 1 と 4。

行（sys_open_runtime.json）:
  歩みの行（"step 記録 番号 動詞"）: ok, declared_grows, declared_shrinks, grows_by_creation（増えたなら在るようにする位置による）
  記録の行（"run 記録"）: run_ok（歩み・expect・halted にエラーがない）, halted_false_decided（halted: false を書いた記録だけ）
  summary 行: supported

使い方:
  python exp/experiments/open_runtime.py
"""
import contextlib
import io
import itertools
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/runtime"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import runtime as rt  # noqa: E402
    import sys_declaration  # noqa: E402

OUT = ROOT / "exp/experiments/results"
FRESH = "_fresh"


def dynamic(T, verb):
    x = verb
    while x in T.N and "pre" not in T.N[x]:
        x = T.up(x)
    return T.N.get(x) or {}


def creation_positions(T, verb):
    n = dynamic(T, verb)
    pre = {a.get("from") for a in n.get("pre", []) if a["is"] == "exists" and a.get("neg")}
    post = {a.get("from") for a in n.get("post", []) if a["is"] == "exists" and not a.get("neg") and "val" not in a}
    return pre & post


class OpenMachine(rt.Machine):
    def __init__(self, T, run, name):
        super().__init__(T, run, name, "world")
        self.frames = [set(self.ind)]

    def kind_at(self, verb, pos):
        if pos == "new":
            return self.T.resolve(dynamic(self.T, verb).get("new_kind", "any"), "exp")
        return self.T.end(verb, pos)

    def step(self, verb, b, where):
        created = False
        for pos, name in b.items():
            if name in self.ind:
                continue
            if pos not in creation_positions(self.T, verb):
                self.frames.append(set(self.ind))
                return self.err(f"{where}: {pos} の {name} は宣言されておらず、在るようにする位置でもない")
            self.ind[name] = self.kind_at(verb, pos)
            created = True
        n = len(self.errors)
        super().step(verb, b, where)
        self.frames.append(set(self.ind))
        return created and len(self.errors) == n

    def halted_false_decided(self):
        """当てはまる歩みが見つかれば True。今の名前だけの歩み（applicable）と、
        まだ使っていない名前を在るようにする位置に1つ置いた歩みを数える。"""
        if self.applicable():
            return True
        for vid, n in self.T.N.items():
            if "pre" not in n:
                continue
            poss = ["from", "to"] + (["new"] if any("new" in rt.atom(f)[2] for f in n["pre"] + n["post"]) else [])
            for pos in creation_positions(self.T, vid) & set(poss):
                others = [p for p in poss if p != pos]
                self.ind[FRESH] = self.kind_at(vid, pos)
                try:
                    for combo in itertools.permutations([i for i in self.ind if i != FRESH], len(others)):
                        b = dict(zip(others, combo)) | {pos: FRESH}
                        r, _ = self.bind(vid, b)
                        if r and self.quant(self.holds(*x) is True for x in r["pre"]) \
                                and not all(self.holds(*x) is True for x in r["post"]):
                            return True
                finally:
                    del self.ind[FRESH]
        return False


def initial_only(run):
    """individuals を、最初の facts で在ると述べた個体だけにする。"""
    first = {f["from"] for f in run.get("facts", []) if f["is"] == "exists" and not f.get("neg")}
    return {**run, "individuals": {i: v for i, v in run["individuals"].items() if i in first}}


def run_one(T, name, run):
    m = OpenMachine(T, initial_only(run), name)
    m.check_laws("最初の状態")
    rows = {}
    for i, st in enumerate(run.get("steps", [])):
        verb, b = st["is"], {k: v for k, v in st.items() if k != "is"}
        n = len(m.errors)
        created = m.step(verb, b, f"steps[{i}] {verb}")
        before, after = m.frames[-2], m.frames[-1]
        grows = len(after) > len(before)
        rows[f"step {name} {i} {verb}"] = {"ok": int(len(m.errors) == n), "declared_grows": int(grows),
                                           "declared_shrinks": int(not before <= after),
                                           "grows_by_creation": int(not grows or bool(created))}
    for f in run.get("expect", []):
        h = m.holds(*rt.fact(f, T))
        if h is None:
            m.err(f"expect の {rt.show(f)} は、述べられていない文の真偽で、この世界では決められない")
        elif not h:
            m.err(f"expect の {rt.show(f)} が成り立っていない")
    row = {"run_ok": None}
    if run.get("halted") is False:
        row["halted_false_decided"] = int(m.halted_false_decided())
    elif run.get("halted") is True:
        m.err("halted: true は、開世界で名前も開いているので決められない")
    row["run_ok"] = int(not m.errors)
    rows[f"run {name}"] = row
    for e in m.errors:
        print(" -", e)
    print(name, "フレームごとの宣言:", [sorted(f) for f in m.frames])
    return rows


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = {}
    for path in sorted((ROOT / "exp/tests").glob("*.yaml")):
        rows |= run_one(T, path.stem, yaml.safe_load(path.read_text(encoding="utf-8")))
    rows |= run_one(T, "sys_declaration", sys_declaration.RECORD)
    supported = all(r.get("ok", 1) and not r.get("declared_shrinks", 0) and r.get("grows_by_creation", 1)
                    and r.get("run_ok", 1) and r.get("halted_false_decided", 1) for r in rows.values())
    rows["summary"] = {"supported": int(supported)}
    for k, r in rows.items():
        print(k, r)
    (OUT / "sys_open_runtime.json").write_text(json.dumps(
        {"_source": "exp/experiments/open_runtime.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("判定:", "支持" if supported else "反証")


if __name__ == "__main__":
    main()
