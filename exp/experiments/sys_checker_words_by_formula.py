"""h_checker_words_by_formula を確かめる: 型検査器が名前で読む role・definition・v_refer の区別は、extends と mod（と holds）の式から読めるか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.extends, syntax.mod])。
  登録（af54d18）の読み: #298（3語を文法の節に置く道）の反証から、もう一方の道として、式で区別する側を仮説にした。

操作: 体系のファイルも検査器も変えない。いまのリポジトリで type_checker.build() を呼び、木と節点を読むだけ（静的）。
語 W ごとに、二つの集合を比べる。
  S_name(W): 検査器が名前でたどる集合 = {x : is_a(x, W)}（extends の子孫。W 自身を含む）。
  S_form(W): W の定義の式を満たす節点の集合。式は W の節点から読む:
    属 G = W の extends。
    W が mod を持つとき: x が is_a(x, G) で、x か x の上位の mod に、W の mod と of が同じで、with が W の mod の with の下にある
      ものがある（名前を付けた mod は、その節点の of と with で読む。W の mod に with がなければ of だけ比べる）。
    W が holds を持つとき（動詞）: x が is_a(x, G) で、x か x の上位の holds に、W の holds の基礎の関係（is）がすべてある。
  数える: n_name = |S_name|、n_form = |S_form|、missing = |S_name − S_form|、extra = |S_form − S_name|、
    行に extra と missing の名（先頭 10）を残す。
仮説からの見込み（事前に決める）: 3語とも missing = 0、extra = 0。
判定（事前に決める）:
  build が失敗すれば、手順が壊れているので外れとし、状態を変えない。
  3語とも一致（missing = extra = 0）なら支持。
  一致が 1 語か 2 語なら mixed。
  一致が 0 語なら反証。
開示（結果を見る前に分かっていること）:
  - missing は、mod や holds が下位に引き継がれるので、0 になりやすい。効くのは extra（式を満たすが W の下に置かれていない節点）。
  - role の mod の with は definition で、S_form(role) は definition を名前の is_a で読む。W 自身の式を読むのは許すとする。
  - 名前を付けた mod（definition の refer_from_concept など）の解き方は、検査器の resolve に任せる。
行（sys_checker_words_by_formula.json）: "word <W>": {...}, "summary 要約": {...}
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_checker_words_by_formula.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
WORDS = ["role", "definition", "v_refer"]


def main():
    import os
    os.chdir(ROOT)
    rows = {}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            import type_checker as tc
            T, O, Dm = tc.build()
    except Exception as e:
        rows["summary 要約"] = {"build_ok": 0, "error": str(e)[:300]}
        OUT.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(rows)
        return
    N = T.N
    res = lambda w: w if (not isinstance(w, str) or w in N) else (T.resolve(w, "signature") or w)

    def mods(x):
        out = []
        for y in [x] + T.ancestors(x):
            ms = N[y].get("mod") or []
            for m in (ms if isinstance(ms, list) else [ms]):
                if isinstance(m, str):
                    m = N.get(res(m), {})
                if isinstance(m, dict) and "of" in m:
                    out.append({"of": [res(m["of"][0]), m["of"][1]], "with": res(m.get("with")) if m.get("with") else None,
                                "neg": bool(m.get("neg"))})
        return out

    def holds(x):
        return {h.get("is") for y in [x] + T.ancestors(x) for h in (N[y].get("holds") or []) if isinstance(h, dict)}

    n_match = 0
    for w in WORDS:
        W = res(w)
        G = N[W].get("extends")
        G = res(G) if isinstance(G, str) else None
        wm = None
        ms = N[W].get("mod")
        if ms:
            ms = ms if isinstance(ms, list) else [ms]
            m = ms[0]
            if isinstance(m, str):
                m = N.get(res(m), {})
            wm = {"of": [res(m["of"][0]), m["of"][1]], "with": res(m.get("with")) if m.get("with") else None, "neg": bool(m.get("neg"))}
        wh = {h.get("is") for h in (N[W].get("holds") or []) if isinstance(h, dict)}
        s_name = {x for x in N if T.is_a(x, W)}
        s_form = set()
        for x in N:
            if not (G and T.is_a(x, G)):
                continue
            ok = True
            if wm:
                ok = any(m["of"] == wm["of"] and m["neg"] == wm["neg"] and (wm["with"] is None or (m["with"] and T.is_a(m["with"], wm["with"])))
                         for m in mods(x))
            if wh:
                ok = ok and wh <= holds(x)
            if not wm and not wh:
                ok = False
            if ok:
                s_form.add(x)
        missing, extra = sorted(s_name - s_form), sorted(s_form - s_name)
        r = {"node": W, "genus": G, "mod": wm, "holds": sorted(wh), "n_name": len(s_name), "n_form": len(s_form),
             "missing": len(missing), "extra": len(extra), "missing_names": missing[:10], "extra_names": extra[:10]}
        rows[f"word {w}"] = r
        n_match += 1 if not missing and not extra else 0
        print(w, json.dumps(r, ensure_ascii=False))
    s = {"build_ok": 1, "n_word": len(WORDS), "n_match": n_match,
         "verdict_support": 1 if n_match == len(WORDS) else 0, "verdict_refute": 1 if n_match == 0 else 0}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
