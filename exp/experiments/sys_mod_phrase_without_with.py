"""仮説 h_mod_phrase_without_with（with のない限定の句は、数量化から訳す: v_depend(syntax.display, syntax.quant)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: #459・#464・#465 で、部分の限定 99 のうち with を持つ 92 の句を、限定の式から訳せた。残る 7 は with のない限定
  （例: ontology.continuant {of: [v_stage, to], neg: true}、subj.warehouse {of: [v_store, to]}）。
  with のない限定は、相手を名指さず、「その位置に来る種類のどれか」と存在で量化して読む（neg なら「どれも…ない」）。
  その種類は、動詞の定義が決める: 第三のものを作る動詞なら new_kind、そうでなければ限定の位置の反対の位置の種類（T.end）。
  ここでは、with のない限定の句を、この相手の種類の表示語から訳せるかを見る。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  #465 の写し（grammar の mod に display、法則は m の display を読む、with の表示語はノードと個体から探す、
  語幹は動詞の上位か holds から取る）に、with のない限定の訳し方を足す:
    相手の種類 = new_kind があればそれ、なければ T.end(動詞, 反対の位置)。句 = 表示(相手の種類) + 言い方（#459 と同じ。neg なら否定）。
    存在の量化は句に語を足さず、種類の名で読む（「商品を部分に持つ」= どれかの商品を部分に持つ。neg の「生起体を時間的な部分に持たない」= どの生起体も持たない）。
走らせるもの: O0（今のまま）と T（変えた写し）。どちらも tc.build() を 1 回。
数える量（T で）:
  n_target              部分の限定（動詞でないノード）の数
  n_translated          句を訳した数
  n_no_with             with のない部分の限定の数
  n_no_with_translated  そのうち句を訳した数
  n_no_kind             相手の種類か、その表示語を取れなかった数
  n_untranslated        訳せなかった部分の限定の数（原因を問わず）
  py_T / new_T          T の法則 part_display_explicit の誤りの数 / O0 にない誤りの数
  crash                 プローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    n_no_with_translated = n_no_with、n_translated = n_target、py_T = 0、new_T = 0 なら支持
      （with のない限定も、存在の量化と動詞の定義の種類から句を訳せ、部分の限定の句はすべて式から訳せる）。
    n_no_kind ≥ 1 か new_T ≥ 1 なら反証。
    それ以外は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: 存在の量化を句の語（「どれか」「何か」）で言い表すかは決めない（日本語の自然さ、ロードマップ b の範囲）。訳した句は texts に残す。
行（sys_mod_phrase_without_with.json）:
  "summary 要約": 上の量
  "texts": with のない限定の訳した句と相手の種類（先頭 20）、訳せなかった限定と原因（先頭 30）、new_T の文（先頭 10）

使い方:
  python exp/experiments/sys_mod_phrase_without_with.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_mod_phrase_without_with.json"
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
    T._tree = {"with": [], "with_disp": [], "target": [], "translated": {}, "c": [], "c_ready": [], "c_translated": [], "why": {}, "by_ancestor": [], "by_holds": [], "verb_form": [], "verb_form_translated": [], "no_with": [], "no_with_kind": {}, "no_with_translated": []}
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
                T._tree["no_with"].append(_key)
                _nk = T.end(_v, "new_kind")
                _wk = _nk if _nk else T.end(_v, "to" if _m["of"][1] == "from" else "from")
                _wd = _disp(_wk) if isinstance(_wk, str) else None
                if not _wd:
                    T._tree["why"][_key] = "no_kind " + str(_wk)
                    continue
                T._tree["no_with_kind"][_key] = _wk
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
            if _key in T._tree["no_with_kind"]:
                T._tree["no_with_translated"].append(_key)
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
    tr = tree.get("translated") or {}
    summary["n_target"] = len(g("target"))
    summary["n_translated"] = len(tr)
    summary["n_no_with"] = len(g("no_with"))
    summary["n_no_with_translated"] = len(g("no_with_translated"))
    summary["n_no_kind"] = sum(v.startswith("no_kind") for v in why.values())
    summary["n_untranslated"] = len(why)
    summary["py_T"] = sum(LAW in e for e in t["errors"])
    new = [e for e in t["errors"] if e not in o0["errors"]]
    summary["new_T"] = len(new)
    summary["crash"] = int(any(e.startswith("probe failed") for p in (o0, t) for e in p["errors"]) or t["tree"] is None)
    texts["no with translated"] = [f"{k}: {tr[k]}（相手の種類 {(tree.get('no_with_kind') or {}).get(k)}）" for k in g("no_with_translated")][:20]
    texts["untranslated"] = [f"{k}: {v}" for k, v in why.items()][:30]
    texts["new T"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
