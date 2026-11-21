"""仮説 h_dependent_continuant_extends（式: v_depend(ontology.specifically_dependent_continuant, ontology.continuant)）を確かめる。
結果を見る前に、この説明と手順を登録した。

出どころ: #671。型の鎖（extends と is）では、型を持つ 5061 語のうち 4860 語が ontology.dependent で止まった。
  dependent は form: [v_depend, from] だけで定められ、extends を持たない。
問い: 「特定依存持続体は持続体である」は、(F) 体系の式がすでに含意しているのに鎖の読みが拾っていないのか、
  (E) 式に足せば矛盾なく書けるのか。二つを別々に測る。
読み F（体系を書き換えない）: 型の鎖に、form の道を足す。語 w が form の事実 (w, 動詞 v) と position の事実 (w, 端 k) を持つとき、
  動詞 v の端 k の型（関係 from か to の事実 (v, 型)）を w の親に足す。そのうえで extends と is と form の道を辿る。
読み E（書き換える）: ontology.yaml の dependent の定義に extends: continuant を足した体系を組み、法則の違反を数える。
  書き換えは実行の間だけで、終われば元に戻す（ファイルの中身を比べて確かめる）。組めなければ build_ok = 0。
測るもの:
  sdc_F / gdc_F    読み F で、specifically_ / generically_dependent_continuant の祖先に continuant があれば 1
  word_frac_L      鎖だけの読みで、型を持つ語のうち continuant か occurrent に届く割合（#671 と同じ数え方。再現の確かめ）
  word_frac_F      読み F で同じ割合
  build_ok_E       読み E で体系が組めれば 1
  viol_L / viol_E  書き換え前・後の法則の違反の数
  dviol_E          viol_E − viol_L
  word_frac_E      読み E で、鎖だけの読みの割合
判定（事前に決める）:
  支持: sdc_F = 1（式がすでに含意している）。
  反証: sdc_F = 0、かつ (build_ok_E = 0 または dviol_E > 0)（含意しておらず、足すと壊れる）。
  そのほかは mixed（含意していないが足せる）。
行（sys_dependent_continuant_extends.json）: "summary 要約"
使い方:
  python exp/experiments/sys_dependent_continuant_extends.py
"""
import collections
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_dependent_continuant_extends.json"
ONT = ROOT / "cscl/library/ontology/ontology.yaml"
OLD = "  dependent: {display: 依存するもの, form: [v_depend, from]}\n"
NEW = "  dependent: {display: 依存するもの, extends: continuant, form: [v_depend, from]}\n"


def last(x):
    return str(x).split(".")[-1]


def measure():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    os.chdir(ROOT)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            import type_checker as tc
            T, O, _ = tc.build()
            items = list(T.syntax_facts())
            viol = tc.evaluate(tc.law_rules(O), tc.Facts(items), tc.variables(O))
    except Exception as e:
        return {"build_ok": 0, "error": repr(e)[:500]}
    home = {}
    for rel, xs in items:
        if last(rel) == "domain" and isinstance(xs[0], str):
            home.setdefault(xs[0], str(xs[1]))
    chain = collections.defaultdict(set)
    form, pos, slot = {}, {}, collections.defaultdict(dict)
    for rel, xs in items:
        r = last(rel)
        if len(xs) < 2 or not all(isinstance(x, str) for x in xs[:2]):
            continue
        if r in ("extends", "is"):
            chain[xs[0]].add(xs[1])
        elif r == "form":
            form[xs[0]] = xs[1]
        elif r == "position":
            pos[xs[0]] = xs[1]
        elif r in ("from", "to"):
            slot[xs[0]][r] = xs[1]
    withform = collections.defaultdict(set, {k: set(v) for k, v in chain.items()})
    for w, v in form.items():
        t = slot.get(v, {}).get(pos.get(w))
        if t:
            withform[w].add(t)

    def anc(w, par):
        seen, stack = set(), [w]
        while stack:
            for p in par.get(stack.pop(), ()):
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    top = {w for w in home if home[w] == "ontology" and last(w) in ("continuant", "occurrent")}
    cont = "ontology.continuant"
    typed = [w for w, d in home.items() if d not in ("signature", "ontology") and chain.get(w)]

    def frac(par):
        return sum(bool(anc(w, par) & top) for w in typed) / len(typed) if typed else 0.0

    return {"build_ok": 1, "viol": len(viol), "n_typed": len(typed), "word_frac": frac(chain), "word_frac_F": frac(withform),
            "sdc_F": int(cont in anc("ontology.specifically_dependent_continuant", withform)),
            "gdc_F": int(cont in anc("ontology.generically_dependent_continuant", withform)),
            "form_parent": {w: sorted(withform[w] - chain.get(w, set())) for w in form}}


def run(variant):
    r = subprocess.run([sys.executable, __file__, "--measure"], capture_output=True, text=True, cwd=ROOT)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"build_ok": 0, "error": (r.stderr or r.stdout)[-500:]}


def main():
    if "--measure" in sys.argv:
        print(json.dumps(measure(), ensure_ascii=False))
        return
    orig = ONT.read_text(encoding="utf-8")
    assert orig.count(OLD) == 1, "dependent の行が見つからない"
    L = run("L")
    try:
        ONT.write_text(orig.replace(OLD, NEW), encoding="utf-8")
        E = run("E")
    finally:
        ONT.write_text(orig, encoding="utf-8")
    assert ONT.read_text(encoding="utf-8") == orig
    s = {"sdc_F": L.get("sdc_F", 0), "gdc_F": L.get("gdc_F", 0), "word_frac_L": L.get("word_frac", 0.0),
         "word_frac_F": L.get("word_frac_F", 0.0), "build_ok_E": E.get("build_ok", 0), "viol_L": L.get("viol", -1),
         "viol_E": E.get("viol", -1), "word_frac_E": E.get("word_frac", 0.0)}
    s["dviol_E"] = s["viol_E"] - s["viol_L"] if s["build_ok_E"] else -1
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"rev": rev, "rows": {"summary 要約": s}, "form_parent_L": L.get("form_parent"),
           "error_L": L.get("error"), "error_E": E.get("error")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
