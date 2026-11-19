"""対の仮説 h_concept_kind_excludes_verb と h_concept_kind_frame_free を、同じ手順で確かめる。
結果を見る前に、この説明と手順を登録した。

系列: h_rule_frame_redundant（#344）は反証。法則 concept_kind は、自分の pre・holds を持たないことを r_concept の前提にし、
  上位から受け継いだものは見ない。そのため v_refer を上位に持つ動詞が r_concept と r_verb の両方に入る（L で 67 項）。
  登録（6315569）で、反証から別々の解き方を対で出した:
    excludes_verb: 概念の分類は、上位をたどって pre・holds を読む（受け継いだ動詞も概念から外す）。
    frame_free:    概念の分類は pre・holds を読まない（枠を足しても導いた関係は変わらない）。
変種（一時の写しの syntax.yaml の法則 concept_kind だけを変える。体系のファイルは書き換えない）:
  L   そのまま。
  E   concept_kind の前提に {is: r_verb, from: var1, neg: true} を足す（r_verb は verb_inherit で上位から受け継ぐ）。
  N   concept_kind の前提から、holds と pre の否定（2 行）を除く。
  各変種に、枠を足した版 +f を作る: syntax.v_assume に holds: [{is: refer, from: from, to: to}] を足す
  （v_refer の holds と同じ文。#344 の R と同じ冗長な枠）。
測るもの（版ごと。型検査を写しで 1 回、exp_check を 1 回）:
  errors       型検査の誤りの数
  ec_fail      exp_check の終了コードが 0 でなければ 1
  n_concept    r_concept の項の数
  n_verb       r_verb の項の数
  n_both       両方に入る項の数
  n_rel        導いた関係の項の総数
  rel_eq_f     その変種の +f 版と、導いた関係の項の集合が同じなら 1（各変種の要約に置く）
判定（事前に決める。二つの仮説を別々に）:
  excludes_verb: E で errors 0、ec_fail 0、n_both 0 なら支持。E で n_both > 0、または errors > 0 なら反証。
    （ec_fail だけが 1 なら mixed。）
  frame_free:    N で errors 0、ec_fail 0、rel_eq_f 1 なら支持。N で rel_eq_f 0、または errors > 0 なら反証。
    （ec_fail だけが 1 なら mixed。）
  L の rel_eq_f は 0 になるはず（#344 の再現。記述）。
見込み:
  E: n_both は 0 になる。ただし概念から外れた動詞が、概念を前提にする法則（placed_deduced, monotone など）から
     抜けるので、誤りが出るかどうかは分からない。
  N: 動詞が r_concept に入ったままになり、n_both は増える。placed_deduced は r_verb の否定を前提にするので、
     動詞が placed_deduced に入ることはない見込み。枠は concept_kind から読まれないので rel_eq_f は 1 の見込み。
  ただし N は「修飾語・形」の否定（of, form）は残すので、完全に枠を読まない分類ではない（開示）。

行（sys_concept_kind_pair.json）:
  "variant <v>": 上の量（v は L, L+f, E, E+f, N, N+f）
  "summary 要約": errors_<V>, ec_fail_<V>, n_both_<V>, n_concept_<V>, rel_eq_f_<V>（V は L, E, N）
使い方:
  python exp/experiments/sys_concept_kind_pair.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_concept_kind_pair.json"
SYN = "cscl/library/syntax/syntax.yaml"
PRE_LINE = "  - {is: v_assume, from: concept_kind, to: {is: pre, from: var1, to: var3, neg: true}}\n"
HOLDS_LINE = "  - {is: v_assume, from: concept_kind, to: {is: holds, from: var1, to: var3, neg: true}}\n"
E_ADD = "  - {is: v_assume, from: concept_kind, to: {is: r_verb, from: var1, neg: true}}\n"
ASSUME = "  v_assume: {display: 前提に置く, extends: v_refer, from: law_rule, to: premise}\n"
ASSUME_F = "  v_assume: {display: 前提に置く, extends: v_refer, from: law_rule, to: premise, holds: [{is: refer, from: from, to: to}]}\n"

PROBE = r'''
import contextlib, io, json, subprocess, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
errs = [str(e) for e in tc.errors]
F = tc.Facts(T.syntax_facts())
tc.evaluate(tc.law_rules(O), F, tc.variables(O))
items = lambda name: set().union(*[set(map(str, F.by[k])) for k in F.by if str(k).split(".")[-1] == name] or [set()])
c, v = items("r_concept"), items("r_verb")
rel = sorted(f"{k}{t}" for k in F.by if str(k).split(".")[-1].startswith("r_") for t in F.by[k])
ec = subprocess.run([sys.executable, "exp/src/exp_check.py"], capture_output=True, text=True)
print(json.dumps({"errors": len(errs), "ec_fail": int(ec.returncode != 0), "n_concept": len(c), "n_verb": len(v),
                  "n_both": len(c & v), "n_rel": len(rel), "rel": rel, "texts": errs[:10]}, ensure_ascii=False))
'''


def edit(s, version, frame):
    def rep(a, b):
        assert s.count(a) == 1, a
        return s.replace(a, b)
    if version == "E":
        s = rep(PRE_LINE, PRE_LINE + E_ADD)
    elif version == "N":
        s = rep(PRE_LINE, "")
        s = rep(HOLDS_LINE, "")
    if frame:
        s = rep(ASSUME, ASSUME_F)
    return s


def run(version, frame):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        f = Path(d) / SYN
        f.write_text(edit(f.read_text(encoding="utf-8"), version, frame), encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    rows, summ, texts = {}, {}, {}
    for v in "LEN":
        a, b = run(v, False), run(v, True)
        eq = int(a["rel"] == b["rel"])
        for name, r in ((v, a), (v + "+f", b)):
            rows[f"variant {name}"] = {k: r[k] for k in ("errors", "ec_fail", "n_concept", "n_verb", "n_both", "n_rel")}
            texts[name] = r["texts"]
        summ |= {f"errors_{v}": a["errors"], f"ec_fail_{v}": a["ec_fail"], f"n_both_{v}": a["n_both"],
                 f"n_concept_{v}": a["n_concept"], f"rel_eq_f_{v}": eq}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, r in rows.items():
        print(k, r)
    for k, t in texts.items():
        for e in t:
            print(k, e)


if __name__ == "__main__":
    main()
