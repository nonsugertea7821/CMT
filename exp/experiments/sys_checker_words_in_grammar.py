"""h_checker_words_in_grammar を確かめる: 型検査器が名前で読む role・definition・v_refer を、文法の語（syntax の grammar の節）に置けるか。

仮説（claims.yaml）: v_refer(syntax.grammar, [syntax.role, syntax.definition, syntax.v_refer])。
  登録の経緯（bedc2bf）: #216（sys_law_names_grammar）で、法則の名のほかに型検査器が名前で読む語として role（1040・1259 行）・
  definition（1154 行）・v_refer（436 行）が残った。法則の名で取った道（KEYWORDS と同じく、文法の節に置き、型検査器が
  その節と等しいことを確かめる）を、この3語に当てはめられるかを見る。

「置ける」の操作（規則で決める）: 写し（cscl.yaml・cscl・exp/src・exp/experiments/results）で次を書き換え、検査を走らせる。
  syntax.yaml の grammar:
    grammar.grammar の列に checker_word を足す（use_word の後）。
    節 checker_word: [role, definition, v_refer] を足す（use_word の節の後）。
  syntax.yaml の nodes（use_word のノードの後）に、節の名のノード checker_word を足す。定義は2通り（変種）:
    N1: {display: 型検査が名前で読む語, extends: word}
    N2: {display: 型検査が名前で読む語, extends: word, mod: {of: [v_compose, to], with: nodes}}
  type_checker.py の KEYWORDS に "checker_word": {"role", "definition", "v_refer"} を足す（読み方の箇所は変えない）。
  対照 M（変異）: N1 の書き換えで、文法の節を checker_word: [role, definition] にする（v_refer を抜く）。

測るもの（変種ごと、before は書き換えなし）:
  errors: tc.build() の誤りの数。ec_errors: exp_check.build() の誤りの数。
  kw_errors: 誤りのうち "grammar.checker_word" を含むものの数。
  changed: 法則を評価した事実（tc.evaluate）の関係ごとのハッシュが before と違う関係の数。
    ハッシュは、checker_word を含む文を除いて取る（#147・#148 で、足した名の宣言そのものを数えた欠けを繰り返さない）。
  nodes_diff: ノードの名（checker_word を除く）の集まりの before との対称差の大きさ。
判定:
  M の kw_errors が 0 なら「外れ」（節と等しいことを確かめる仕組みが働いていない）。
  そうでなく、N1 か N2 のどちらかで errors 0・ec_errors 0・changed 0・nodes_diff 0 なら支持。
  どちらもそうでなければ反証（誤りの中身を行に書く）。

開示（結果を見る前に分かっていること）:
  - KEYWORDS の節（laws, rule_word, use_word, world）は、すでに同じ形で文法に置かれ、検査を通っている。
  - 文法の各語はノードに当たること、節の名は grammar.grammar に書かれていることを、型検査器が確かめる（748 行付近）。
  - 節の名のノードの定義に何が要るかは試していない。2通りを置いたのはそのため。結果は予想しない。
  - 「置ける」は、文法に書けて検査が等しさを確かめられることまでで、名前で読む箇所を式に置き換えることではない。
使い方:
  python exp/experiments/sys_checker_words_in_grammar.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYN = "cscl/library/syntax/syntax.yaml"
TC = "cscl/bootstrap/type_checker/type_checker.py"
OUT = ROOT / "exp/experiments/results/sys_checker_words_in_grammar.json"
NEW = "checker_word"

G_LIST = ("laws, rule_word, use_word, domain, individuals, facts, grammar]",
          "laws, rule_word, use_word, checker_word, domain, individuals, facts, grammar]")
SECT = "  use_word: [v_use, v_presume]\n"
NODE = "  use_word: {display: 領域の宣言を組み立てる語, extends: word, mod: {of: [v_compose, to], with: domain}}\n"
N1 = "  checker_word: {display: 型検査が名前で読む語, extends: word}\n"
N2 = "  checker_word: {display: 型検査が名前で読む語, extends: word, mod: {of: [v_compose, to], with: nodes}}\n"
KW = ('"use_word": {"v_use", "v_presume"},', '"use_word": {"v_use", "v_presume"}, "checker_word": {"role", "definition", "v_refer"},')

PROBE = r'''
import contextlib, hashlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker", "exp/src"]
NEW = "checker_word"
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
errs = [str(e) for e in tc.errors]
with contextlib.redirect_stdout(io.StringIO()):
    import exp_check
    del tc.errors[:]
    try:
        exp_check.build()
    except SystemExit:
        pass
ec = len(tc.errors)
F = tc.Facts(T.syntax_facts())
tc.evaluate(tc.law_rules(O), F, tc.variables(O))
rel = {}
for r, xs in F.by.items():
    keep = sorted(str(x) for x in xs if not any(NEW in str(a) for a in x))
    if keep:
        rel[r] = [len(keep), hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]]
nodes = sorted(n for n in T.N if NEW not in n)
print(json.dumps({"errors": len(errs), "ec_errors": ec, "kw_errors": sum("grammar." + NEW in e for e in errs),
                  "err_text": errs[:20], "rel": rel, "nodes": nodes}, ensure_ascii=False))
'''


def variant(syn_edits, tc_edits):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src", "exp/experiments/results"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        for rel_path, edits in ((SYN, syn_edits), (TC, tc_edits)):
            f = Path(d) / rel_path
            s = f.read_text(encoding="utf-8")
            for old, new in edits:
                assert s.count(old) == 1, old
                s = s.replace(old, new)
            f.write_text(s, encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    sect = lambda ws: (SECT, SECT + f"  checker_word: [{', '.join(ws)}]\n")
    full = ["role", "definition", "v_refer"]
    V = {"before": ([], []),
         "N1": ([G_LIST, sect(full), (NODE, NODE + N1)], [KW]),
         "N2": ([G_LIST, sect(full), (NODE, NODE + N2)], [KW]),
         "M": ([G_LIST, sect(full[:2]), (NODE, NODE + N1)], [KW])}
    res = {k: variant(*e) for k, e in V.items()}
    b0 = res["before"]
    rows = {}
    for k, r in res.items():
        ch = sorted(x for x in set(r["rel"]) | set(b0["rel"]) if r["rel"].get(x) != b0["rel"].get(x))
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "kw_errors": r["kw_errors"],
                                "changed": len(ch), "nodes_diff": len(set(r["nodes"]) ^ set(b0["nodes"]))}
        rows |= {f"changed {k} {x}": {"before": b0["rel"].get(x), "after": r["rel"].get(x)} for x in ch}
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
                             for x in ("errors", "ec_errors", "kw_errors", "changed", "nodes_diff")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        if not k.startswith("error"):
            print(k, json.dumps(v, ensure_ascii=False))
    print("判定:", verdict)


if __name__ == "__main__":
    main()
