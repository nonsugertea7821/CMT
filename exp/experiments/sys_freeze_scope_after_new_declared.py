"""h_freeze_scope_after_new_declared（#949）: new を宣言する動詞にそろえた後なら、宣言の範囲は固定に従えるか。

前の実験（sys_declaration_follows_freeze_v2.py、結果 results/sys_declaration_follows_freeze_v2.json、#943）:
  (c)（宣言を取り消した名前の文を同じ歩みで取り消す）の「それ以外の」エラーが 42 で、h_dangling_by_append_only_declaration は反証。
  宣言されていない名前の文は、new を宣言せずに使う動詞（undeclared_new_verbs）からだけ出た（h_dangling_by_undeclared_new 支持）。
  #943 の追加の分析（結果を見た後）: 42 のうち 32 は (b) にだけ残る前の生の文に頼る手、9 は状態が分かれた後の連鎖、4 は宣言されていない名前、1 はほか。

手: 型の木 T を前の版と同じく読み、宣言せずに new を使う動詞（前の版の undeclared_new_verbs）の定義を、メモリの上で次のようにそろえる。
  - pre が new を端に持つ肯定の文を述べる動詞（new は前から在る名前）: pre に exists(new) を足す。
  - そうでない動詞（new はこの歩みで生まれる名前）: post に exists(new) を足す。
  ファイルは書き換えない（写しの代わりにメモリで当てる）。(b) と (c) は前の版と同じ（sys_declaration_follows_freeze の B と C）。

材料と歩ませ方: 前の版と同じ（最初の状態、乱数の種 1、長さ 8、300 本、組「取り消す」「生まれ直す」「ほか」を 1/3 ずつ）。
  直すところ 1 つ: 候補を「(b) で破れない手」から「(b) でも (c) でも破れない手」にする。こうすると (b) と (c) の宣言の集まりは分かれない
  （前の版の 9 の連鎖を除くため）。
  候補を作るとき、(b) で破れず (c) で破れる手を、選ぶ前にすべて数え、次に分ける:
    (i)   (c) で成り立たない pre の文が、どれも (c) で宣言されていない名前を端に持つ（宣言の外の文に頼る手）。
    (ii)  (i) でなく、成り立たない pre の文が、どれも (b) で成り立ち、端のどれかが、一度取り消されて生まれ直した名前で、
          (b) でその文が述べられた歩みが、その名前が最後に生まれた歩みより前（前の生の文に頼る手）。
    (iii) ほか（法則の破れも含む）。
  (i) と (ii) は (c) が退けるように作ったもので、判定から除く。
  参考に、(c) で破れず (b) で破れる手も数える。

判定（事前登録）:
  前提: 宣言を取り消す歩みを含む本が 50 以上、生まれ直す歩みを含む本が 20 以上。2 時間で終わらなければ止める。満たさなければ判定しない。
  支持: (iii) が 0、(c) で一度宣言された名前の宣言されていない文がどの歩みの後も 0、(c) の古い文がどの歩みの後も 0、
        (c) の一度も宣言されていない名前の文が 0（選んだ手を (c) で歩ませてエラーが出たら、それも (iii) に数える）。
  反証: どれかが破れる。

開示（結果を見る前に分かっていること）:
  - 前の版の結果と #943 の追加の分析を見ている。選び方を「両方で破れない手」に変えたのは、それを見たから。
  - 9 つの動詞の定義を読んで、そろえ方を 2 つに分けた（pre が new の肯定の文を持つのは exp.v_substitute、exp.v_withdraw、
    ja_basic.j_go、ja_basic.j_keep、std.v_vary。ほかの exp.v_adopt、exp.v_deliver、ja_basic.j_put、subj.v_sell は post で宣言する）。
    この分け方は定義の式から機械的に決め、名前では決めない。
  - 両方で破れない手から選ぶので、選んだ手の (c) のエラーは作り方から 0 になる見込み。中身があるのは、候補を作るときの (iii) の数と、
    宣言されていない文・古い文が残らないか。
  - 手元で走らせるのはこの 1 回だけ。tc と ec は手元で走らせない。

出力: results/sys_freeze_scope_after_new_declared.json
使い方:
  python exp/experiments/sys_freeze_scope_after_new_declared.py
"""
import contextlib
import io
import json
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import sys_declaration_follows_freeze_v2 as v2  # noqa: E402
v1, rt, tc = v2.v1, v2.rt, v2.tc

