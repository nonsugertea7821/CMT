"""仮説 h_display_as_part_tree（表示語を平らな文字列でなく、式の部分の木として持ち、検査は木を読む:
v_depend(syntax.display, syntax.expression_part)）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: h_part_display_from_formula の反証（#450）から対で出した二つ目。一つ目の h_part_display_own_phrase（#454、支持）は、
  表示名から上位の表示語を除いて読めば、訳した表示語で誤りが出ないことを示した。ただし、一つのノードが部分の限定と
  全体の限定を両方持つとき、平らな文字列ではどの句がどの限定のものかを分けられない（#454 の範囲の外）。
  こちらは、限定（式の部分）ごとに表示語の句を持たせ、法則がその句だけを読めば、両方を持つノードも分けて検査できるかを見る。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  syntax.yaml の写しの grammar で、限定の語（mod）に display を足す: [of, with, neg, quant, at, display]。
  検査器の写しの check_parts で、部分の限定 m ごとに読む文字列を、m に display があればその句、なければ表示名（今と同じ）にする。
走らせるもの（どれも tc.build() を 1 回）:
  O0 体系のまま、文法と検査器は今のまま
  O1 体系のまま、文法と検査器は写しを変えたもの
  合成の版（claims の写しにノードを足す。文法と検査器は変えた写し。zz_b「試しB」と zz_c「試しC」は quality の下）:
    zz_a「試しBの部分である試しCを部分に持つ試しA」（quality の下）に、限定を二つ:
      部分の限定 {of: [v_compose, from], with: zz_b}（zz_a は zz_b の部分）
      全体の限定 {of: [v_compose, to], with: zz_c}（zz_a は zz_c を部分に持つ）
    F 限定に句を持たせない（平らな文字列だけ）
    M 句を持たせる: 部分の限定に「試しBの部分である」、全体の限定に「試しCを部分に持つ」
    X 句を入れ替える: 部分の限定に「試しCを部分に持つ」、全体の限定に「試しBの部分である」
    G 部分の限定の句を曖昧にする: 「試しBから部分になる」（全体の限定は M と同じ）
数える量:
  lost / gained  O0 にあって O1 にない誤りの数 / O1 にあって O0 にない誤りの数
  py_<v>         版 v（F M X G）の、法則 part_display_explicit の誤りの数
  other_<v>      版 v の誤りのうち、法則 part_display_explicit のものでも、版 F の誤りでもないものの数（M X G）
  n_both         体系（O1）の中で、部分の限定と全体の限定を両方持つ、動詞でないノードの数（記録だけ。判定に使わない）
  crash          どれかのプローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    lost = 0、gained = 0、py_F ≥ 1、py_M = 0、py_X ≥ 2、py_G ≥ 1、other_M = other_X = other_G = 0 なら支持
      （句を限定ごとに持てば、平らな文字列では咎めてしまう両方を持つノードを、正しく分けて検査できる）。
    py_M ≥ 1、または other のどれかが 1 以上なら反証（限定に句を持たせると、ほかの検査を壊すか、分けて読めない）。
    それ以外（py_F = 0、py_X < 2、py_G = 0、lost か gained が 1 以上）は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: 訳した表示語を体系に入れることも、法則を規則に移した形（#455）で読むことも、この手順ではしない。
行（sys_display_as_part_tree.json）:
  "summary 要約": 上の量
  "texts": 版ごとの法則の誤りの文（先頭 4）、other の文（先頭 6）、O0 と O1 の差の文（先頭 10）、n_both のノード（先頭 20）

使い方:
  python exp/experiments/sys_display_as_part_tree.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_display_as_part_tree.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
CLAIMS = "cscl/design/claims.yaml"
GRAM_OLD = "  mod: [of, with, neg, quant, at]\n"
GRAM_NEW = "  mod: [of, with, neg, quant, at, display]\n"
TC_OLD = """            if any(w in disp for w in PART_VAGUE):
                err(f"法則 part_display_explicit に反する: {nid} の表示名「{disp}」は、どちらが部分かが曖昧")
            if any(w in disp for w in PART_WORDS["to" if r == "part" else "from"]) and not m.get("neg"):
