"""宣言の範囲を、固定する動詞（std.v_freeze）に従わせると、宣言されていない名前の文が残らず、ほかは壊れないか
（h_dangling_by_append_only_declaration: v_depend(declared_scope, std.v_freeze)）。issue #938。

系列:
  h_open_declaration（sys_declaration.py）は反証: 宣言を歩みで足す書き方 (b) で std.v_freeze が r1 の宣言を取り消すと、
  depend(r1, sys1) と refer(r1, dec1) が、宣言されていない名前の文として残った。
  解釈（未検証）: 残るのは、宣言の取り消しが、その名前についての文に及ばないから（宣言が追記専用のように振る舞う）。

手（一時の実行器だけを替える。体系と実行器のファイルは替えない）:
  (a) 今の実行器そのまま（runtime.Machine、閉世界。名前は最初にすべて宣言し、在ることは exists で述べる）。
  (b) sys_declaration.Declared そのまま（宣言を歩みで足し、exists を偽にすると宣言を取り消す）。
  (c) (b) に一つだけ足す: 歩みで宣言を取り消した名前があれば、その名前を端に持つ文を、同じ歩みのうちに取り消す（述べられていないにする）。
      法則の当てはめは、取り消しの後に行う。

材料（モデルは走らせない）:
  A. 決めた記録: sys_declaration.RECORD の 3 歩に、4 歩目として std.v_learn(from dec1, to sys1, new r1) を足す（r1 が生まれ直す）。
     (a)(b)(c) で歩ませる。(a) が歩めなければ、記録の誤りとして止め、判定しない。
  B. 無作為の歩み: 最初の状態は sys1（system）と dec1（exp.decision）が在るだけ。乱数の種 0 から、長さ 6 の歩みを 200 本。
     各歩みで、(c) の状態で当てはまる手をすべて並べ、一様に 1 つ選ぶ。手の並べ方:
       - 動的な動詞（pre を持つ）ごとに、from と to は (c) で宣言されている名前の、異なる組。
       - new を使う動詞は、new に「宣言されている名前」「前に宣言され、いまは取り消されている名前」「新しい名前 n<番号> を 1 つ」を試す。
       - bind が通り、pre がすべて成り立ち、post のすべてが既に成り立っているのではないもの（runtime.applicable と同じ条件）。
     選んだ手を、(b) と (c) の両方で歩ませる。手が 1 つもなければ、その本はそこで止める。
     各歩みの後に数える: (c) のエラー（pre の破れと法則の違反）、(c) と (b) の宣言されていない名前の文の数、
     生まれ直した名前について、生まれ直す前の歩みで述べられ、生まれ直してから述べ直されていない文（古い文）の数。

判定（事前登録）:
  前提: A で (a) が 4 歩とも歩める。B で、宣言を取り消す歩みを 1 度以上含む本が 50 以上。満たさなければ判定しない。
  h_dangling_by_append_only_declaration:
    次がすべて成り立てば支持:
      1. A で (c) が 4 歩ともエラーなく歩め、各歩みの後の宣言されていない名前の文が 0、4 歩目の後の古い文が 0。
      2. B で (c) のエラーが合わせて 0、宣言されていない名前の文が、どの歩みの後も 0。
    どれかが破れれば反証。
  参考（判定に使わない）: A と B の (b) の宣言されていない名前の文の数、A の (a) の 4 歩目の後の古い文の数、
    B で生まれ直しを含む本の数とその古い文の数（(b) と (c)）、B で (b) がエラーになった歩みの数、手の数の平均。

開示（結果を見る前に分かっていること）:
  - sys_declaration の結果を読んでいる（(b) で 3 歩目の後に宣言されていない名前の文が 2）。
  - (c) の取り消しは、宣言されていない名前の文が残らないように作ったので、判定の「宣言されていない名前の文が 0」は、作り方からほぼ決まる。
    中身があるのは、取り消した後でも、法則と、その後の歩みの pre が破れないか（判定 1 と 2 のエラー）と、生まれ直しで古い文が消えるか。
  - 支持でも、言えるのは、この記録とこの歩ませ方で、取り消しを文に及ぼしても壊れないこと。体系に式として書けることまでは言えない
    （(c) の取り消しは、実行器の外のコードで書いている）。式で書けるかは、次の仮説に回す。
  - 反証でも、宣言を固定に従わせる案そのものが駄目とまでは言えない。言えるのは、この取り消し方では、どこかで法則か歩みが破れること。
  - B が 2 時間で終わらなければ止め、判定しない。

出力: results/sys_declaration_follows_freeze.json
使い方:
  python exp/experiments/sys_declaration_follows_freeze.py
"""
import contextlib
import io
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import sys_declaration as sd  # noqa: E402
rt, tc = sd.rt, sd.tc