OUT = ROOT / "exp/experiments/results/sys_freeze_scope_after_new_declared.json"
N_WALKS, LENGTH, SEED = 300, 8, 1


def align(T):
    out = {}
    for v in sorted(v2.undeclared_new_verbs(T)):
        node = T.N[v]
        uses = any(not neg and rel != "exists" and "new" in args for neg, rel, args in
                   ((f.get("neg", False), f["is"], tuple(x for k, x in f.items() if k in ("from", "to"))) for f in node["pre"]))
        if uses:
            node["pre"] = list(node["pre"]) + [{"is": "exists", "from": "new"}]
            out[v] = "pre"
        else:
            node["post"] = list(node["post"]) + [{"is": "exists", "from": "new"}]
            out[v] = "post"
    return out


def failing_pre(m, verb, bind):
    s = v2.snapshot(m)
    try:
        for pos, name in bind.items():
            if name not in m.ind:
                m.ind[name] = "any"
        r, _ = m.bind(verb, bind)
        return [f for f in (r or {}).get("pre", []) if not m.holds(*f)]
    finally:
        v2.restore(m, s)


def classify(b, c, hb, verb, bind):
    bad = failing_pre(c, verb, bind)
    if not bad:
        return "iii"
    if all(any(a not in c.declared for a in f[2]) for f in bad):
        return "i"
    for f in bad:
        if not b.holds(*f):
            return "iii"
        t = b.said.get((f[1], f[2]))
        if t is None or not any(a in hb.removed and a in hb.last_birth and t < hb.last_birth[a] for a in f[2]):
            return "iii"
    return "ii"


