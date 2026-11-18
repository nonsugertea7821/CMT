"""仮説 h_given_laws_as_rules（実行の記録へ述べる文は、規則で書いた法則で書ける: v_express(run_sentence, law_rule)）を確かめる。
結果を見る前に、この説明と手順と判定を登録した。

考え方: 規則で書いた法則（law_rule）は、実行の検査（runtime.py の Machine.check_laws）が、1つの状態の
「真と述べた文」（基礎の関係で書いたもの）に当てはめる。規則の前提・導く文・求める文が見られるのは、それだけ
（と、束縛と same）。だから、ある法則の確かめが、それ以外のもの（動詞の pre・post、歩みの記録、halted、
個体の種類、ほかの状態）を読むなら、その法則は、いまの規則の当てはめ方では規則で書けない。

対象（事前に決める）: runtime の5つの法則（law_given）と、それを当てはめるコードの場所。
  unique_names  type_checker.py の _match のうち、`rel == "same"` の分岐
  step          runtime.py の Machine.step のうち、「法則 step」と書いた if 文
  frame         runtime.py の Machine.step のうち、「法則 frame」と書いた for 文
  halt          runtime.py の main のうち、「法則 halt」と書いた if 文と、それが呼ぶ Machine.applicable
  no_confusion  runtime.py の Machine.confusion

手順:
  1. HEAD のコードを ast で読み、場所ごとに、使っている名前を集める（属性名、変数名、添字の文字列）。
  2. 規則から見えないものを表す目印を数える。目印（事前に決める）:
     pre, post, bind, N, up, is_a, spot_type, halted, ind, applicable, steps, run
  3. 場所ごとに、目印の数と、どの目印かを記録する。
判定（ec が通るもとで）:
  5つの法則すべてで目印が 0 なら支持（v_support）: どの法則も、規則が見るもの（1つの状態の文と束縛）だけで確かめられている。
  目印が 1 以上の法則が一つでもあれば反証（v_contradict）: その法則の確かめは、規則の当てはめ方からは見えないものを読む。

開示:
  登録の前にコードを読んで、step, frame, halt, no_confusion は動詞の pre・post や歩みの記録を読むと見ている（反証を予想する）。
  unique_names は、規則の照合（_match）そのものの中に、same の読み方として書かれている。目印が 0 でも、
  それは「規則で書いた」のではなく「規則の言語の基本の語として与えた」ものである。結果の解釈で、この区別を書く。
  登録の前に試したのは、5つの場所が見つかること（行番号）だけで、名前は数えていない。
  この判定は、いまの規則の当てはめ方（1つの状態に当てはめる）を前提にする。当てはめ方を広げる（2つの状態や歩みを
  規則に見せる）ことは、この実験では扱わない。

行（sys_given_laws_as_rules.json）:
  "law <法則>": n_markers, uses_pre, uses_post, uses_record（halted, steps, run, applicable のどれか）, uses_kinds（N, up, is_a, spot_type, ind のどれか）
  "summary 要約": n_laws, n_with_markers, n_without_markers

使い方:
  python exp/experiments/sys_given_laws_as_rules.py
"""
import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
RT = ROOT / "cscl/bootstrap/runtime/runtime.py"
TC = ROOT / "cscl/bootstrap/type_checker/type_checker.py"
MARKERS = {"pre", "post", "bind", "N", "up", "is_a", "spot_type", "halted", "ind", "applicable", "steps", "run"}
RECORD = {"halted", "steps", "run", "applicable"}
KINDS = {"N", "up", "is_a", "spot_type", "ind"}


def names(nodes):
    out = set()
    for node in nodes:
        for n in ast.walk(node):
            if isinstance(n, ast.Attribute):
                out.add(n.attr)
            elif isinstance(n, ast.Name):
                out.add(n.id)
            elif isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
                out.add(n.slice.value)
            elif isinstance(n, ast.Compare):
                out |= {c.value for c in [n.left, *n.comparators] if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return out


def func(tree, name, cls=None):
    scope = tree.body
    if cls:
        scope = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
    return next(n for n in scope if isinstance(n, ast.FunctionDef) and n.name == name)


def tagged(fn, src, kind, tag):
    lines = src.splitlines()
    return [n for n in ast.walk(fn) if isinstance(n, kind) and tag in lines[n.lineno - 1]]


def regions():
    rs, ts = RT.read_text(encoding="utf-8"), TC.read_text(encoding="utf-8")
    rt, tt = ast.parse(rs), ast.parse(ts)
    m = func(tt, "_match")
    same = [n for n in ast.walk(m) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
            and any(isinstance(c, ast.Constant) and c.value == "same" for c in n.test.comparators)]
    step = func(rt, "step", "Machine")
    return {
        "unique_names": same[:1],
        "step": tagged(step, rs, ast.If, "法則 step"),
        "frame": tagged(step, rs, ast.For, "法則 frame"),
        "halt": tagged(func(rt, "main"), rs, ast.If, "法則 halt") + [func(rt, "applicable", "Machine")],
        "no_confusion": [func(rt, "confusion", "Machine")],
    }


def main():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows, detail = {}, {}
    for law, nodes in regions().items():
        if not nodes:
            raise SystemExit(f"法則 {law} の場所が見つからないので測らない")
        used = names(nodes)
        hit = sorted(used & MARKERS)
        rows[f"law {law}"] = {"n_markers": len(hit), "uses_pre": int("pre" in used), "uses_post": int("post" in used),
                              "uses_record": int(bool(used & RECORD)), "uses_kinds": int(bool(used & KINDS))}
        detail[law] = {"markers": hit, "lines": [n.lineno for n in nodes]}
    R = [r for k, r in rows.items()]
    rows["summary 要約"] = {"n_laws": len(R), "n_with_markers": sum(r["n_markers"] > 0 for r in R),
                          "n_without_markers": sum(r["n_markers"] == 0 for r in R)}
    (OUT / "sys_given_laws_as_rules.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_given_laws_as_rules.py", "_commit": head, "rows": rows, "markers": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print(json.dumps(detail, ensure_ascii=False))
    print("判定: 反証" if rows["summary 要約"]["n_with_markers"] else "判定: 支持")


if __name__ == "__main__":
    main()
