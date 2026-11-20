"""仮説 h_mod_phrase_any_verb（限定の句は、部分の動詞に限らず、動詞の位置から作れる: v_depend(syntax.display, syntax.position)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: #471 で、検査器は部分の限定 99 の句を限定の式から作る（mod_phrases）。ほかの動詞の限定には句がない。
  名前を付けた限定（{extends: quality, of: [...], with: ...} の個体）には、手で書いた表示語がある
  （例: 「実行するへ述べる（始点）」「モデルが発話する（終点）」「固定されている」）。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  検査器の syntax_facts で、mod_phrases の句がない限定にも、次の一つの型で句を作り、限定の文の表示語として書く:
    V = 動詞の表示語、W = 相手の表示語（with があればその表示語。なければ相手を書かない）、
    位置の語 = from なら「始点」、to なら「終点」、new なら「新しくできるもの」、否定なら位置の語の前に「否定」を足す。
    句 = (W があれば W + 助詞) + V + 「（」+ (否定なら「否定」+「、」) + 位置の語 + 「）」、助詞は from なら「へ」、to なら「が」、new なら「から」。
  相手の表示語は #468 と同じ探し方（ノード、なければ個体）。動詞は名前で読まず、限定の of の動詞をそのまま使う。
対象: 動詞でないノードの限定（mod の要素）と、名前を付けた限定のノード（of を持つ、動詞でないノード）。
数える量（T: 変えた写し）:
  n_target       対象の数
  n_part         そのうち mod_phrases の句がある数（部分の限定）
  n_other        それ以外の数
  n_other_phrase それ以外のうち、句を作れた数（V の表示語があり、with があるなら W の表示語がある）
  n_no_disp      作れなかった数（V か W の表示語がない）
  n_named        名前を付けた限定のノードの数
  n_named_agree  そのうち、この型の句が手で書いた表示語と一字一句同じ数（記述。判定に使わない）
  new_T          T にあって、変えない写し（O0）にない誤りの数
  crash          プローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    n_other_phrase = n_other（n_no_disp = 0）かつ new_T = 0 なら支持
      （どの動詞の限定も、動詞と位置と相手の表示語だけから句を作れ、検査は変わらない）。
    n_no_disp ≥ 1 か new_T ≥ 1 なら反証。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: 句の日本語の自然さ（助詞と態の選び方）は問わない（ロードマップ b、h_case_frame_by_signature は反証済み）。
  n_named_agree は、手で書いた名前を付けた限定の表示語が、すでにこの型に従っているかの記述。
行（sys_mod_phrase_any_verb.json）:
  "summary 要約": 上の量
  "texts": 作った句の例（先頭 15）、作れなかった限定と原因（先頭 20）、型と食い違う名前を付けた限定（型の句 / 手の表示語、先頭 20）、new_T の文（先頭 10）

使い方:
  python exp/experiments/sys_mod_phrase_any_verb.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_mod_phrase_any_verb.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
ANCHOR = """        phrases = mod_phrases(self)   # 部分の限定の句は、限定の式から作り、限定の表示語として書く
"""
ADD = """        self._apv = {"target": [], "part": [], "other": [], "other_phrase": {}, "no_disp": {}, "named": [], "named_agree": [], "named_diff": []}
        _ind = dict(self.O.get("individuals") or {})
        for _name, _ in lib_and_domain_files():
            _ind |= (load(_name) or {}).get("individuals") or {}
        def _disp(_x):
            if not isinstance(_x, str):
                return None
            if (self.N.get(self.q(_x)) or {}).get("display"):
                return self.N[self.q(_x)]["display"]
            for _k in (_x, _x.split(".")[-1]):
                if isinstance(_ind.get(_k), dict) and isinstance(_ind[_k].get("display"), str):
                    return _ind[_k]["display"]
            return None
        def _phrase(_m):
            if not isinstance(_m, dict) or not isinstance(_m.get("of"), list) or len(_m["of"]) != 2:
                return None, "no_of"
            _v, _p = self.q(_m["of"][0]), _m["of"][1]
            _vd = (self.N.get(_v) or {}).get("display")
            if not _vd:
                return None, "no_verb_display " + str(_v)
            _w = _m.get("with")
            _wd = _disp(_w) if isinstance(_w, str) else None
            if isinstance(_w, str) and not _wd:
                return None, "no_with_display " + _w
            _pw = {"from": "始点", "to": "終点", "new": "新しくできるもの"}.get(_p, str(_p))
            _pa = {"from": "へ", "to": "が", "new": "から"}.get(_p, "")
            return (f"{_wd}{_pa}" if _wd else "") + _vd + "（" + ("否定、" if _m.get("neg") else "") + _pw + "）", None
        _dump = lambda x: yaml.safe_dump(x, sort_keys=True, allow_unicode=True).strip()
        self._apv_facts = {}
        for _nid, _n in self.N.items():
            if self.is_verb(_nid):
                continue
            _items = [(f"{_nid} {_i}", _m, (_nid, _i)) for _i, _m in enumerate(_n.get("mod") or []) if isinstance(_m, dict)]
            if "of" in _n:
                _items.append((f"{_nid} named", {k: _n[k] for k in ("of", "with", "neg") if k in _n}, None))
                self._apv["named"].append(_nid)
            for _key, _m, _pos in _items:
                self._apv["target"].append(_key)
                if _pos is not None and _pos in phrases:
                    self._apv["part"].append(_key)
                    continue
                self._apv["other"].append(_key)
                _ph, _why = _phrase(_m)
                if _ph is None:
                    self._apv["no_disp"][_key] = _why
                    continue
                self._apv["other_phrase"][_key] = _ph
                if _pos is not None:
                    self._apv_facts[_dump(_m)] = _ph
                else:
                    (self._apv["named_agree"] if _ph == _n.get("display") else self._apv["named_diff"]).append(f"{_nid}: {_ph} / {_n.get('display')}")
