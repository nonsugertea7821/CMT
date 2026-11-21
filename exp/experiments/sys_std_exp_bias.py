"""h_std_exp_biased を確かめる: std の語の多くは、exp が使うために置かれた。

仮説（exp.yaml）: v_refer(h, v_depend(std, exp))。登録 #593。わき道。
残り項目: b_std_exp_biased（偏りの量）、b_std_residue（exp に移したあと std に残るもの）。

操作: 体系のファイルを読むだけ（写しも書き換えもしない）。
  読むファイルは cscl.yaml の library と include（各ファイルの domain: がその領域）。
  std の項目 = std.yaml のノードと個体（領域の個体 std そのものは除く）と、facts の各行。
  参照: 各ファイルの項目（ノード・個体・facts の行）の値に現れる文字列 s を、
    s が "std.x" なら x、std の中なら素の x、ほかの領域では素の x が std にだけあるとき（tc の resolve が std.x を返すか、
    個体なら std のほかに同じ名前がない）x への参照とする。項目自身の名前は数えない。
  使い手: std の項目 e を参照する項目の集まり。std の外の使い手は領域で、std の中の使い手は項目で持つ。
  移す集まり M（不動点まで繰り返す）:
    (1) e の使い手が一つ以上あり、どれも exp の項目か M の項目なら、e は M に入る（exp のためだけにある）。
    (2) e が M の項目を参照するなら、e は M に入る（std は exp を使えない）。
  残り R = std の項目 − M。R のうち使い手のないものは「誰も使わない」と分けて数える。
行（sys_std_exp_bias.json）: 項目ごとに、種類（node / individual / fact）、M か R か、入った理由、std の外の使い手の領域、
  std の中の使い手の数。
  s: n_node, n_node_move, share_node_move, n_ind, n_ind_move, n_fact, n_fact_move,
     n_node_stay_other（exp 以外の領域が使うので残るノード）, n_node_unused（使い手のないノード）。

判定（事前に決める）:
  ファイルが読めなければ外れ（状態を変えない）。
  b_std_exp_biased: share_node_move >= 0.5 なら支持、< 0.5 なら反証。
  b_std_residue: R のノードと個体を並べる（記述だけで、判定には使わない）。
開示: 主張（仮説の式、観察）の中の参照も使い手に数える。lang の主張が std の語を述べれば、それで std に残る。
  走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_std_exp_bias.py
"""
import contextlib
import glob
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_std_exp_bias.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    import os
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    cfg = tc.yload(open(root / "cscl.yaml"))
    files = []
    for pat in list(cfg.get("library") or []) + list(cfg.get("include") or []):
        files += sorted(glob.glob(str(root / pat)))
    docs = []
    for f in files:
        y = tc.yload(open(f)) or {}
        if isinstance(y, dict) and y.get("domain"):
            docs.append((y["domain"], Path(f).relative_to(root).as_posix(), y))
    std = [y for d, _, y in docs if d == "std"]
    assert len(std) == 1, "std のファイルが一つでない"
    S = std[0]
    kind = {}
    for k in S.get("nodes") or {}:
        kind[k] = "node"
    for k in S.get("individuals") or {}:
        if k != "std":
            kind[k] = "individual"
    other_ind = set()
    for d, _, y in docs:
        if d != "std":
            other_ind |= set((y.get("individuals") or {}).keys()) | set((y.get("nodes") or {}).keys())
    facts = S.get("facts") or []
    for i in range(len(facts)):
        kind[f"fact{i}"] = "fact"

    def ref(s, d):
        if s.startswith("std."):
            x = s[4:]
            return x if x in kind else None
        if s not in kind or kind[s] == "fact":
            return None
        if d == "std":
            return s
        if kind[s] == "node":
            return s if T.resolve(s, d) == f"std.{s}" else None
        return s if s not in other_ind else None

    refs = {}
    users_ext = {e: set() for e in kind}
    users_in = {e: set() for e in kind}
    for d, name, y in docs:
        items = [(k, v) for k, v in (y.get("nodes") or {}).items()]
        items += [(k, v) for k, v in (y.get("individuals") or {}).items()]
        items += [(f"fact{i}", v) for i, v in enumerate(y.get("facts") or [])]
        for k, v in items:
            me = k if d == "std" and k in kind else None
            for s in strings(v):
                e = ref(s, d)
                if e is None or e == me:
                    continue
                if d == "std" and me is not None:
                    refs.setdefault(me, set()).add(e)
                    users_in[e].add(me)
                elif d == "std":
                    continue
                else:
                    users_ext[e].add(d)
    M, why = set(), {}
    changed = True
    while changed:
        changed = False
        for e in kind:
            if e in M:
                continue
            ext_ok = users_ext[e] <= {"exp"}
            in_ok = users_in[e] <= M
            if (users_ext[e] or users_in[e]) and ext_ok and in_ok:
                M.add(e); why[e] = "used_only_by_exp_or_moved"; changed = True
            elif refs.get(e, set()) & M:
                M.add(e); why[e] = "refers_to_moved"; changed = True
    rows = {}
    for e in kind:
        if e in M:
            st = "move"
        elif users_ext[e] - {"exp"}:
            st = "stay_other"
        elif not users_ext[e] and not users_in[e]:
            st = "stay_unused"
        else:
            st = "stay"
        rows[e] = {"kind": kind[e], "status": st, "why": why.get(e),
                   "ext_domains": sorted(users_ext[e]), "n_std_users": len(users_in[e])}
    cnt = lambda kd, cond: sum(1 for r in rows.values() if r["kind"] == kd and cond(r))
    n_node = cnt("node", lambda r: True)
    n_node_move = cnt("node", lambda r: r["status"] == "move")
    s = {"n_node": n_node, "n_node_move": n_node_move, "share_node_move": n_node_move / n_node,
         "n_ind": cnt("individual", lambda r: True), "n_ind_move": cnt("individual", lambda r: r["status"] == "move"),
         "n_fact": cnt("fact", lambda r: True), "n_fact_move": cnt("fact", lambda r: r["status"] == "move"),
         "n_node_stay_other": cnt("node", lambda r: r["status"] == "stay_other"),
         "n_node_unused": cnt("node", lambda r: r["status"] == "stay_unused")}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
