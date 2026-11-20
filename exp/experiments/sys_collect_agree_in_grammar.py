"""h_collect_agree_in_grammar を確かめる: 型検査器が名前で読む v_collect・v_agree を、文法の語（syntax の grammar の節）に置けるか。

仮説（claims.yaml）: v_refer(syntax.grammar, [syntax.v_collect, syntax.v_agree])。
  登録（7a60bc2）の読み: #301（h_renaming_invariant）の反証から、層の名を付けて読む v_collect・v_agree の解き方を対で出した。
  こちらは #232・#298 と同じ道（文法の節に置き、型検査器がその節と等しいことを確かめる）。
  対のもう一方 h_collect_by_formula は #398 で反証（式 F が広すぎた）。

手順: #298 の訂正版（sys_checker_words_in_grammar_fix.py）の操作と測りを、そのまま使う。替えるのは次だけ:
  節の名: checker_word → collect_word。語: [role, definition, v_refer] → [v_collect, v_agree]。
  対照 M: 節を [v_collect] にする（v_agree を抜く）。
  ノードの変種:
    N1: collect_word: {display: 型検査が名前で読む集まりと一致の語, extends: word}
    N2: collect_word: {display: 型検査が名前で読む集まりと一致の語, extends: word, mod: {of: [v_compose, to], with: nodes}}
  KEYWORDS に "collect_word": {"v_collect", "v_agree"} を足す（読み方の箇所は変えない）。
  測り（#298 の訂正版のまま）: errors、ec_errors、kw_errors、changed（before に現れない項を含む文を除いたハッシュ）、nodes_diff。
  #298 の結果ファイル（sys_checker_words_in_grammar*.json）は書かない。出力は sys_collect_agree_in_grammar.json。
判定（#298 と同じ規則）:
  M の kw_errors が 0 なら「外れ」（状態を変えない）。
  そうでなく、N1 か N2 のどちらかで errors 0・ec_errors 0・changed 0・nodes_diff 0 なら支持。どちらもそうでなければ反証。
開示（結果を見る前に分かっていること）:
  - #298 では、N1 は「式がない」と法則 monotone で落ち、N2 は r_kpart が 3 文増えて落ちた（訂正版）。節の名のノードの定義が課題で、
    3語の中身には依らない落ち方だった。同じ手順なので、同じ落ち方をする見込みが高い。予想としては反証。
  - それでも確かめるのは、v_collect・v_agree は KEYWORDS の検査（748 行付近）がその語を読むか、という点が 3 語と違いうるため。
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_checker_words_in_grammar_fix  # noqa: E402,F401  (m.PROBE を訂正版に替える)
import sys_checker_words_in_grammar as m  # noqa: E402

OUT = m.ROOT / "exp/experiments/results/sys_collect_agree_in_grammar.json"
NAME = "collect_word"
m.PROBE = m.PROBE.replace('NEW = "checker_word"', f'NEW = "{NAME}"')
assert f'NEW = "{NAME}"' in m.PROBE and '"dropped": dropped' in m.PROBE
G_LIST = (m.G_LIST[0], m.G_LIST[0].replace("use_word, domain", f"use_word, {NAME}, domain"))
N1 = f"  {NAME}: {{display: 型検査が名前で読む集まりと一致の語, extends: word}}\n"
N2 = f"  {NAME}: {{display: 型検査が名前で読む集まりと一致の語, extends: word, mod: {{of: [v_compose, to], with: nodes}}}}\n"
KW = (m.KW[0], m.KW[0] + f' "{NAME}": {{"v_collect", "v_agree"}},')


def main():
    with tempfile.TemporaryDirectory() as d:
        terms = str(Path(d) / "before_terms.json")
        os.environ["CWG_TERMS"] = terms
        os.environ.pop("CWG_BEFORE", None)
        sect = lambda ws: (m.SECT, m.SECT + f"  {NAME}: [{', '.join(ws)}]\n")
        full = ["v_collect", "v_agree"]
        res = {"before": m.variant([], [])}
        os.environ["CWG_BEFORE"] = terms
        res["N1"] = m.variant([G_LIST, sect(full), (m.NODE, m.NODE + N1)], [KW])
        res["N2"] = m.variant([G_LIST, sect(full), (m.NODE, m.NODE + N2)], [KW])
        res["M"] = m.variant([G_LIST, sect(full[:1]), (m.NODE, m.NODE + N1)], [KW])
    b0 = res["before"]
    rows = {}
    for k, r in res.items():
        ch = sorted(x for x in set(r["rel"]) | set(b0["rel"]) if r["rel"].get(x) != b0["rel"].get(x))
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "kw_errors": r["kw_errors"],
                                "changed": len(ch), "nodes_diff": len(set(r["nodes"]) ^ set(b0["nodes"])),
                                "n_new_terms": r["n_new_terms"], "n_dropped": sum(r["dropped"].values())}
        rows |= {f"changed {k} {x}": {"before": b0["rel"].get(x), "after": r["rel"].get(x)} for x in ch}
        rows |= {f"new_term {k} {i}": {"text": t} for i, t in enumerate(r["new_terms"])}
        rows |= {f"error {k} {i}": {"text": e} for i, e in enumerate(r["err_text"])}
    ok = lambda k: all(rows[f"variant {k}"][x] == 0 for x in ("errors", "ec_errors", "changed", "nodes_diff"))
    if rows["variant M"]["kw_errors"] == 0:
        verdict = "外れ"
    elif ok("N1") or ok("N2"):
        verdict = "支持"
    else:
        verdict = "反証"
    rows["summary 要約"] = {"verdict_support": int(verdict == "支持"), "verdict_refute": int(verdict == "反証"),
                          "N1_passes": int(ok("N1")), "N2_passes": int(ok("N2")),
                          **{f"{k}_{x}": rows[f"variant {k}"][x] for k in res
                             for x in ("errors", "ec_errors", "kw_errors", "changed", "nodes_diff")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=m.ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        if not k.startswith(("error", "new_term")):
            print(k, json.dumps(v, ensure_ascii=False))
    for k, v in rows.items():
        if k.startswith("error"):
            print(k, v["text"][:200])
    print("判定:", verdict)


if __name__ == "__main__":
    main()
