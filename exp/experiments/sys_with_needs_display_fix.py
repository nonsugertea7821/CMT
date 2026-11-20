"""h_with_needs_display の訂正の手順（sys_with_needs_display.py の訂正）。結果を見る前に、この訂正を登録した。

訂正: もとの手順は、個体の表示語を T.O["individuals"] だけから探した。それは公理の個体だけで、領域の個体（subj・exp など）は
  build の中にだけあり、T から届かなかった（もとの結果で n_c が 0、表示語がないと出た 14 がどれも領域の個体）。
  訂正では、ライブラリと領域のファイルを読み直し（load、yaml を読むだけ）、そこにある individuals も探す。
  ほかの手順・数える量・判定は、もとの手順（下に写す）のまま。結果は sys_with_needs_display_fix.json に書く。

もとの手順:
仮説 h_with_needs_display（限定の with が指すものには表示語が要る: v_depend(syntax.with, syntax.display)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: h_mod_phrase_from_formula（#459、反証）は、部分の限定 99 のうち 77 だけ句を訳せた。訳せなかった原因の一つを
  「with が個体で、表示語がない」と読んだ。ところが #459 の訳し方は、with の表示語をノード（種類）からだけ探し、
  個体（individuals）からは探していなかった。個体にも display を書いている。ここでは、(1) 体系の限定の with が指すものが
  どれも表示語を持つか、(2) 個体からも表示語を探せば、with が個体の部分の限定が訳せるようになるか、を見る。
  (2) で訳せなくなるのは、動詞の表示語が「になる」で終わらないとき（h_verb_stem_from_signature の範囲）なので、それは除いて数える。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  #459 と同じ写し（grammar の mod に display、法則は m の display を読む、限定ごとに句を訳す）を作り、
  訳すときの with の表示語を、ノードになければ個体（T.O["individuals"]、名前のままか、領域を外した名前）から探す。
走らせるもの: O0（今のまま）と T2（変えた写し）。どちらも tc.build() を 1 回。
数える量（T2 で）:
  n_with       体系のノードの限定で、with が名前（文字列）のものの数（動詞のノードも含む）
  n_with_disp  そのうち、with が指すノードか個体が表示語を持つものの数
  n_target     部分の限定（動詞でないノード）の数（#459 と同じ）
  n_translated そのうち句を訳した数
  n_c          部分の限定で、with が個体のものの数
  n_c_ready    そのうち、動詞の表示語が「になる」で終わるものの数
  n_c_translated  n_c_ready のうち句を訳した数
  n_no_with    部分の限定で、with を持たないものの数
  n_verb_form  部分の限定で、with はあるが動詞の表示語が「になる」で終わらないものの数
  py_T         T2 の法則 part_display_explicit の誤りの数
  new_T        T2 の誤りのうち、O0 にないものの数
  crash        プローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    n_with_disp = n_with、n_c_translated = n_c_ready、py_T = 0、new_T = 0 なら支持
      （with が指すものはどれも表示語を持ち、それを読めば with が個体の限定も訳せる。#459 の (c) は測り方の見落とし）。
    n_with_disp < n_with なら反証（表示語を持たないものを with が指している）。
    それ以外は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: #459 の結果は書き換えない（あちらの反証は、(a)・(b) だけでも成り立つ）。
行（sys_with_needs_display.json）:
  "summary 要約": 上の量
  "texts": 表示語のない with（先頭 20）、with が個体で訳した句（先頭 20）、訳せなかった部分の限定と原因（先頭 30）、new_T の文（先頭 10）

使い方:
  python exp/experiments/sys_with_needs_display_fix.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_with_needs_display_fix.json"
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
    T._tree = {"with": [], "with_disp": [], "target": [], "translated": {}, "c": [], "c_ready": [], "c_translated": [], "why": {}}
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
            if not _vd.endswith("になる"):
                T._tree["why"][_key] = "verb_form " + _vd
                continue
            if not _wd:
                T._tree["why"][_key] = "no_display " + _m["with"]
                continue
            _s = _vd.removesuffix("になる")
            _say = (f"の{_s}でない" if _m.get("neg") else f"の{_s}である") if _r == "part" else (f"を{_s}に持たない" if _m.get("neg") else f"を{_s}に持つ")
            _m["display"] = _wd + _say
            T._tree["translated"][_key] = _m["display"]
            if _ind:
                T._tree["c_translated"].append(_key)
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
    summary["n_with"] = len(g("with"))
    summary["n_with_disp"] = len(g("with_disp"))
    summary["n_target"] = len(g("target"))
    summary["n_translated"] = len(tree.get("translated") or {})
    summary["n_c"] = len(g("c"))
    summary["n_c_ready"] = len(g("c_ready"))
    summary["n_c_translated"] = len(g("c_translated"))
    why = tree.get("why") or {}
    summary["n_no_with"] = sum(v == "no_with" for v in why.values())
    summary["n_verb_form"] = sum(v.startswith("verb_form") for v in why.values())
    summary["py_T"] = sum(LAW in e for e in t["errors"])
    new = [e for e in t["errors"] if e not in o0["errors"]]
    summary["new_T"] = len(new)
    summary["crash"] = int(any(e.startswith("probe failed") for p in (o0, t) for e in p["errors"]) or t["tree"] is None)
    disp = set(g("with_disp"))
    texts["with without display"] = [w for w in g("with") if " ".join(w.split()[:2]) not in disp][:20]
    texts["c translated"] = [f"{k}: {tree['translated'][k]}" for k in g("c_translated")][:20]
    texts["untranslated"] = [f"{k}: {v}" for k, v in why.items()][:30]
    texts["new T"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
