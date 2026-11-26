"""sys_declaration_follows_freeze.py の歩ませ方を直して、確かめ直す（h_dangling_by_append_only_declaration、#938）。
あわせて h_dangling_by_undeclared_new（宣言されていない名前の文は、new を宣言せずに使う動詞からも出る）を確かめる。

前の版（判定しない）で分かったこと（結果を読んでいる）:
  - 宣言を取り消す歩みを含む本が 200 本のうち 10 で、前提の 50 に届かなかった。
  - 手を選ぶとき歩んだ後の法則を見ていなかったので、(b) でも (c) でも法則 part_antisymmetric の違反が出た。
  - 古い文の数え方が、宣言されないまま使われた名前を「生まれ直し」と数えた。
  - (c) でも宣言されていない名前の文が出た。exp.v_adopt と exp.v_deliver は new の文を足すが exists(new) を述べない。

手（前の版と同じ）: (b) sys_declaration.Declared、(c) (b) に「宣言を取り消した名前の文を同じ歩みで取り消す」を足したもの。
  実装は sys_declaration_follows_freeze の B と C をそのまま使う。

直したところ:
  1. 手の並べ方は前の版の moves と同じ。そのうち (b) の写しで歩ませてエラーが増えないもの（pre と法則が破れないもの）だけを候補にする。
  2. 選び方: 候補を「宣言を取り消す手」（post で exists(new) を偽にする）「生まれ直す手」（new が、前に宣言され、取り消された名前）
     「ほか」に分け、乱数で 1/3 ずつ組を選び、空でない組から一様に選ぶ（空なら、空でない組から選び直す）。
  3. 古い文は、宣言を取り消されたことのある名前について、最後に生まれ直す前に述べられ、生まれ直してから述べ直されていない文だけを数える。
  4. 宣言されていない名前の文を、その名前が「一度でも宣言されたか」で分けて数える。
     一度も宣言されていない名前の文は、どの歩みが足したかを覚え、その動詞の post が「new を端に持つ exists 以外の文を述べ、exists(new) を述べない」か
     （以下「宣言せずに new を使う動詞」）を、定義から調べる。
  材料: 最初の状態は前の版と同じ（sys1 と dec1 が在る）。乱数の種 1、長さ 8、300 本。
  選んだ手を (b) と (c) の両方で歩ませる。(c) のエラーは、pre の破れのうち、成り立たない文の端に (c) で宣言されていない名前があるもの
  （宣言されていない名前についての手。(c) では文が消えているので破れて当然）と、それ以外に分けて数える。

判定（事前登録）:
  前提: 宣言を取り消す歩みを含む本が 50 以上、取り消した名前が生まれ直す歩みを含む本が 20 以上。満たさなければ両方とも判定しない。
        2 時間で終わらなければ止め、判定しない。
  h_dangling_by_append_only_declaration:
    支持: (c) の「それ以外の」エラーが 0、(c) で一度宣言された名前の宣言されていない文が、どの歩みの後も 0、(c) の古い文が、どの歩みの後も 0。
    反証: どれかが破れる。
  h_dangling_by_undeclared_new:
    支持: (c) の宣言されていない名前の文が 1 つ以上あり、その文を足した歩みの動詞が、すべて「宣言せずに new を使う動詞」。
    反証: (c) の宣言されていない名前の文が 1 つもない、またはそれを足した歩みに、そうでない動詞がある。
  参考（判定に使わない）: (b) の、一度宣言された名前の宣言されていない文の数と古い文の数、(c) の「宣言されていない名前についての手」のエラーの数、
    宣言せずに new を使う動詞の一覧、組ごとの選ばれた数。

開示:
  - 前の版の結果を読んで直した（上の 4 点）。直したことは訂正として開示する。
  - (c) の「一度宣言された名前の宣言されていない文が 0」は、作り方からほぼ決まる。中身があるのは、取り消しの後の歩みが破れないか（エラー）と、
    生まれ直しで古い文が残らないか。手は (b) で破れないものから選ぶので、(b) のエラーは作り方から 0 になる。
  - 手元で走らせるのはこの 1 回だけ。tc と ec は手元で走らせない。

出力: results/sys_declaration_follows_freeze_v2.json
使い方:
  python exp/experiments/sys_declaration_follows_freeze_v2.py
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
    import sys_declaration_follows_freeze as v1  # noqa: E402
rt, tc = v1.rt, v1.tc

OUT = ROOT / "exp/experiments/results/sys_declaration_follows_freeze_v2.json"
N_WALKS, LENGTH, SEED = 300, 8, 1


def snapshot(m):
    return (dict(m.facts), set(m.declared), dict(m.ind), list(m.errors), m.t, dict(m.said), dict(m.born))


def restore(m, s):
    m.facts, m.declared, m.ind, m.errors, m.t, m.said, m.born = dict(s[0]), set(s[1]), dict(s[2]), list(s[3]), s[4], dict(s[5]), dict(s[6])


def ok_in(m, verb, bind):
    s = snapshot(m)
    n = len(m.errors)
    try:
        m.step(verb, bind, "try")
        return len(m.errors) == n
    finally:
        restore(m, s)


def undeclared_new_verbs(T):
    out = set()
    for vid, node in T.N.items():
        if "pre" not in node:
            continue
        post = [rt.atom(f) for f in node.get("post", [])]
        other = any(rel != "exists" and "new" in args for _, rel, args in post)
        declares = any(rel == "exists" and args == ("new",) for _, rel, args in post) or \
            any(rel == "exists" and list(args) == ["new"] for _, rel, args in post)
        if other and not declares:
            out.add(vid)
    return out


def removes(T, vid):
    node = T.N.get(vid, {})
    for f in node.get("post", []):
        neg, rel, args = rt.atom(f)
        if rel == "exists" and "new" in args and (neg or f.get("neg")):
            return True
    return False


class Hist:
    def __init__(self):
        self.ever = set()
        self.removed = set()
        self.last_birth = {}
        self.added_by = {}


def note(m, h, verb, d0, f0):
    h.ever |= m.declared
    h.removed |= d0 - m.declared
    for x in m.declared - d0:
        h.last_birth[x] = m.t
    for k in m.facts:
        if k not in f0:
            h.added_by[k] = verb


def counts(m, h):
    dang = [k for k in m.facts if any(a not in m.declared for a in k[1])]
    once = [k for k in dang if all(a in h.ever or a in m.declared for a in k[1] if a not in m.declared)]
    never = [k for k in dang if k not in once]
    stale = sum(1 for k, t in m.said.items()
                if any(a in h.removed and a in h.last_birth and t < h.last_birth[a] for a in k[1]))
    return once, never, stale


def main():
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    unv = undeclared_new_verbs(T)
    rng = random.Random(SEED)
    walks, timed_out, picked = [], False, Counter()
    for w in range(N_WALKS):
        b, c = v1.B(T, v1.START, "b"), v1.C(T, v1.START, "c")
        hb, hc = Hist(), Hist()
        hb.ever |= b.declared
        hc.ever |= c.declared
        rec = {"steps": [], "c_other_errors": 0, "c_undeclared_errors": 0, "b_errors": 0, "removed": 0, "reborn": 0,
               "c_once_max": 0, "b_once_max": 0, "c_stale_max": 0, "b_stale_max": 0, "c_never": [], "c_error_texts": []}
        k = 0
        for i in range(LENGTH):
            if time.time() > t0 + 7200:
                timed_out = True
                break
            fresh = f"n{k}"
            ms = [mv for mv in v1.moves(b, fresh) if ok_in(b, *mv)]
            if not ms:
                break
            groups = {"remove": [mv for mv in ms if removes(T, mv[0])],
                      "reborn": [mv for mv in ms if mv[1].get("new") in hb.removed and mv[1].get("new") not in b.declared],
                      }
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
                    if key == "b":
                        rec["b_errors"] += 1
                    else:
                        r, _ = m.bind(verb, bind)
                        bad = [f for f in (r or {}).get("pre", []) if not m.holds(*f)]
                        undecl = r is not None and bad and all(any(a not in m.declared for a in f[2]) for f in bad)
                        rec["c_undeclared_errors" if undecl else "c_other_errors"] += 1
                        rec["c_error_texts"] += m.errors[ne:ne + 2]
                note(m, h, verb, d0, f0)
            rec["removed"] += int(removes(T, verb))
            rec["steps"].append([verb, bind])
            for m, h, key in ((b, hb, "b"), (c, hc, "c")):
                once, never, stale = counts(m, h)
                rec[f"{key}_once_max"] = max(rec[f"{key}_once_max"], len(once))
                rec[f"{key}_stale_max"] = max(rec[f"{key}_stale_max"], stale)
                if key == "c":
                    for kk in never:
                        item = [f"{kk[0]}{kk[1]}", hc.added_by.get(kk)]
                        if item not in rec["c_never"]:
                            rec["c_never"].append(item)
        rec["c_error_texts"] = rec["c_error_texts"][:5]
        walks.append(rec)
        print("W", w, len(rec["steps"]), rec["removed"], rec["reborn"], rec["c_other_errors"], rec["c_once_max"],
              rec["c_stale_max"], len(rec["c_never"]), flush=True)
        if timed_out:
            break
    never_all = [x for w in walks for x in w["c_never"]]
    never_verbs = Counter(v for _, v in never_all)
    summary = {
        "walks": len(walks), "timed_out": timed_out,
        "walks_with_removal": sum(1 for w in walks if w["removed"]),
        "walks_with_rebirth": sum(1 for w in walks if w["reborn"]),
        "c_other_errors": sum(w["c_other_errors"] for w in walks),
        "c_undeclared_errors": sum(w["c_undeclared_errors"] for w in walks),
        "b_errors": sum(w["b_errors"] for w in walks),
        "c_once_max": max((w["c_once_max"] for w in walks), default=0),
        "b_once_walks": sum(1 for w in walks if w["b_once_max"]),
        "c_stale_max": max((w["c_stale_max"] for w in walks), default=0),
        "b_stale_walks": sum(1 for w in walks if w["b_stale_max"]),
        "c_never_facts": len(never_all),
        "c_never_by_undeclared_verb": sum(n for v, n in never_verbs.items() if v in unv),
        "c_never_by_other_verb": sum(n for v, n in never_verbs.items() if v not in unv),
        "never_verbs": dict(never_verbs.most_common()),
        "undeclared_new_verbs": sorted(unv),
        "picked": dict(picked),
        "secs": round(time.time() - t0, 1),
    }
    pre_ok = not timed_out and summary["walks_with_removal"] >= 50 and summary["walks_with_rebirth"] >= 20
    if not pre_ok:
        j1 = j2 = "not_judged"
    else:
        j1 = "support" if summary["c_other_errors"] == 0 and summary["c_once_max"] == 0 and summary["c_stale_max"] == 0 else "refute"
        j2 = "support" if summary["c_never_facts"] > 0 and summary["c_never_by_other_verb"] == 0 else "refute"
    judgment = {"h_dangling_by_append_only_declaration": j1, "h_dangling_by_undeclared_new": j2}
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_declaration_follows_freeze_v2.py", "_commit": commit,
                               "summary": summary, "judgment": judgment, "walks": walks},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps(judgment))


if __name__ == "__main__":
    main()
