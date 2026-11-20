"""仮説 h_verb_stem_from_signature（限定の句の語幹は、動詞の表示語の語尾でなく、動詞の定義から訳す: v_depend(syntax.display, syntax.from)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: h_mod_phrase_from_formula（#459、反証）と h_with_needs_display（#464、支持）で、部分の限定 99 のうち 84 の句を訳せた。
  残る 15 のうち 8 は、動詞の表示語が「になる」で終わらないもの（合成する・保管される・商品分類で分類される・所在する）。
  語幹を表示語の語尾から切り出す訳し方が、表示語の書き方に頼っていた。ここでは、語幹を動詞の定義から取る:
  (1) 動詞の上位（extends）をたどり、表示語が「になる」で終わる最も近い動詞から語幹を取る（例: 保管される → 部分になる）。
  (2) たどっても無ければ、動詞の holds が部分の事実を持つとき、語幹を「部分」とする（例: 合成する。部分は第三のもの new）。
  部分の限定の役割（部分か全体か）は、もともと動詞の holds の位置から読んでいる（role）。語幹も同じ定義から取れるかを見る。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  #464 の訂正の写し（grammar の mod に display、法則は m の display を読む、with の表示語はノードと、ライブラリと領域のファイルの個体から探す）に、
  上の語幹の取り方を足す。句 = 表示(with) + 言い方（#459 と同じ: 部分なら「の{語幹}である」、全体なら「を{語幹}に持つ」、neg なら否定）。
  with のない限定は訳さない（h_mod_phrase_without_with の範囲）。
走らせるもの: O0（今のまま）と T（変えた写し）。どちらも tc.build() を 1 回。
数える量（T で）:
  n_target        部分の限定（動詞でないノード）の数
  n_no_with       そのうち with を持たないもの
  n_with_target   n_target - n_no_with
  n_translated    句を訳した数
  n_verb_form     with を持ち、動詞の表示語が「になる」で終わらないものの数
  n_verb_form_translated  そのうち句を訳した数
  n_by_ancestor   上位の動詞から語幹を取った数
  n_by_holds      holds から「部分」を語幹にした数
  n_no_stem       語幹を取れなかった数
  py_T / new_T    T の法則 part_display_explicit の誤りの数 / O0 にない誤りの数
  crash           プローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    n_translated = n_with_target、n_verb_form_translated = n_verb_form、py_T = 0、new_T = 0 なら支持
      （with を持つ部分の限定は、どれも語幹を動詞の定義から取って句を訳せ、訳した句で検査が通る）。
    n_no_stem ≥ 1 か new_T ≥ 1 なら反証。
    それ以外は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: 句が日本語として自然かは数えない（h_ja_text_needs_naturalness の範囲）。訳した句は texts に残す。
行（sys_verb_stem_from_signature.json）:
  "summary 要約": 上の量
  "texts": 動詞の形が合わなかった限定の訳した句（先頭 20）、訳せなかった限定と原因（先頭 30）、new_T の文（先頭 10）

使い方:
  python exp/experiments/sys_verb_stem_from_signature.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_verb_stem_from_signature.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
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
TR_ADD = """    _IND = dict(T.O.get("individuals") or {})
    for _name, _dom in lib_and_domain_files():
        _IND |= (load(_name) or {}).get("individuals") or {}
    def _disp(_x):
        if not isinstance(_x, str):
            return None
        _d = (T.N.get(T.q(_x)) or {}).get("display")
        if _d:
            return _d
        for _k in (_x, _x.split(".")[-1]):
            if isinstance(_IND.get(_k), dict) and isinstance(_IND[_k].get("display"), str):
                return _IND[_k]["display"]
        return None
    def _is_ind(_x):
        return isinstance(_x, str) and T.q(_x) not in T.N and (_x in _IND or _x.split(".")[-1] in _IND)
    T._tree = {"with": [], "with_disp": [], "target": [], "translated": {}, "c": [], "c_ready": [], "c_translated": [], "why": {}, "by_ancestor": [], "by_holds": [], "verb_form": [], "verb_form_translated": []}
    for _nid, _n in T.N.items():
        for _i, _m in enumerate(_n.get("mod") or []):
            if isinstance(_m, dict) and isinstance(_m.get("with"), str):
                T._tree["with"].append(f"{_nid} {_i} {_m['with']}")
                if _disp(_m["with"]):
                    T._tree["with_disp"].append(f"{_nid} {_i}")
    for _nid, _n in T.N.items():
        if T.is_verb(_nid):
            continue
        for _i, _m in enumerate(_n.get("mod") or []):
            _r = role(_m)
            if _r is None:
                continue
            _key = f"{_nid} {_i}"
            T._tree["target"].append(_key)
            _v = T.q(_m["of"][0])
            _vd = (T.N.get(_v) or {}).get("display") or ""
            _ind = _is_ind(_m.get("with"))
            if _ind:
                T._tree["c"].append(_key)
                if _vd.endswith("になる"):
                    T._tree["c_ready"].append(_key)
            _wd = _disp(_m.get("with"))
            if not isinstance(_m.get("with"), str):
                T._tree["why"][_key] = "no_with"
                continue
            if not _wd:
                T._tree["why"][_key] = "no_display " + _m["with"]
                continue
            _a, _hops = _v, 0
            while _a in T.N and not ((T.N[_a].get("display") or "").endswith("になる")) and _hops < 50:
                _a, _hops = T.q(T.N[_a].get("extends")) if isinstance(T.N[_a].get("extends"), str) else None, _hops + 1
            if _a in T.N and (T.N[_a].get("display") or "").endswith("になる"):
                _s = T.N[_a]["display"].removesuffix("になる")
                if _a != _v:
                    T._tree["by_ancestor"].append(_key)
            elif parts(_v):
                _s = "部分"
                T._tree["by_holds"].append(_key)
            else:
                T._tree["why"][_key] = "no_stem " + _vd
                continue
            if not _vd.endswith("になる"):
                T._tree["verb_form"].append(_key)
            _say = (f"の{_s}でない" if _m.get("neg") else f"の{_s}である") if _r == "part" else (f"を{_s}に持たない" if _m.get("neg") else f"を{_s}に持つ")
            _m["display"] = _wd + _say
            T._tree["translated"][_key] = _m["display"]
            if _ind:
                T._tree["c_translated"].append(_key)
            if not _vd.endswith("になる"):
                T._tree["verb_form_translated"].append(_key)
