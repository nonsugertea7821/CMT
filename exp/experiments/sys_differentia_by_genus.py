"""h_differentia_by_genus を確かめる: 同じ親を持つ兄弟の動詞の間では、自分で書いた欄が必ず違う（差異は類に相対的に一意）。

仮説（claims.yaml）: v_refer(h, v_depend([syntax.holds, syntax.from, syntax.to, syntax.mod], syntax.extends))。
  登録 #583（issue #584）。出どころ: #582（h_verb_extends_primitive、支持。収斂は類の違う 1 組だけ）と、
  最初の設計の分化の条件「兄弟では失敗し、その概念では通るテストがある」。

操作: 体系を読むだけ（写しも書き換えもしない）。動詞の集まり・自分の欄 F・書いた extends E は #582 と同じ。
  E が同じ動詞を兄弟の群にまとめ、群の中で F が同じ組（衝突）を数える。
行（sys_differentia_by_genus.json）: 衝突ごとに、E・F・動詞。
  s: n_verbs, n_sib_groups（2 つ以上の動詞を持つ兄弟の群）, n_sib_pairs（兄弟の組）,
     n_clash（F が同じ兄弟の組）, n_clash_nonempty（そのうち F が空でないもの）。

判定（事前に決める）:
  tc.build が通らなければ外れ（状態を変えない）。
  支持: n_clash = 0。
  mixed: n_clash_nonempty = 0 かつ n_clash >= 1（自分では何も書かない兄弟どうしだけが衝突）。
  反証: n_clash_nonempty >= 1。
開示: #582 で F が同じ群は 118 群中 1 つだけで、その 2 動詞は E が違った。したがって n_clash = 0 は #582 の行から
  すでに読める見込みが高い。この確かめはそれを兄弟の側から数え直して記録するもので、新しい情報は少ない。
使い方:
  python exp/experiments/sys_differentia_by_genus.py
"""
import contextlib
import io
import json
import os
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve()
KEYS = ("holds", "pre", "post")
OWN = ("holds", "pre", "post", "from", "to", "new_kind", "mod")


def canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_differentia_by_genus.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    top_o = T.top_o
    res = lambda w: w if (not isinstance(w, str) or w in N) else (T.resolve(w, "signature") or w)

    def has_any(x):
        return any(N.get(y, {}).get(k) for y in [x] + T.ancestors(x) for k in KEYS)

    verbs = sorted(x for x in N if x != top_o and T.is_a(x, top_o) and has_any(x))

    def ext(x):
        e = N[x].get("extends")
        e = e if isinstance(e, list) else [e] if e else []
        return canon(sorted(str(res(w)) for w in e))

    sib = {}
    for x in verbs:
        sib.setdefault(ext(x), []).append(x)
    rows = {}
    n_groups = n_pairs = n_clash = n_clash_nonempty = 0
    for E, xs in sorted(sib.items()):
        if len(xs) < 2:
            continue
        n_groups += 1
        for a, b in combinations(xs, 2):
            n_pairs += 1
            Fa = {k: N[a].get(k) for k in OWN}
            if canon(Fa) == canon({k: N[b].get(k) for k in OWN}):
                n_clash += 1
                nonempty = any(v is not None for v in Fa.values())
                n_clash_nonempty += nonempty
                rows[f"clash {len(rows)}"] = {"extends": json.loads(E), "own": Fa, "nonempty": nonempty, "verbs": [a, b]}
    s = {"n_verbs": len(verbs), "n_sib_groups": n_groups, "n_sib_pairs": n_pairs,
         "n_clash": n_clash, "n_clash_nonempty": n_clash_nonempty}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
