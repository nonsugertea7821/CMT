"""h_law_given_as_rule の訂正（sys_law_given_as_rule.py の後、結果を見てから、実行の前に登録した）。

訂正の理由: 元の手順では zz_a と zz_b が同じ式になり、named_mod と関係のない誤り（one_name・specific・大きさ）が 5 つ出た。
  また N と I の文の違いは r_written(lang:zz_m, lang.zz_m) の 1 つだけで、これは「名前 zz_m がどこかで書かれた」ことしか
  言わない。どのノードが名前で書いたかが文にあるかは、元の比べ方では分からない。
訂正した操作（一時の写しで行う。体系のファイルも検査器も書き換えない。アンカーは元と同じ）:
  二つのノードに別の上位を与え、式を違える:
    zz_a: extends: symmetry_break、zz_b: extends: implementation_break
  版:
    N  両方が名前で使う                     zz_a: mod: zz_m、zz_b: mod: zz_m
    M  zz_a は名前で、zz_b はその場に書く     zz_a: mod: zz_m、zz_b: mod: {of: [v_refer, from], with: quality}
    I  両方がその場に書く
  zz_m は元と同じ: zz_m: {display: 試しの修飾語, extends: quality, of: [v_refer, from], with: quality}
数える量（版ごと）: py_<v>、other_<v>、n_facts_<v>（元と同じ定義）。facts_equal_MN、facts_equal_NI（文の集まりが等しければ 1）。
判定（事前に決める）:
  facts_equal_MN = 1 かつ py_N = 0 かつ py_M ≥ 1 かつ other_N = other_M = 0 なら反証
    （M と N は同じ文なのに named_mod は M だけを咎める。今の syntax_facts の上の規則では named_mod を書けない）。
  facts_equal_MN = 0 なら、この手順では妨げを示せない。未検証のまま残し、違う文を開示する。
  ほかの組み合わせは、手順の誤りとして開示し、状態を変えない。
行（sys_law_given_as_rule_fix.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 4）と、M と N、N と I で違う文（最大 10）

使い方:
  python exp/experiments/sys_law_given_as_rule_fix.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_law_given_as_rule as base

base.OUT = base.ROOT / "exp/experiments/results/sys_law_given_as_rule_fix.json"
INL = base.INL


def node(name, parent, mod):
    return f"  {name}: {{display: 試し{name[-1].upper()}, extends: {parent}, mod: {mod}}}\n"


A = lambda mod: node("zz_a", "symmetry_break", mod)
B = lambda mod: node("zz_b", "implementation_break", mod)
base.CASES = {
    "N": base.ZM + A("zz_m") + B("zz_m"),
    "M": base.ZM + A("zz_m") + B(INL),
    "I": base.ZM + A(INL) + B(INL),
}


def main():
    R = {c: base.run(c) for c in base.CASES}
    F = {c: set(r["facts"]) for c, r in R.items()}
    summary = {}
    for c, r in R.items():
        summary[f"py_{c}"] = r["py"]
        summary[f"other_{c}"] = r["other"]
        summary[f"n_facts_{c}"] = len(F[c])
    summary["facts_equal_MN"] = int(F["M"] == F["N"])
    summary["facts_equal_NI"] = int(F["N"] == F["I"])
    texts = {f"errors {c}": r["texts"] for c, r in R.items()}
    texts["only_M_vs_N"] = sorted(F["M"] - F["N"])[:10]
    texts["only_N_vs_M"] = sorted(F["N"] - F["M"])[:10]
    texts["only_N_vs_I"] = sorted(F["N"] - F["I"])[:10]
    texts["only_I_vs_N"] = sorted(F["I"] - F["N"])[:10]
    base.OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
