"""h_identifier_free_of_declaration（#939）: 識別子は、宣言の範囲に依らないか。

仮説（claims.yaml）: v_not_depend(syntax.identifier, declared_scope)。
読み（この実験で採る形）:
  宣言の範囲は、動詞の pre・post・holds の中の exists の文で書かれる（歩みで名前が在るようになる・在らなくなる）。
  識別子が宣言の範囲に依らないなら、概念を中身で分ける分け方は、exists の文を取り去っても変わらない。
  つまり、exists の文だけで分かれている概念の組はない。

識別子の作り方: sys_identifier_bisimulation と同じ、中身による分割の細分（最大の双模倣）。
  ノードの値から display と gloss を除き、T.N のノードの名前は類の番号に置き換え、並びは並べ替えて比べる。
  この作り方は pre・post・holds を読む（中身をすべて読む）。

手（体系のファイルは変えない。tc.build() の T.N をメモリで変える）:
  木 W0: main のまま。
  木 W1: #951 のそろえ方を当てた木（new を宣言せずに使う 9 つの動詞のうち、pre が new の肯定の文を持つ 5 つは pre に、
         ほかの 4 つは post に exists(new) を足す）。
  それぞれについて、P = そのままの分割、Q = すべてのノードの pre・post・holds から is が exists の文を取り去った分割を作る。
  数える: merged = P で別の類で Q で同じ類になるノードの組の数、split = P で同じ類で Q で別の類になる組の数。

判定（事前登録）:
  支持: W0 と W1 の両方で merged = 0 かつ split = 0。
  反証: どちらかで merged > 0 か split > 0。
  前提: W0 で exists の文を持つノードが 1 つ以上ある（なければ判定しない）。

開示（結果を見る前に分かっていること）:
  - この読みは一つの読み。識別子を中身の全部から作るとき、宣言の文だけが区別を担う組がないかを見る。
  - 本命の h_identifier_by_genus_differentia は、識別子が extends・mod・holds・from・to に依るとする。
    holds に exists の文があれば、その作り方でも同じ問いが立つ。pre・post だけなら、その作り方では作り方から依らない。
  - #950（支持）と #951（採用、未マージ）の結果を見ている。W1 はその採用を写したもの。
  - 双模倣の分け方は h_identifier_by_bisimulation で反証された（予測の 4 類と一致しなかった）。ここでは衝突の数ではなく、
    exists を取り去る前後の分割の違いだけを見る。
  - 型検査は 1 回だけ（軽い）。手元で走らせるのはこの 1 回だけ。tc と ec は手元で走らせない。

出力: results/sys_identifier_free_of_declaration.json
使い方:
  python exp/experiments/sys_identifier_free_of_declaration.py
"""
import contextlib
import copy
import io
import json
import subprocess
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_identifier_free_of_declaration.json"
DROP = ("display", "gloss")
LISTS = ("pre", "post", "holds")
UNDECLARED = ("exp.v_adopt", "exp.v_deliver", "exp.v_substitute", "exp.v_withdraw",
              "ja_basic.j_go", "ja_basic.j_keep", "ja_basic.j_put", "std.v_vary", "subj.v_sell")


def partition(N):
    names = sorted(N)
    cls = {q: 0 for q in names}

    def canon(x):
        if isinstance(x, str):
            return f"<{cls[x]}>" if x in N else json.dumps(x, ensure_ascii=False)
        if isinstance(x, dict):
            return "{" + ",".join(f"{json.dumps(k)}:{canon(v)}" for k, v in sorted(x.items())) + "}"
        if isinstance(x, list):
            return "[" + ",".join(sorted(canon(v) for v in x)) + "]"
        return json.dumps(x)

    n = 1
    while True:
        keys = {q: (cls[q], canon({k: v for k, v in N[q].items() if k not in DROP})) for q in names}
        ids = {k: i for i, k in enumerate(sorted(set(keys.values())))}
        cls = {q: ids[keys[q]] for q in names}
        if len(ids) == n:
            return cls
        n = len(ids)


def is_exists(f):
    return isinstance(f, dict) and f.get("is") == "exists"


def strip(N):
    M = copy.deepcopy(N)
    for q, node in M.items():
        if not isinstance(node, dict):
            continue
        for k in LISTS:
            if isinstance(node.get(k), list):
                node[k] = [f for f in node[k] if not is_exists(f)]
    return M


def align(N):
    M = copy.deepcopy(N)
    done = {}
    for v in UNDECLARED:
        node = M[v]
        uses = any(not f.get("neg") and f.get("is") != "exists" and "new" in (f.get("from"), f.get("to"))
                   for f in node.get("pre", []))
        if uses:
            node["pre"] = list(node["pre"]) + [{"is": "exists", "from": "new"}]
            done[v] = "pre"
        else:
            node["post"] = list(node["post"]) + [{"is": "exists", "from": "new"}]
            done[v] = "post"
    return M, done


def compare(N):
    P, Q = partition(N), partition(strip(N))
    groups = {}
    for q in N:
        groups.setdefault(Q[q], []).append(q)
    merged, split = [], []
    for g in groups.values():
        for a, b in combinations(sorted(g), 2):
            if P[a] != P[b]:
                merged.append([a, b])
    pg = {}
    for q in N:
        pg.setdefault(P[q], []).append(q)
    for g in pg.values():
        for a, b in combinations(sorted(g), 2):
            if Q[a] != Q[b]:
                split.append([a, b])
    with_exists = sorted(q for q, node in N.items() if isinstance(node, dict)
                         and any(is_exists(f) for k in LISTS for f in (node.get(k) or []) if isinstance(node.get(k), list)))
    return {"n_nodes": len(N), "n_classes_P": len(set(P.values())), "n_classes_Q": len(set(Q.values())),
            "n_with_exists": len(with_exists), "n_merged": len(merged), "n_split": len(split),
            "merged": merged[:200], "split": split[:200], "with_exists": with_exists}


def main():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    base_errors = len(tc.errors)
    N0 = T.N
    N1, aligned = align(N0)
    r0, r1 = compare(N0), compare(N1)
    summary = {"base_errors": base_errors, "aligned": aligned,
               **{f"W0_{k}": v for k, v in r0.items() if k.startswith("n_")},
               **{f"W1_{k}": v for k, v in r1.items() if k.startswith("n_")}}
    if r0["n_with_exists"] == 0:
        j = "not_judged"
    elif r0["n_merged"] == r0["n_split"] == r1["n_merged"] == r1["n_split"] == 0:
        j = "support"
    else:
        j = "refute"
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_identifier_free_of_declaration.py", "_commit": rev,
                               "summary": summary, "judgment": {"h_identifier_free_of_declaration": j},
                               "W0": r0, "W1": r1}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print("W0 merged", r0["merged"][:20])
    print("W1 merged", r1["merged"][:20])
    print(json.dumps({"h_identifier_free_of_declaration": j}))


if __name__ == "__main__":
    main()