OUT = ROOT / "exp/experiments/results/sys_declaration_follows_freeze.json"
RECORD = {**sd.RECORD, "steps": sd.RECORD["steps"] + [{"is": "std.v_learn", "from": "dec1", "to": "sys1", "new": "r1"}]}
START = {"individuals": {"sys1": {"is": "system"}, "dec1": {"is": "exp.decision"}},
         "facts": [{"is": "exists", "from": "sys1"}, {"is": "exists", "from": "dec1"}]}
N_WALKS, LENGTH, SEED = 200, 6, 0


class Tracked:
    """歩みの番号を数え、文がいつ述べられたかと、名前がいつ生まれたかを覚える。"""

    def track_init(self):
        self.t = 0
        self.said = {k: 0 for k in self.facts}
        self.born = {x: 0 for x in self.declared}

    def after_step(self, before_decl, before_facts):
        self.t += 1
        for k, v in self.facts.items():
            if before_facts.get(k, rt.UNSTATED) != v or k not in before_facts:
                self.said[k] = self.t
        for k in list(self.said):
            if k not in self.facts:
                del self.said[k]
        for x in self.declared - before_decl:
            self.born[x] = self.t

    def stale(self):
        return sum(1 for (rel, args), t in self.said.items()
                   if any(a in self.born and self.born[a] > 0 and t < self.born[a] for a in args))


class B(Tracked, sd.Declared):
    def __init__(self, T, run, name):
        super().__init__(T, run, name)
        self.track_init()

    def step(self, verb, b, where):
        d0, f0 = set(self.declared), dict(self.facts)
        super().step(verb, b, where)
        self.after_step(d0, f0)


class C(B):
    def check_laws(self, where):
        if not getattr(self, "_hold", False):
            super().check_laws(where)

    def step(self, verb, b, where):
        d0, f0, ne = set(self.declared), dict(self.facts), len(self.errors)
        self._hold = True
        try:
            sd.Declared.step(self, verb, b, where)
        finally:
            self._hold = False
        gone = d0 - self.declared
        for k in [k for k in self.facts if any(a in gone for a in k[1])]:
            del self.facts[k]
        if len(self.errors) == ne:
            self.check_laws(where)
        self.after_step(d0, f0)


class A(Tracked, rt.Machine):
    def __init__(self, T, run, name):
        super().__init__(T, run, name, "closed_world")
        self.declared = {a[0] for (rel, a), v in self.facts.items() if rel == "exists" and v is True}
        self.track_init()

    def step(self, verb, b, where):
        d0, f0 = set(self.declared), dict(self.facts)
        super().step(verb, b, where)
        self.declared = {a[0] for (rel, a), v in self.facts.items() if rel == "exists" and v is True}
        self.after_step(d0, f0)


def moves(m, fresh):
    T, out = m.T, []
    decl = sorted(m.declared)
    gone = sorted(set(m.ind) - m.declared)
    for vid, node in T.N.items():
        if "pre" not in node:
            continue
        uses_new = any("new" in rt.atom(f)[2] for f in node["pre"] + node.get("post", []))
        news = (decl + gone + [fresh]) if uses_new else [None]
        kind = T.resolve(node.get("new_kind", "any"), "exp")
        for a in decl:
            for c in decl:
                if a == c:
                    continue
                for n in news:
                    if n is not None and n in (a, c):
                        continue
                    b = {"from": a, "to": c} | ({"new": n} if n is not None else {})
                    added = n is not None and n not in m.ind
                    if added:
                        m.ind[n] = kind
                    try:
                        r, _ = m.bind(vid, b)
                        ok = r is not None and m.quant(m.holds(*x) is True for x in r["pre"]) \
                            and not all(m.holds(*x) is True for x in r["post"])
                    finally:
                        if added:
                            del m.ind[n]
                    if ok:
                        out.append((vid, b))
    return out


def part_a(T):
    a, b, c = A(T, RECORD, "a"), B(T, RECORD, "b"), C(T, RECORD, "c")
    for m in (a, b, c):
        m.check_laws("最初の状態")
    rows = []
    for i, st in enumerate(RECORD["steps"]):
        verb, bind = st["is"], {k: v for k, v in st.items() if k != "is"}
        ne = {m.name: len(m.errors) for m in (a, b, c)}
        for m in (a, b, c):
            m.step(verb, bind, f"steps[{i}] {verb}")
        if len(a.errors) > ne["a"]:
            return None, a.errors
        rows.append({"step": f"{i} {verb}", "c_ok": int(len(c.errors) == ne["c"]), "b_ok": int(len(b.errors) == ne["b"]),
                     "c_dangling": len(c.dangling()), "b_dangling": len(b.dangling()),
                     "a_stale": a.stale(), "b_stale": b.stale(), "c_stale": c.stale()})
        print("A", rows[-1], flush=True)
    return rows, c.errors + b.errors


