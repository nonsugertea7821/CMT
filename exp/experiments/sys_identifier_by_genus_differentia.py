"""h_identifier_by_genus_differentia: 識別子は、類と種差（extends・mod・holds・from・to）だけで決まるか。

仮説（claims.yaml）: v_depend(syntax.identifier, [syntax.extends, syntax.mod, syntax.holds, syntax.from, syntax.to])。
読み（この実験で採る形）:
  概念を中身で分けた分け方が、類と種差の鍵だけを読んでも、中身の全部を読んだときと同じなら、識別子は類と種差で決まる。
  逆に、類と種差だけでは同じになり、ほかの鍵（pre・post・form・axis など）でだけ分かれる組があれば、識別子はそれにも依る。

識別子の作り方: sys_identifier_bisimulation と同じ、中身による分割の細分（最大の双模倣）。
  T.N のノードの名前は類の番号に置き換え、並びは並べ替えて比べる。
  P（全部）: ノードの値から display と gloss を除いたもの。
  G（類と種差）: ノードの値のうち extends・mod・holds・from・to と、名前を付けた限定の中身 of・with だけ。
    of・with は、名前を付けた限定のノードで mod の中身を直に持つ鍵なので、mod の一部として読む。

数える: merged = P で別の類で G で同じ類になるノードの組。split = P で同じ類で G で別の類になる組（作り方から 0 の見込み）。
  merged の組ごとに、P で違いを生んだ鍵（二つのノードで値が違う、G に入らない鍵）を記録する。

判定（事前登録）:
  支持: merged = 0（かつ split = 0）。
  反証: merged > 0 か split > 0。

開示（結果を見る前に分かっていること）:
  - T.N の鍵の種類と数を数えた（795 ノード。display 795、extends 759、mod 556、to 117、from 112、of 72、with 54、holds 38、
    form 33、pre 23、post 23、axis 22、many 20、new_kind 18、verbatim 13、neg 8、cmp 5、val 4、opposite 4、derive 2、via 2、
    ranges 1、always 1、sometime 1）。どのノードがどの鍵で分かれるかは見ていない。
  - P は sys_identifier_free_of_declaration（#952）の W0 の P と同じ作り方で、類は 793（795 ノード）だった。
  - 動的な動詞（pre・post を持つ 23）は、from・to・extends が同じで pre・post だけが違う組があれば merged に出る。
    そういう組があるかは確かめていない。
  - of・with を G に入れたのは読みの選択。
  - 型検査は 1 回だけ（軽い）。手元で走らせるのはこの 1 回だけ。tc と ec は手元で走らせない。

出力: results/sys_identifier_by_genus_differentia.json
使い方:
  python exp/experiments/sys_identifier_by_genus_differentia.py
"""
import contextlib
import io
import json
import subprocess
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_identifier_by_genus_differentia.json"
DROP = ("display", "gloss")
KEEP = ("extends", "mod", "holds", "from", "to", "of", "with")


def partition(N, pick):
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
        keys = {q: (cls[q], canon(pick(N[q]))) for q in names}
        ids = {k: i for i, k in enumerate(sorted(set(keys.values())))}
        cls = {q: ids[keys[q]] for q in names}
        if len(ids) == n:
            return cls
        n = len(ids)


def full(node):
    return {k: v for k, v in node.items() if k not in DROP} if isinstance(node, dict) else node


def gd(node):
    return {k: v for k, v in node.items() if k in KEEP} if isinstance(node, dict) else node


def main():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    base_errors = len(tc.errors)
    N = T.N
    P, G = partition(N, full), partition(N, gd)
    byG, byP = {}, {}
    for q in N:
        byG.setdefault(G[q], []).append(q)
        byP.setdefault(P[q], []).append(q)
    merged, split = [], []
    for g in byG.values():
        for a, b in combinations(sorted(g), 2):
            if P[a] != P[b]:
                na, nb = N[a] if isinstance(N[a], dict) else {}, N[b] if isinstance(N[b], dict) else {}
                diff = sorted(k for k in set(na) | set(nb) if k not in DROP and k not in KEEP and na.get(k) != nb.get(k))
                merged.append({"pair": [a, b], "keys": diff})
    for g in byP.values():
        for a, b in combinations(sorted(g), 2):
            if G[a] != G[b]:
                split.append([a, b])
    key_count = {}
    for m in merged:
        for k in m["keys"]:
            key_count[k] = key_count.get(k, 0) + 1
    merged_nodes = sorted({q for m in merged for q in m["pair"]})
    summary = {"base_errors": base_errors, "n_nodes": len(N), "n_classes_P": len(byP), "n_classes_G": len(byG),
               "n_merged": len(merged), "n_split": len(split), "n_merged_nodes": len(merged_nodes),
               "merged_by_key": dict(sorted(key_count.items(), key=lambda x: -x[1]))}
    j = "support" if not merged and not split else "refute"
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_identifier_by_genus_differentia.py", "_commit": rev,
                               "summary": summary, "judgment": {"h_identifier_by_genus_differentia": j},
                               "merged": merged, "split": split}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    for m in merged[:40]:
        print(m)
    print(json.dumps({"h_identifier_by_genus_differentia": j}))


if __name__ == "__main__":
    main()
