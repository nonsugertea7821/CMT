"""h_verb_extends_primitive を確かめる: 動詞の extends は、自分で書いた欄の関数ではない。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.extends, [syntax.holds, syntax.from, syntax.to, syntax.mod], neg))。
  登録 #575（issue #576）。出どころ: #561・#565・#566・#570・#574（自分の欄からの導出の反証）。

操作: 体系を読むだけ（写しも書き換えもしない）。
  動詞の集まりは #561 と同じ（top_o の下で、holds・pre・post のどれかを祖先まで含めて持つもの）。
  各動詞 x の自分の欄 F(x) = x が自分で書いた holds・pre・post・from・to・new_kind・mod の値
  （書いていない欄は「なし」として F に入る）。
  書いた extends E(x)（解決したもの。複数ならその集合）。
  F が同じ動詞を一つの群にまとめ、群の中に E が 2 種類以上あれば、その群を「収斂」と数える。
行（sys_verb_extends_primitive.json）: 収斂した群ごとに、F の要約と、E ごとの動詞。
  s: n_verbs, n_groups, n_conv（収斂した群の数）, n_conv_nonempty（F が空でない収斂した群の数）,
     n_conv_verbs（収斂した群に入る動詞の数）。

判定（事前に決める）:
  tc.build が通らなければ外れ（状態を変えない）。
  支持: n_conv_nonempty >= 1。
  mixed: n_conv_nonempty = 0 かつ n_conv >= 1（自分では何も書かない動詞どうしだけが収斂）。
  反証: n_conv = 0。
開示: F が同じでも、祖先から継いだ中身は違いうる。この確かめは「自分の欄だけ」からの関数かを問うもので、
  継いだ中身を含めた導出（#557、支持）とは別の問い。走らせる前に数は計算していない。
使い方:
  python exp/experiments/sys_verb_extends_primitive.py
"""
import contextlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
KEYS = ("holds", "pre", "post")
OWN = ("holds", "pre", "post", "from", "to", "new_kind", "mod")


def canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_verb_extends_primitive.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    import os
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    top_o = T.top_o
    res = lambda w: w if (not isinstance(w, str) or w in N) else (T.resolve(w, "signature") or w)

    def has_any(x):
        for y in [x] + T.ancestors(x):
            if any(N.get(y, {}).get(k) for k in KEYS):
                return True
        return False

    verbs = sorted(x for x in N if x != top_o and T.is_a(x, top_o) and has_any(x))

    def ext(x):
        e = N[x].get("extends")
        e = e if isinstance(e, list) else [e] if e else []
        return canon(sorted(str(res(w)) for w in e))

    groups = {}
    for x in verbs:
        F = canon({k: N[x].get(k) for k in OWN})
        groups.setdefault(F, {}).setdefault(ext(x), []).append(x)
    rows = {}
    n_conv = n_conv_nonempty = n_conv_verbs = 0
    for F, byE in sorted(groups.items()):
        if len(byE) < 2:
            continue
        n_conv += 1
        nonempty = any(v is not None for v in json.loads(F).values())
        n_conv_nonempty += nonempty
        n_conv_verbs += sum(len(v) for v in byE.values())
        rows[f"group {len(rows)}"] = {"own": json.loads(F), "nonempty": nonempty,
                                      "by_extends": {E: xs for E, xs in sorted(byE.items())}}
    s = {"n_verbs": len(verbs), "n_groups": len(groups), "n_conv": n_conv,
         "n_conv_nonempty": n_conv_nonempty, "n_conv_verbs": n_conv_verbs}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