def part_b(T, deadline):
    rng = random.Random(SEED)
    walks = []
    for w in range(N_WALKS):
        b, c = B(T, START, "b"), C(T, START, "c")
        rec = {"steps": [], "c_errors": 0, "b_errors": 0, "c_dangling_max": 0, "b_dangling_max": 0,
               "removed": 0, "reborn": 0, "c_stale_max": 0, "b_stale_max": 0, "n_moves": []}
        k = 0
        for i in range(LENGTH):
            if time.time() > deadline:
                return walks, True
            fresh = f"n{k}"
            ms = moves(c, fresh)
            rec["n_moves"].append(len(ms))
            if not ms:
                break
            verb, bind = rng.choice(ms)
            if bind.get("new") == fresh:
                k += 1
            reborn = bind.get("new") in (set(c.ind) - c.declared)
            ne = (len(b.errors), len(c.errors))
            d0 = set(c.declared)
            for m in (b, c):
                m.step(verb, bind, f"walk[{w}] steps[{i}] {verb}")
            rec["steps"].append([verb, bind])
            rec["b_errors"] += int(len(b.errors) > ne[0])
            rec["c_errors"] += int(len(c.errors) > ne[1])
            rec["removed"] += int(bool(d0 - c.declared))
            rec["reborn"] += int(reborn)
            rec["c_dangling_max"] = max(rec["c_dangling_max"], len(c.dangling()))
            rec["b_dangling_max"] = max(rec["b_dangling_max"], len(b.dangling()))
            rec["c_stale_max"] = max(rec["c_stale_max"], c.stale())
            rec["b_stale_max"] = max(rec["b_stale_max"], b.stale())
        rec["c_error_texts"] = c.errors[:5]
        rec["b_error_texts"] = b.errors[:5]
        walks.append(rec)
        print("B", w, len(rec["steps"]), rec["removed"], rec["reborn"], rec["c_errors"], rec["b_dangling_max"], flush=True)
    return walks, False


def main():
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows, a_errors = part_a(T)
    if rows is None:
        OUT.write_text(json.dumps({"a_failed": a_errors}, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.exit("(a) が歩めない")
    walks, timed_out = part_b(T, t0 + 7200)
    n_removed_walks = sum(1 for w in walks if w["removed"])
    a_ok = all(r["c_ok"] and r["c_dangling"] == 0 for r in rows) and rows[-1]["c_stale"] == 0
    b_ok = sum(w["c_errors"] for w in walks) == 0 and all(w["c_dangling_max"] == 0 for w in walks)
    summary = {
        "A_c_ok": a_ok, "A_b_dangling": [r["b_dangling"] for r in rows],
        "A_last_stale": {k: rows[-1][k] for k in ("a_stale", "b_stale", "c_stale")},
        "B_walks": len(walks), "B_timed_out": timed_out, "B_walks_with_removal": n_removed_walks,
        "B_c_error_steps": sum(w["c_errors"] for w in walks), "B_b_error_steps": sum(w["b_errors"] for w in walks),
        "B_c_dangling_max": max((w["c_dangling_max"] for w in walks), default=0),
        "B_b_dangling_walks": sum(1 for w in walks if w["b_dangling_max"]),
        "B_walks_with_rebirth": sum(1 for w in walks if w["reborn"]),
        "B_b_stale_walks": sum(1 for w in walks if w["b_stale_max"]),
        "B_c_stale_walks": sum(1 for w in walks if w["c_stale_max"]),
        "B_mean_moves": round(sum(sum(w["n_moves"]) for w in walks) / max(1, sum(len(w["n_moves"]) for w in walks)), 2),
        "secs": round(time.time() - t0, 1),
    }
    if timed_out or n_removed_walks < 50:
        judgment = "not_judged"
    elif a_ok and b_ok:
        judgment = "support"
    else:
        judgment = "refute"
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_declaration_follows_freeze.py", "_commit": commit,
                               "summary": summary, "judgment": {"h_dangling_by_append_only_declaration": judgment},
                               "A": rows, "A_errors": a_errors, "B": walks}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps({"h_dangling_by_append_only_declaration": judgment}))


if __name__ == "__main__":
    main()
