"""仮説 h_mod_phrase_from_formula（限定ごとの表示語の句を、その限定の式から訳す: v_depend(syntax.display, syntax.mod)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: h_part_display_from_formula（#450、反証）は、ノードの表示語を丸ごと訳して置き換えたので、上位の表示語に入った逆向きの句を
  法則 part_display_explicit が読んだ。h_display_as_part_tree（#456、支持）は、句を限定ごとに持てば法則がその句だけを読めると示した。
  こちらは、句を書かずに限定の式から訳すとき、(1) 体系の中の部分の限定がすべて訳せるか、(2) 訳した句で法則も
  ほかの検査も誤りを出さないか、(3) 書き手が逆向きの句を書いても、訳が置き換えるので法則に届かないか、を見る。
  訳した句は役割から言い方を選ぶので、(2) の法則の誤りが 0 なのは訳し方からして当然。確かめる中身は (1) と、ほかの検査を壊さないこと。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  syntax.yaml の写しの grammar で、限定の語（mod）に display を足す（#456 と同じ）。
  検査器の写しの check_parts で、表示名を読む前に、部分の限定 m ごとに句を訳して m の display に置く:
    句 = 表示(with) + 言い方。言い方は、役割が部分なら「の{語幹}である」、全体なら「を{語幹}に持つ」、
    neg の限定なら「の{語幹}でない」「を{語幹}に持たない」。語幹は限定の動詞の表示語から「になる」を除いたもの（#450 と同じ）。
    with が名前でノードを指し、そのノードと動詞が表示語を持ち、動詞の表示語が「になる」で終わるときだけ訳す。
    訳せない限定には何も置かない（法則は今と同じく表示名を読む）。
  法則は、m に display があればその句、なければ表示名を読む（#456 と同じ）。
走らせるもの（どれも tc.build() を 1 回）:
  O0 体系のまま、文法と検査器は今のまま
  T  体系のまま、文法と検査器は変えた写し
  合成の版（claims の写しにノードを足す。文法と検査器は変えた写し。zz_b「試しB」は quality の下）:
    R 「試しBを部分に持つ試しA」、限定 {of: [v_compose, from], with: zz_b}（今の法則なら向きが逆と咎める）
    X R に、書き手の句 display: 試しBを部分に持つ を限定に書き足したもの
数える量:
  n_target      T で、部分の限定を持つ動詞でないノードの、部分の限定の数
  n_translated  そのうち、句を訳して置いた数
  py_O0 / py_T  O0 / T の、法則 part_display_explicit の誤りの数
  new_T         T の誤りのうち、O0 にないものの数
  py_R / py_X   版 R / X の、法則 part_display_explicit の誤りの数
  crash         どれかのプローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    n_translated = n_target、py_T = 0、new_T = 0、py_R = 0、py_X = 0 なら支持
      （部分の限定の句は、どれも限定の式から訳せ、訳した句で体系の検査が通り、書き手の句は法則に届かない）。
    n_translated < n_target か、new_T ≥ 1 なら反証（式から訳せない限定があるか、訳した句がほかの検査を壊す）。
    それ以外（py_T ≥ 1、py_R ≥ 1、py_X ≥ 1）は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: 法則を外すこと、表示名（平らな文字列）を訳した句から組み立てることは、この手順ではしない。
行（sys_mod_phrase_from_formula.json）:
  "summary 要約": 上の量
  "texts": 訳した句（先頭 30）、訳せなかった限定（先頭 20）、new_T の文（先頭 10）、版ごとの法則の誤りの文（先頭 4）

使い方:
  python exp/experiments/sys_mod_phrase_from_formula.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_mod_phrase_from_formula.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
CLAIMS = "cscl/design/claims.yaml"
GRAM_OLD = "  mod: [of, with, neg, quant, at]\n"
GRAM_NEW = "  mod: [of, with, neg, quant, at, display]\n"
READ_OLD = """            if any(w in disp for w in PART_VAGUE):
                err(f"法則 part_display_explicit に反する: {nid} の表示名「{disp}」は、どちらが部分かが曖昧")
            if any(w in disp for w in PART_WORDS["to" if r == "part" else "from"]) and not m.get("neg"):
