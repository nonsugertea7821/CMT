"""仮説 h_mod_phrase_without_with を確かめる手順の訂正（sys_mod_phrase_without_with.py の訂正）。
結果を見る前に、この説明と手順を登録した。

訂正の開示: 元の手順（sys_mod_phrase_without_with.py）は、写しを書き換える段で止まり、何も測らなかった（結果のファイルなし）。
  原因: 元の手順は #465 の写しを土台にした。その写しは、表示語の法則が検査器の Python（part_display_explicit）にあった時の
  差し込み位置を前提にしている。#455 で、その法則は文法の規則（syntax.yaml の disp_vague・disp_dir_part・disp_dir_whole）に移り、
  検査器は表示語から says_vague・says_part_side・says_whole_side の文を作り、規則がそれを読むようになった。差し込み位置がなくなっていた。
訂正した操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  - 句の訳し方（元の手順と同じ: with があればその表示語、なければ相手の種類の表示語 + 語幹の言い方）を、検査器の syntax_facts の
    初めに差し込む。部分か全体かの読み（role）は、#465 と同じ式（holds の part と位置）で写しの中で計る。
  - 訳した句は、限定に display を足すのでなく、ノードごとの句として持つ（法則 single でノードの限定は一つ）。
    says_* の文は、ノードの句があればそれから、なければノードの表示語から作る。限定に display を足さないので、文法の書き換えはしない。
  - 法則の誤りは「法則 disp_」で数える（py_T）。
数える量と判定は、元の手順のまま。

使い方:
  python exp/experiments/sys_mod_phrase_without_with_fix.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_mod_phrase_without_with_fix.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
READ_OLD = """            disp = n.get("display") or ""
"""
READ_NEW = """            disp = (getattr(self, "_ph", {}) or {}).get(nid) or n.get("display") or ""
"""
TR_ANCHOR = """        add = lambda rel, *xs: out.append((rel, tuple(xs)))
"""
TR_ADD = """        T = self
        def parts(verb):
            return {(h["from"], h["to"]) for h in T.end(verb, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"} if verb in T.N else set()
        def role(m):
            if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2:
                return None
            v, pos = T.q(m["of"][0]), m["of"][1]
            wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
            P = parts(v)
            return "part" if (pos, wpos) in P else "whole" if (wpos, pos) in P else None
        T._ph = {}
        _IND = dict(T.O.get("individuals") or {})
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
                T._ph.setdefault(_nid, _wd + _say)
                T._tree["translated"][_key] = _wd + _say
                if _ind:
                    T._tree["c_translated"].append(_key)
                if _key in T._tree["no_with_kind"]:
                    T._tree["no_with_translated"].append(_key)
                if not _vd.endswith("になる"):
                    T._tree["verb_form_translated"].append(_key)
"""
LAW = "法則 disp_"

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
