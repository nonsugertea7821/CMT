"""sys_checker_words_in_grammar の訂正（開示）: 元の実行（sys_checker_words_in_grammar.json）で、判定は反証。
  N1: errors 2・ec 2（syntax.checker_word: 式がない。法則 monotone に反する: checker_word と word）。
  N2: errors 0・ec 0・nodes_diff 0 で、changed 9（of・with・position・r_written が 1 ずつ、r_kpart 3、r_op_of 2、
      r_mod_differ 70、r_mod_lacks 70、r_same_slot 71 文増えた）。
  M: kw_errors 1（v_refer を抜いた節を、型検査器が等しくないと言った）。
N2 で増えた文は、足したノードの式の中の限定 {of: [v_compose, to], with: nodes} の文と読める。syntax_facts は式の中の限定を
yaml の書き出し（"of:\n- syntax.v_compose ..."）で名づけ、その名は checker_word を含まない。ハッシュから除く文を名前の部分一致で
決めたため、足した名前なしの項の文が残った。#147・#148 と同じ型の測りの欠け（足したものの宣言そのものを数えた）である。

訂正: 文を除く基準を「before に現れない項を1つでも含む文」に変える（checker_word を含む文もこれに入る）。
  before の項は、before の事実のどれかの文の項として現れたもの全体。除いた後のハッシュを関係ごとに比べ、changed を取り直す。
  あわせて、除いた新しい項の名（最初の 20）と、関係ごとの除いた文の数を行に書く。
  変種・書き換え・ほかの測り・判定の規則は sys_checker_words_in_grammar.py のまま（そこから読み込む）。
  元の結果ファイルは上書きしない。出力は sys_checker_words_in_grammar_fix.json。

結果を見て分かっていること（開示）: 上の元の数。N1 は changed でなく誤りで落ちているので、この訂正で N1 の判定は変わらない。
  N2 の changed が 0 になれば支持、残れば反証。M の kw_errors は変わらない。
使い方:
  python exp/experiments/sys_checker_words_in_grammar_fix.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_checker_words_in_grammar as m  # noqa: E402

OUT = m.ROOT / "exp/experiments/results/sys_checker_words_in_grammar_fix.json"
OLD = '''rel = {}
for r, xs in F.by.items():
    keep = sorted(str(x) for x in xs if not any(NEW in str(a) for a in x))
    if keep:
        rel[r] = [len(keep), hashlib.sha256("\\n".join(keep).encode()).hexdigest()[:16]]
'''
NEW = '''import os
terms = {str(a) for xs in F.by.values() for x in xs for a in x}
base = os.environ.get("CWG_BEFORE")
old = set(json.load(open(base, encoding="utf-8"))) if base else terms
if not base:
    json.dump(sorted(terms), open(os.environ["CWG_TERMS"], "w", encoding="utf-8"))
rel, dropped = {}, {}
for r, xs in F.by.items():
    keep = sorted(str(x) for x in xs if all(str(a) in old for a in x))
    if len(keep) != len(xs):
        dropped[r] = len(xs) - len(keep)
    if keep:
        rel[r] = [len(keep), hashlib.sha256("\\n".join(keep).encode()).hexdigest()[:16]]
new_terms = sorted(terms - old)
'''
assert m.PROBE.count(OLD) == 1
m.PROBE = m.PROBE.replace(OLD, NEW).replace('"nodes": nodes}', '"nodes": nodes, "dropped": dropped, "new_terms": new_terms[:20], "n_new_terms": len(new_terms)}')
assert '"dropped": dropped' in m.PROBE


def main():
    with tempfile.TemporaryDirectory() as d:
        terms = str(Path(d) / "before_terms.json")
        os.environ["CWG_TERMS"] = terms
        sect = lambda ws: (m.SECT, m.SECT + f"  checker_word: [{', '.join(ws)}]\n")
        full = ["role", "definition", "v_refer"]
        res = {"before": m.variant([], [])}
        os.environ["CWG_BEFORE"] = terms
        res["N1"] = m.variant([m.G_LIST, sect(full), (m.NODE, m.NODE + m.N1)], [m.KW])
        res["N2"] = m.variant([m.G_LIST, sect(full), (m.NODE, m.NODE + m.N2)], [m.KW])
        res["M"] = m.variant([m.G_LIST, sect(full[:2]), (m.NODE, m.NODE + m.N1)], [m.KW])
    b0 = res["before"]
    rows = {}
    for k, r in res.items():
        ch = sorted(x for x in set(r["rel"]) | set(b0["rel"]) if r["rel"].get(x) != b0["rel"].get(x))
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "kw_errors": r["kw_errors"],
                                "changed": len(ch), "nodes_diff": len(set(r["nodes"]) ^ set(b0["nodes"])),
                                "n_new_terms": r["n_new_terms"], "n_dropped": sum(r["dropped"].values())}
        rows |= {f"changed {k} {x}": {"before": b0["rel"].get(x), "after": r["rel"].get(x)} for x in ch}
        rows |= {f"dropped {k} {x}": {"n": n} for x, n in sorted(r["dropped"].items())}
        rows |= {f"new_term {k} {i}": {"text": t} for i, t in enumerate(r["new_terms"])}
        rows |= {f"error {k} {i}": {"text": e} for i, e in enumerate(r["err_text"])}
    ok = lambda k: all(rows[f"variant {k}"][x] == 0 for x in ("errors", "ec_errors", "changed", "nodes_diff"))
    if rows["variant M"]["kw_errors"] == 0:
        verdict = "外れ"
    elif ok("N1") or ok("N2"):
        verdict = "支持"
    else:
        verdict = "反証"
    rows["summary 要約"] = {"verdict_support": int(verdict == "支持"), "N1_passes": int(ok("N1")), "N2_passes": int(ok("N2")),
                          **{f"{k}_{x}": rows[f"variant {k}"][x] for k in res
                             for x in ("errors", "ec_errors", "kw_errors", "changed", "nodes_diff", "n_new_terms", "n_dropped")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=m.ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        if not k.startswith(("error", "new_term")):
            print(k, json.dumps(v, ensure_ascii=False))
    print("判定:", verdict)


if __name__ == "__main__":
    main()