"""
READ_NEW = """            _ph = m.get("display") if isinstance(m.get("display"), str) else disp
            if any(w in _ph for w in PART_VAGUE):
                err(f"法則 part_display_explicit に反する: {nid} の表示名「{disp}」は、どちらが部分かが曖昧")
            if any(w in _ph for w in PART_WORDS["to" if r == "part" else "from"]) and not m.get("neg"):
"""
TR_ANCHOR = "    PART_WORDS, PART_VAGUE = part_words(T)\n"
TR_ADD = """    T._tree = {"target": [], "translated": {}}
    for _nid, _n in T.N.items():
        if T.is_verb(_nid):
            continue
        for _i, _m in enumerate(_n.get("mod") or []):
            _r = role(_m)
            if _r is None:
                continue
            _key = f"{_nid} {_i}"
            T._tree["target"].append(_key)
            _w = T.q(_m["with"]) if isinstance(_m.get("with"), str) else None
            _v = T.q(_m["of"][0])
            _wd = (T.N.get(_w) or {}).get("display") if _w else None
            _vd = (T.N.get(_v) or {}).get("display") or ""
            if not _wd or not _vd.endswith("になる"):
                continue
            _s = _vd.removesuffix("になる")
            _say = (f"の{_s}でない" if _m.get("neg") else f"の{_s}である") if _r == "part" else (f"を{_s}に持たない" if _m.get("neg") else f"を{_s}に持つ")
            _m["display"] = _wd + _say
            T._tree["translated"][_key] = _m["display"]
"""
NODE_ANCHOR = "  is_from_lang_decision: {display: 言語の設計の決定へ属する（始点）, extends: quality, of: [is, from], with: lang_decision}\n"
ZB = "  zz_b: {display: 試しB, extends: quality}\n"
SYNTH = {
    "R": "  zz_a: {display: 試しBを部分に持つ試しA, extends: quality, mod: {of: [v_compose, from], with: zz_b}}\n" + ZB,
    "X": "  zz_a: {display: 試しBを部分に持つ試しA, extends: quality, mod: {of: [v_compose, from], with: zz_b, display: 試しBを部分に持つ}}\n" + ZB,
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
tree = getattr(T, "_tree", None) if T is not None else None
print(json.dumps({"errors": errs, "tree": tree}, ensure_ascii=False))
'''


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]], "tree": None}


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
            patch(d / TC, READ_OLD, READ_NEW)
            patch(d / TC, TR_ANCHOR, TR_ADD + TR_ANCHOR)
        if nodes:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + nodes)
        return probe(d)


def main():
    o0, t = run(False), run(True)
    probes = [o0, t]
    summary, texts = {}, {}
    tree = t["tree"] or {"target": [], "translated": {}}
    summary["n_target"] = len(tree["target"])
    summary["n_translated"] = len(tree["translated"])
    summary["py_O0"] = sum(LAW in e for e in o0["errors"])
    summary["py_T"] = sum(LAW in e for e in t["errors"])
    new = [e for e in t["errors"] if e not in o0["errors"]]
    summary["new_T"] = len(new)
    texts["translated"] = [f"{k}: {v}" for k, v in list(tree["translated"].items())[:30]]
    texts["untranslated"] = [k for k in tree["target"] if k not in tree["translated"]][:20]
    texts["new T"] = new[:10]
    for v, nodes in SYNTH.items():
        r = run(True, nodes)
        probes.append(r)
        law = [e for e in r["errors"] if LAW in e]
        summary[f"py_{v}"] = len(law)
        texts[f"law {v}"] = law[:4]
    summary["crash"] = int(any(e.startswith("probe failed") for p in probes for e in p["errors"]) or t["tree"] is None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
