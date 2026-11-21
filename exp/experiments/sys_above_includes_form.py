"""仮説の対 h_above_includes_form（式: v_refer(syntax.form, ontology.v_above)）と
h_above_split_written_derived（式: v_refer(syntax.form, ontology.v_above, neg)）を確かめる。
結果を見る前に、この説明と手順を登録した。

出どころ: #678。form で定めた 29 語の上位（端の型）は r_kind_up にあり（cover 1.0）、above にはない（cover 0）。
  上位を表す関係が二つに分かれている。対の仮説はこの分かれを、includes は「一つにすべき」、split は「分かれているのが正しい」と読む。
問い: above に form からの上位を含めると、above について書かれた法則と食い違うか。
読み L（体系を書き換えない）: 法則を評価し、違反を数える。
読み I（書き換える）: syntax.yaml に法則 above_by_kind_up を足す。r_kind_up(var1, var2) から above(var1, var2) を導く
  （above_by_ancestor と同じ形）。ほかの法則は変えない。書き換えは実行の間だけで、終われば元に戻す（中身を比べて確かめる）。
  組めなければ build_ok_I = 0。
測るもの:
  viol_L / viol_I   書き換え前・後の法則の違反の数
  dviol_I           viol_I − viol_L
  viol_by_law_I     読み I の違反を法則ごとに数えたもの（記述）
  cover_above_L / cover_above_I  #678 と同じ対象（form の端の型が any でない語）で、above の推移閉包が端の型に届く割合
判定（事前に決める。一つの測りで対の両方を決める）:
  build_ok_I = 1 かつ dviol_I = 0: h_above_includes_form を支持、h_above_split_written_derived を反証。
  build_ok_I = 0 または dviol_I > 0: h_above_includes_form を反証、h_above_split_written_derived を支持。
限り（事前に開示）: 読み I は「導く規則を一つ足し、ほかの法則は変えない」一つの書き方だけを試す。
  above の法則（above_is_ancestor など）も合わせて書き換える含め方は、この実験では問わない。
行（sys_above_includes_form.json）: "summary 要約"
使い方:
  python exp/experiments/sys_above_includes_form.py
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
OUT = ROOT / "exp/experiments/results/sys_above_includes_form.json"
SYN = ROOT / "cscl/library/syntax/syntax.yaml"
IND_OLD = "  above_by_ancestor: {is: law_rule, display: 祖先は上位である}\n"
IND_NEW = IND_OLD + "  above_by_kind_up: {is: law_rule, display: 種類として上は上位である}\n"
RUL_OLD = "  - {is: v_derive, from: above_by_ancestor, to: {is: above, from: var1, to: var2}}\n"
RUL_NEW = RUL_OLD + ("  - {is: v_assume, from: above_by_kind_up, to: {is: r_kind_up, from: var1, to: var2}}\n"
                     "  - {is: v_derive, from: above_by_kind_up, to: {is: above, from: var1, to: var2}}\n")


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
            F = tc.Facts(items)
            viol = tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    except Exception as e:
        return {"build_ok": 0, "error": repr(e)[:500]}
    form, pos, slot = {}, {}, collections.defaultdict(dict)
    for rel, xs in items:
        r = last(rel)
        if len(xs) < 2 or not all(isinstance(x, str) for x in xs[:2]):
            continue
        if r == "form":
            form[xs[0]] = xs[1]
        elif r == "position":
            pos[xs[0]] = xs[1]
        elif r in ("from", "to"):
            slot[xs[0]][r] = xs[1]
    targets = {}
    for w, v in form.items():
        t = slot.get(v, {}).get(pos.get(w))
        if t and t != "any":
            targets[w] = t
    e = collections.defaultdict(set)
    for xs in F.by.get("above", ()):
        xs = tuple(xs)
        if len(xs) >= 2 and isinstance(xs[0], str) and isinstance(xs[1], str):
            e[xs[0]].add(xs[1])

    def reach(a, b):
        seen, stack = {a}, [a]
        while stack:
            for y in e.get(stack.pop(), ()):
                if y == b:
                    return True
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return False

    by_law = collections.Counter(str(v[0]) for v in viol)
    examples = collections.defaultdict(list)
    for v in viol:
        if len(examples[str(v[0])]) < 5:
            examples[str(v[0])].append(repr(v[1])[:300])
    return {"build_ok": 1, "viol": len(viol), "n_target": len(targets),
            "cover_above": sum(reach(w, t) for w, t in targets.items()) / len(targets) if targets else 0.0,
            "n_pairs_above": sum(len(v) for v in e.values()),
            "viol_by_law": dict(by_law), "examples": dict(examples)}


def run():
    r = subprocess.run([sys.executable, __file__, "--measure"], capture_output=True, text=True, cwd=ROOT)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"build_ok": 0, "error": (r.stderr or r.stdout)[-500:]}


def main():
    if "--measure" in sys.argv:
        print(json.dumps(measure(), ensure_ascii=False))
        return
    orig = SYN.read_text(encoding="utf-8")
    assert orig.count(IND_OLD) == 1 and orig.count(RUL_OLD) == 1, "above_by_ancestor の行が見つからない"
    L = run()
    try:
        SYN.write_text(orig.replace(IND_OLD, IND_NEW).replace(RUL_OLD, RUL_NEW), encoding="utf-8")
        I = run()
    finally:
        SYN.write_text(orig, encoding="utf-8")
    assert SYN.read_text(encoding="utf-8") == orig
    s = {"build_ok_I": I.get("build_ok", 0), "viol_L": L.get("viol", -1), "viol_I": I.get("viol", -1),
         "cover_above_L": L.get("cover_above", 0.0), "cover_above_I": I.get("cover_above", 0.0),
         "n_pairs_above_L": L.get("n_pairs_above", 0), "n_pairs_above_I": I.get("n_pairs_above", 0)}
    s["dviol_I"] = s["viol_I"] - s["viol_L"] if s["build_ok_I"] else -1
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"rev": rev, "rows": {"summary 要約": s}, "viol_by_law_L": L.get("viol_by_law"), "viol_by_law_I": I.get("viol_by_law"),
           "examples_I": I.get("examples"), "error_L": L.get("error"), "error_I": I.get("error")}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