"""
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


def run(tree):
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
        return probe(d)


def main():
    o0, t = run(False), run(True)
    tree = t["tree"] or {}
    g = lambda k: tree.get(k) or []
    summary, texts = {}, {}
    why = tree.get("why") or {}
    summary["n_target"] = len(g("target"))
    summary["n_no_with"] = sum(v == "no_with" for v in why.values())
    summary["n_with_target"] = summary["n_target"] - summary["n_no_with"]
    summary["n_translated"] = len(tree.get("translated") or {})
    summary["n_verb_form"] = len(g("verb_form"))
    summary["n_verb_form_translated"] = len(g("verb_form_translated"))
    summary["n_by_ancestor"] = len(g("by_ancestor"))
    summary["n_by_holds"] = len(g("by_holds"))
    summary["n_no_stem"] = sum(v.startswith("no_stem") for v in why.values())
    summary["py_T"] = sum(LAW in e for e in t["errors"])
    new = [e for e in t["errors"] if e not in o0["errors"]]
    summary["new_T"] = len(new)
    summary["crash"] = int(any(e.startswith("probe failed") for p in (o0, t) for e in p["errors"]) or t["tree"] is None)
    tr = tree.get("translated") or {}
    texts["verb form translated"] = [f"{k}: {tr[k]}" for k in g("verb_form_translated")][:20]
    texts["untranslated"] = [f"{k}: {v}" for k, v in why.items()][:30]
    texts["new T"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
