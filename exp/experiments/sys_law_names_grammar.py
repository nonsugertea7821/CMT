"""h_law_names_grammar を確かめる: 型検査器が名前で読む語は、法則の名を除けば、文法の語・層の名・基礎の関係の名だけか。

仮説（claims.yaml）: 依存する(型検査器, [層の置き場, シグネチャから定まる分類, 文法の記述])。
  登録の経緯: 法則の名（LAWS_HERE, LAWS_RUN）を syntax の文法の語に置けば、型検査器が依るのはこの3つだけになる。
  ここでは置き換えをせず、いまのコードで、法則の名のほかに残る読み方があるかを数える。
  法則の名のほかに残るものがなければ、置き換えで仮説が成り立つ。残れば、法則の名を文法に置いても成り立たない。

手順（規則で決める）:
  cscl/bootstrap/type_checker/type_checker.py を ast で読み、文字列の定数を集める。
    f 文字列の中の定数と、関数・クラス・モジュールの説明（docstring）は除く。
  体系を tc.build() で読み、識別子の集まりを作る: ノード（領域を外した名）と個体の名。
  定数のうち識別子に一致するもの（名前で読む語）を、次の順に1つの組に入れる。
    grammar: syntax の grammar のどれかの節の語か、節の名。
    domain:  層の名（build が返す領域の名と signature）。
    base:    基礎の関係の名（ontology の base）。
    law:     law_given の個体の名。
    other:   上のどれでもない。
  行（sys_law_names_grammar.json）: "name 語": {grammar, domain, base, law, other（どれか1つが 1）, n_sites（出てくる箇所の数）}
  要約: n_names, n_grammar, n_domain, n_base, n_law, n_other
判定: n_other が 0 なら支持。1 以上なら反証。

開示（結果を見る前に分かっていること）:
  - KEYWORDS は文法の節（laws, rule_word, use_word, world）と等しいことを型検査器自身が確かめている。
  - LAWS_HERE と LAWS_RUN は law_given の個体の名で、文法の語でない。
  - ほかに名前で読む語があるかは数えていない。結果は予想しない。
  - 識別子に一致しても、名前で読んでいるとは限らない（誤りの文の一部など）。f 文字列は除いたが、
    ほかの文字列が偶然識別子と一致したものも数に入る。other の語は、箇所を見て解釈で書く。

訂正（結果の後、マージの後に開示）:
  - 「文法の語」を、syntax の grammar の節に書かれた語に限った。h_layers_unhardcode（#210）の手順は、
    syntax の層に置いたノード（role・definition・v_refer・v_agree）を「名前で読んでよい」として扱っていた。
    同じ仮説の系列で、名前で読んでよい語の範囲が2つの実験で違う。
  - #210 の範囲で読み直すと、other の 12 語のうち role・definition・v_refer は syntax のノード、syntax は層の名、
    7 語は偶然の一致で、残るのは any（シグネチャの語）だけになる。その読みでは反証にならない。
  - 判定は事前登録の範囲のまま（反証）とし、変えない。範囲の違いを、体系に式で書いていないことが原因。
使い方:
  python exp/experiments/sys_law_names_grammar.py
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "cscl/bootstrap/type_checker/type_checker.py"
OUT = ROOT / "exp/experiments/results/sys_law_names_grammar.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
import type_checker as tc  # noqa: E402

GROUPS = ("grammar", "domain", "base", "law", "other")


def constants(tree):
    skip = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            skip |= {id(c) for c in ast.walk(n)}
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                skip.add(id(b.value))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def main():
    T, O, Dm = tc.build()
    idents = {tc.short(k) for k in T.N} | set(T.I)
    gram = set(T.G) | {w for v in T.G.values() for w in (v or [])}
    doms = set(Dm) | {"signature"}
    base = set(O["base"])
    laws = {i for i, k in T.I.items() if tc.short(k) == "law_given"}
    sites = {}
    for c in constants(ast.parse(SRC.read_text(encoding="utf-8"))):
        if c.value in idents:
            sites.setdefault(c.value, []).append(c.lineno)
    rows = {}
    for w in sorted(sites):
        g = ("grammar" if w in gram else "domain" if w in doms else "base" if w in base
             else "law" if w in laws else "other")
        rows[f"name {w}"] = {**{x: int(x == g) for x in GROUPS}, "n_sites": len(sites[w])}
    R = list(rows.values())
    rows["summary 要約"] = {"n_names": len(R), **{f"n_{x}": sum(r[x] for r in R) for x in GROUPS}}
    other = {w: sites[w] for w in sites if rows[f"name {w}"]["other"]}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_law_names_grammar.py", "_commit": commit,
                               "rows": rows, "other_sites": other}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print(json.dumps(other, ensure_ascii=False))
    print("判定:", "支持" if rows["summary 要約"]["n_other"] == 0 else "反証")


if __name__ == "__main__":
    main()