def main():
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    aligned = align(T)
    left = sorted(v2.undeclared_new_verbs(T))
    rng = random.Random(SEED)
    walks, timed_out, picked, cls = [], False, Counter(), Counter()
    examples = []
    for w in range(N_WALKS):
        b, c = v1.B(T, v1.START, "b"), v1.C(T, v1.START, "c")
        hb, hc = v2.Hist(), v2.Hist()
        hb.ever |= b.declared
        hc.ever |= c.declared
        rec = {"steps": [], "i": 0, "ii": 0, "iii": 0, "c_only": 0, "c_step_errors": 0, "b_step_errors": 0,
               "removed": 0, "reborn": 0, "c_once_max": 0, "b_once_max": 0, "c_stale_max": 0, "b_stale_max": 0,
               "c_never": [], "diverged": 0}
        k = 0
        for i in range(LENGTH):
            if time.time() > t0 + 7200:
                timed_out = True
                break
            fresh = f"n{k}"
            cand = v1.moves(b, fresh)
            for mv in v1.moves(c, fresh):
                if mv not in cand:
                    cand.append(mv)
            ms = []
            for mv in cand:
                ob, oc = v2.ok_in(b, *mv), v2.ok_in(c, *mv)
                if ob and oc:
                    ms.append(mv)
                elif ob:
                    g = classify(b, c, hb, *mv)
                    rec[g] += 1
                    cls[g] += 1
                    if g == "iii" and len(examples) < 20:
                        examples.append({"walk": w, "step": i, "verb": mv[0], "bind": mv[1],
                                         "failing": [rt.show_atom(*f) for f in failing_pre(c, *mv)]})
                elif oc:
                    rec["c_only"] += 1
            if not ms:
                break
            groups = {"remove": [mv for mv in ms if v2.removes(T, mv[0])],
                      "reborn": [mv for mv in ms if mv[1].get("new") in hb.removed and mv[1].get("new") not in b.declared]}
            groups["other"] = [mv for mv in ms if mv not in groups["remove"] and mv not in groups["reborn"]]
            order = ["remove", "reborn", "other"]
            g = rng.choice(order)
            if not groups[g]:
                g = rng.choice([x for x in order if groups[x]])
            verb, bind = rng.choice(groups[g])
            picked[g] += 1
            if bind.get("new") == fresh:
                k += 1
            rec["reborn"] += int(bind.get("new") in hc.removed and bind.get("new") not in c.declared)
            for m, h, key in ((b, hb, "b"), (c, hc, "c")):
                d0, f0, ne = set(m.declared), dict(m.facts), len(m.errors)
                m.step(verb, bind, f"walk[{w}] steps[{i}] {verb}")
                if len(m.errors) > ne:
                    rec[f"{key}_step_errors"] += 1
                v2.note(m, h, verb, d0, f0)
            rec["diverged"] += int(b.declared != c.declared)
            rec["removed"] += int(v2.removes(T, verb))
            rec["steps"].append([verb, bind])
            for m, h, key in ((b, hb, "b"), (c, hc, "c")):
                once, never, stale = v2.counts(m, h)
                rec[f"{key}_once_max"] = max(rec[f"{key}_once_max"], len(once))
                rec[f"{key}_stale_max"] = max(rec[f"{key}_stale_max"], stale)
                if key == "c":
                    for kk in never:
                        item = [f"{kk[0]}{kk[1]}", hc.added_by.get(kk)]
                        if item not in rec["c_never"]:
                            rec["c_never"].append(item)
        walks.append(rec)
        print("W", w, len(rec["steps"]), rec["removed"], rec["reborn"], rec["i"], rec["ii"], rec["iii"],
              rec["c_once_max"], rec["c_stale_max"], len(rec["c_never"]), flush=True)
        if timed_out:
            break
    summary = {
        "walks": len(walks), "timed_out": timed_out,
        "walks_with_removal": sum(1 for w in walks if w["removed"]),
        "walks_with_rebirth": sum(1 for w in walks if w["reborn"]),
        "cand_i": cls["i"], "cand_ii": cls["ii"], "cand_iii": cls["iii"],
        "cand_c_only": sum(w["c_only"] for w in walks),
        "c_step_errors": sum(w["c_step_errors"] for w in walks),
        "b_step_errors": sum(w["b_step_errors"] for w in walks),
        "diverged_steps": sum(w["diverged"] for w in walks),
        "c_once_max": max((w["c_once_max"] for w in walks), default=0),
        "b_once_walks": sum(1 for w in walks if w["b_once_max"]),
        "c_stale_max": max((w["c_stale_max"] for w in walks), default=0),
        "b_stale_walks": sum(1 for w in walks if w["b_stale_max"]),
        "c_never_facts": sum(len(w["c_never"]) for w in walks),
        "aligned": aligned, "undeclared_new_verbs_after": left,
        "picked": dict(picked),
        "secs": round(time.time() - t0, 1),
    }
    pre_ok = not timed_out and summary["walks_with_removal"] >= 50 and summary["walks_with_rebirth"] >= 20
    if not pre_ok:
        j = "not_judged"
    else:
        iii = summary["cand_iii"] + summary["c_step_errors"]
        j = "support" if iii == 0 and summary["c_once_max"] == 0 and summary["c_stale_max"] == 0 \
            and summary["c_never_facts"] == 0 else "refute"
    judgment = {"h_freeze_scope_after_new_declared": j}
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_freeze_scope_after_new_declared.py", "_commit": commit,
                               "summary": summary, "judgment": judgment, "iii_examples": examples, "walks": walks},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps(judgment))


if __name__ == "__main__":
    main()
