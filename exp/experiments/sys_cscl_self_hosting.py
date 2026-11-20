"""仮説 h_cscl_self_hosting（型検査器は cscl で書ける: v_express(type_checker, cscl)）を、今の形で確かめる。
検査器が誤りを出す箇所が、cscl に書いた法則でどこまで表されているかを数える。結果を見る前に、この説明と手順を登録した。

範囲: cscl/bootstrap/type_checker/type_checker.py の中で err(...) を呼ぶ箇所（静的に、ast で数える）。
  実行の検査（cscl/bootstrap/runtime/runtime.py、LAWS_RUN）と ec（exp/src/exp_check.py）は対象にしない。
  検査器を実行しない。体系のファイルも書き換えない。
単位: err の呼び出し 1 つ。それを囲む一番内側の関数で分ける（メソッドは関数として数える）。
分け方（事前に決める）:
  rule   囲む関数が check_laws（規則で書いた法則 law_rule を当てはめて出す箇所）
  given  囲む関数が GIVEN_FUNCS のどれか（意味を Python が与える法則 law_given の検査）
         GIVEN_FUNCS = check_world_declared, presumed_worlds, check_named_mod, check_definition_stratified,
                       definition_edges, definition_cycles, check_parts, part_words
  unnamed それ以外（法則の個体に結びつかない検査: 文法・形・読み込み・領域など）
数える量:
  n_sites, n_rule, n_given, n_unnamed
  by_func_<関数名>  unnamed の箇所の、関数ごとの数（記述）
  n_law_rule, n_law_given  cscl/library/syntax/syntax.yaml の法則の個体を種類で数えた数（記述）
判定（事前に決める）:
  仮説は今の形（検査器は cscl で書けている）で述べているので、
  n_given = 0 かつ n_unnamed = 0 なら支持。n_given + n_unnamed > 0 なら反証。
  この判定は「今書けているか」であって、「書けるようにできるか」は問わない。後者は反証のあとの別の仮説にする。
行（sys_cscl_self_hosting.json）:
  "summary 要約": 上の量
  "texts": unnamed の箇所の (行, 関数, 文の定数の部分の先頭 40 字)

使い方:
  python exp/experiments/sys_cscl_self_hosting.py
"""
import ast
import collections
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TC = ROOT / "cscl/bootstrap/type_checker/type_checker.py"
SYNTAX = ROOT / "cscl/library/syntax/syntax.yaml"
OUT = ROOT / "exp/experiments/results/sys_cscl_self_hosting.json"

GIVEN_FUNCS = {"check_world_declared", "presumed_worlds", "check_named_mod", "check_definition_stratified",
               "definition_edges", "definition_cycles", "check_parts", "part_words"}
RULE_FUNCS = {"check_laws"}


def sites(src):
    out = []

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, n):
            self.stack.append(n.name)
            self.generic_visit(n)
            self.stack.pop()

        def visit_Call(self, n):
            if getattr(n.func, "id", None) == "err":
                text = ""
                if n.args and isinstance(n.args[0], ast.JoinedStr):
                    text = "".join(v.value for v in n.args[0].values if isinstance(v, ast.Constant))
                elif n.args and isinstance(n.args[0], ast.Constant):
                    text = str(n.args[0].value)
                out.append((n.lineno, self.stack[-1] if self.stack else "<module>", text[:40]))
            self.generic_visit(n)

    V().visit(ast.parse(src))
    return out


def main():
    ss = sites(TC.read_text())
    kind = lambda f: "rule" if f in RULE_FUNCS else "given" if f in GIVEN_FUNCS else "unnamed"
    c = collections.Counter(kind(f) for _, f, _ in ss)
    by = collections.Counter(f for _, f, _ in ss if kind(f) == "unnamed")
    S = yaml.safe_load(SYNTAX.read_text())
    laws = collections.Counter(str((x or {}).get("is", "")).split(".")[-1] for x in (S.get("individuals") or {}).values())
    summary = {"n_sites": len(ss), "n_rule": c["rule"], "n_given": c["given"], "n_unnamed": c["unnamed"],
               "n_law_rule": laws["law_rule"], "n_law_given": laws["law_given"]}
    summary.update({f"by_func_{f}": n for f, n in sorted(by.items())})
    texts = [{"line": l, "func": f, "text": t} for l, f, t in ss if kind(f) == "unnamed"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