"""
TC_NEW = """            _ph = m.get("display") if isinstance(m.get("display"), str) else disp
            if any(w in _ph for w in PART_VAGUE):
                err(f"法則 part_display_explicit に反する: {nid} の表示名「{disp}」は、どちらが部分かが曖昧")
            if any(w in _ph for w in PART_WORDS["to" if r == "part" else "from"]) and not m.get("neg"):
"""
NODE_ANCHOR = "  is_from_lang_decision: {display: 言語の設計の決定へ属する（始点）, extends: quality, of: [is, from], with: lang_decision}\n"
ZBC = "  zz_b: {display: 試しB, extends: quality}\n  zz_c: {display: 試しC, extends: quality}\n"


def node(p_part=None, p_whole=None):
    a = f", display: {p_part}" if p_part else ""
    b = f", display: {p_whole}" if p_whole else ""
    return ("  zz_a: {display: 試しBの部分である試しCを部分に持つ試しA, extends: quality, mod: ["
            f"{{of: [v_compose, from], with: zz_b{a}}}, {{of: [v_compose, to], with: zz_c{b}}}]}}\n" + ZBC)


SYNTH = {
    "F": node(),
    "M": node("試しBの部分である", "試しCを部分に持つ"),
    "X": node("試しCを部分に持つ", "試しBの部分である"),
    "G": node("試しBから部分になる", "試しCを部分に持つ"),
}
LAW = "法則 part_display_explicit"

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T = tc.build()[0]
        crash = ""
    except Exception as e:
        T, crash = None, repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
both = []
if T is not None:
    parts = lambda v: {(h["from"], h["to"]) for h in T.end(v, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"} if v in T.N else set()
    def role(m):
        if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2:
            return None
        v, pos = T.q(m["of"][0]), m["of"][1]
        wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
        P = parts(v)
        return "part" if (pos, wpos) in P else "whole" if (wpos, pos) in P else None
    for nid, n in T.N.items():
        if T.is_verb(nid):
            continue
        rs = {role(m) for m in n.get("mod") or []}
        if {"part", "whole"} <= rs:
            both.append(nid)
print(json.dumps({"errors": errs, "both": both}, ensure_ascii=False))
'''


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]], "both": []}


def patch(p, old, new):
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, old
    p.write_text(s.replace(old, new), encoding="utf-8")


def run(tree, nodes=""):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")
        if tree:
            patch(d / SYN, GRAM_OLD, GRAM_NEW)
            patch(d / TC, TC_OLD, TC_NEW)
        if nodes:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + nodes)
        return probe(d)


def main():
    o0, o1 = run(False), run(True)
    probes = [o0, o1]
    summary, texts = {}, {}
    summary["lost"] = len([e for e in o0["errors"] if e not in o1["errors"]])
    summary["gained"] = len([e for e in o1["errors"] if e not in o0["errors"]])
    texts["O0 vs O1"] = ([e for e in o0["errors"] if e not in o1["errors"]] + [e for e in o1["errors"] if e not in o0["errors"]])[:10]
    res = {}
    for v, nodes in SYNTH.items():
        res[v] = run(True, nodes)
        probes.append(res[v])
        law = [e for e in res[v]["errors"] if LAW in e]
        summary[f"py_{v}"] = len(law)
        texts[f"law {v}"] = law[:4]
    for v in ("M", "X", "G"):
        other = [e for e in res[v]["errors"] if LAW not in e and e not in res["F"]["errors"]]
        summary[f"other_{v}"] = len(other)
        texts[f"other {v}"] = other[:6]
    summary["n_both"] = len(o1["both"])
    texts["both"] = o1["both"][:20]
    summary["crash"] = int(any(e.startswith("probe failed") for p in probes for e in p["errors"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