"""
FACT_OLD = """                if (nid, i_m) in phrases:
                    add("display", t, phrases[(nid, i_m)])
"""
FACT_NEW = """                if (nid, i_m) in phrases:
                    add("display", t, phrases[(nid, i_m)])
                elif t in getattr(self, "_apv_facts", {}):
                    add("display", t, self._apv_facts[t])
"""

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
print(json.dumps({"errors": errs, "apv": getattr(T, "_apv", None) if T is not None else None}, ensure_ascii=False))
'''


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]], "apv": None}


def patch(p, old, new):
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, old
    p.write_text(s.replace(old, new), encoding="utf-8")


def run(change):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")
        if change:
            patch(d / TC, ANCHOR, ANCHOR + ADD)
            patch(d / TC, FACT_OLD, FACT_NEW)
        return probe(d)


def main():
    o0, t = run(False), run(True)
    a = t["apv"] or {}
    g = lambda k: a.get(k) or []
    summary, texts = {}, {}
    summary["n_target"] = len(g("target"))
    summary["n_part"] = len(g("part"))
    summary["n_other"] = len(g("other"))
    summary["n_other_phrase"] = len(g("other_phrase"))
    summary["n_no_disp"] = len(g("no_disp"))
    summary["n_named"] = len(g("named"))
    summary["n_named_agree"] = len(g("named_agree"))
    new = [e for e in t["errors"] if e not in o0["errors"]]
    summary["new_T"] = len(new)
    summary["crash"] = int(any(e.startswith("probe failed") for p in (o0, t) for e in p["errors"]) or t["apv"] is None)
    texts["phrases"] = [f"{k}: {v}" for k, v in list((a.get("other_phrase") or {}).items())[:15]]
    texts["no phrase"] = [f"{k}: {v}" for k, v in list((a.get("no_disp") or {}).items())[:20]]
    texts["named differ"] = g("named_diff")[:20]
    texts["new T"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
