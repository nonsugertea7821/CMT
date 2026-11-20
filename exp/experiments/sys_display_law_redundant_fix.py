"""仮説 h_display_law_redundant を確かめる手順の訂正（sys_display_law_redundant.py の訂正）。
結果を見る前に、この説明と手順を登録した。

訂正の開示: 元の手順は crash = 1 で、何も測れなかった（results/sys_display_law_redundant.json に開示）。
  原因: 写しに差し込む T._role の 2 行（neg でない部分の限定のノードの向きを覚える）の字下げが、ループの外にずれていた。
  そのため build が UnboundLocalError で落ちた。
訂正: その 2 行の字下げをループの中に直す。ほかの手順・数える量・判定は、元の手順（下）のまま。
  行は sys_display_law_redundant_fix.json に書く。

元の手順:
仮説 h_display_law_redundant（表示語は、法則に頼らない: v_not_depend(syntax.display, syntax.laws)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: 表示語の法則（syntax.yaml の規則 disp_vague・disp_dir_part・disp_dir_whole）は、手で書いた表示語が、限定の式と食い違う
  向き（部分なのに「…を部分に持つ」と言う、など）を言わないかを見る。#459・#464・#465・#468 で、部分の限定 99 の句は、
  すべて限定の式から訳せた。句が式から来るなら、式と食い違う句は作れず、法則は何も捕まえない（要らない）はず。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  - 句の訳し方は #468（sys_mod_phrase_without_with_fix.py）と同じものを、検査器の syntax_facts の初めに差し込む。
  - 条件は三つの切り替えの組み合わせ:
      PH    says_* の文を、訳した句から作る（句がなければノードの表示語）。PH なしは今のまま（ノードの表示語）。
      MUT   部分の限定（neg でないもの）を持つノードの表示語に、逆の向きの言い方（部分のノードなら「を<語幹>に持つ」、
            全体のノードなら「の<語幹>である」、語幹は part_words の先頭）を書き足す。わざと食い違わせた表示語。
      NOLAW 文法から規則 disp_vague・disp_dir_part・disp_dir_whole（個体とその v_assume・v_require）を除く。
  - 走らせるもの（どれも tc.build() を 1 回）: O0（なし）、O_mut（MUT）、T（PH）、T_mut（PH+MUT）、T_nolaw（PH+NOLAW）、
    T_mut_nolaw（PH+MUT+NOLAW）。
数える量:
  n_mut            書き足したノードの数
  caught_O_mut     O_mut の「法則 disp_」の誤りの数（法則が、手で書いた食い違いを捕まえること）
  caught_T_mut     T_mut の「法則 disp_」の誤りの数
  caught_T         T の「法則 disp_」の誤りの数
  diff_T_nolaw     T と T_nolaw の誤りの集合の対称差の大きさ
  diff_T_mut_nolaw T_mut と T_mut_nolaw の誤りの集合の対称差の大きさ
  diff_T_O0        T と O0 の誤りの集合の対称差の大きさ
  new_T_mut        T_mut にあって T にない誤りの数（書き足した表示語が、ほかの法則に効くか）
  crash            プローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    caught_O_mut = 0 なら、書き足しが効いていない。手順の誤りとして開示し、状態を変えない。
    caught_O_mut ≥ 1 で、caught_T_mut = 0、caught_T = 0、diff_T_nolaw = 0、diff_T_mut_nolaw = 0、diff_T_O0 = 0 なら支持
      （句を式から作れば、手で書いた表示語が食い違っても法則は何も捕まえず、法則を除いても検査の結果は変わらない）。
    caught_T_mut ≥ 1 か diff_T_nolaw ≥ 1 か diff_T_mut_nolaw ≥ 1 なら反証。
    それ以外は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
  new_T_mut は判定に使わない（表示語をほかの法則が読むかの観察）。
範囲: 法則を体系から実際に除くかは、この実験では決めない（除く変更は別の PR で手で見る）。
行（sys_display_law_redundant.json）:
  "summary 要約": 上の量
  "texts": 条件ごとの「法則 disp_」の誤りの文（先頭 5）、対称差の文（先頭 10）、new_T_mut の文（先頭 10）

使い方:
  python exp/experiments/sys_display_law_redundant.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_display_law_redundant_fix.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
RULES = ("disp_vague", "disp_dir_part", "disp_dir_whole")
READ_OLD = """            disp = n.get("display") or ""
"""
READ_NEW = """            _nd = n.get("display") or ""
            if __import__("os").environ.get("MUT") and nid in self._role:
                _nd = _nd + _pw["to" if self._role[nid] == "part" else "from"][0]
            disp = (self._ph.get(nid) if __import__("os").environ.get("PH") else None) or _nd
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
        T._ph, T._role = {}, {}
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
                if not _m.get("neg"):
                    T._role.setdefault(_nid, _r)
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
role = getattr(T, "_role", None) if T is not None else None
print(json.dumps({"errors": errs, "role": role}, ensure_ascii=False))
'''


def probe(d, env):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True, env={**os.environ, **env})
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]], "role": None}


def patch(p, old, new):
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, old
    p.write_text(s.replace(old, new), encoding="utf-8")


def run(ph, mut, nolaw):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")
        patch(d / TC, READ_OLD, READ_NEW)
        patch(d / TC, TR_ANCHOR, TR_ANCHOR + TR_ADD)
        if nolaw:
            p = d / SYN
            lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
            keep = [l for l in lines if not any(f" {r}:" in l or f"from: {r}," in l for r in RULES)]
            assert len(lines) - len(keep) == 3 + 14, len(lines) - len(keep)
            p.write_text("".join(keep), encoding="utf-8")
        env = {k: "1" for k, on in (("PH", ph), ("MUT", mut)) if on}
        return probe(d, env)


def main():
    R = {name: run(*flags) for name, flags in {
        "O0": (False, False, False), "O_mut": (False, True, False), "T": (True, False, False),
        "T_mut": (True, True, False), "T_nolaw": (True, False, True), "T_mut_nolaw": (True, True, True)}.items()}
    caught = lambda k: [e for e in R[k]["errors"] if LAW in e]
    sd = lambda a, b: sorted(set(R[a]["errors"]) ^ set(R[b]["errors"]))
    summary, texts = {}, {}
    summary["n_mut"] = len(R["O_mut"]["role"] or {})
    summary["caught_O_mut"] = len(caught("O_mut"))
    summary["caught_T_mut"] = len(caught("T_mut"))
    summary["caught_T"] = len(caught("T"))
    summary["diff_T_nolaw"] = len(sd("T", "T_nolaw"))
    summary["diff_T_mut_nolaw"] = len(sd("T_mut", "T_mut_nolaw"))
    summary["diff_T_O0"] = len(sd("T", "O0"))
    new = [e for e in R["T_mut"]["errors"] if e not in R["T"]["errors"]]
    summary["new_T_mut"] = len(new)
    summary["crash"] = int(any(e.startswith("probe failed") for r in R.values() for e in r["errors"]) or any(r["role"] is None for r in R.values()))
    for k in R:
        texts[f"caught {k}"] = caught(k)[:5]
    for a, b in (("T", "T_nolaw"), ("T_mut", "T_mut_nolaw"), ("T", "O0")):
        texts[f"diff {a} {b}"] = sd(a, b)[:10]
    texts["new T_mut"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
