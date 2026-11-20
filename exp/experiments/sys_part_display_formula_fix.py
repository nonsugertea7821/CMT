"""仮説 h_part_display_from_formula（表示語を holds の式から訳せば、part_display_explicit は要らなくなる:
v_depend(syntax.display, syntax.holds)）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: 対の仮説 h_part_display_by_word_facts（#449、支持）は、法則を残したまま規則に移せることを示した。
  そこで Python に残ったのは、表示語の部分文字列を読んで言い方の文を作るところ。こちらは、表示語を式から訳せば、
  言い方と限定の向きは食い違いようがなく、法則も言い方の文も要らなくなるかを見る。
  訳した表示語が法則を満たすのは、訳し方からして当然（言い方を役割から選ぶため）。この手順で確かめるのは、
  体系の中の部分の限定を持つノードをすべて訳した表示語に置き換えても、ほかの検査が壊れないか（訳が体系の中で成り立つか）。
訳し方（部分の限定 m を持つ、動詞でないノード n ごと。役割は check_parts と同じ読み方で決める）:
  D(n) = （n の部分の限定ごとに、書いた順で）表示(with) + 言い方 ＋ 表示(上位)
    言い方: 役割が部分なら「の{語幹}である」、全体なら「を{語幹}に持つ」。neg の限定なら「の{語幹}でない」「を{語幹}に持たない」。
    語幹は、限定の動詞の表示語から「になる」を除いたもの（part_words と同じ）。
    表示(with) と 表示(上位) は、置き換える前の表示語を使う（入れ子に訳さない）。部分でない限定（at など）は訳に入れない。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  1. 写しで tc.build() を走らせ、対象のノードと D(n) を求める（版 B の誤りもここで数える）。
  2. 写しの yaml で、ノードを定義する行「  {短い名前}: {display: 旧, 」の旧を D(n) に置き換える（行が一つに定まるものだけ）。
  3. 置き換えた写しで tc.build() をもう一度走らせる。
数える量:
  n_target    部分の限定を持つ、動詞でないノードの数
  n_replaced  2 で置き換えられたノードの数
  py_B        置き換える前の、法則 part_display_explicit の誤りの数
  py_D        置き換えた後の、法則 part_display_explicit の誤りの数
  err_B       置き換える前の誤りの数
  new_D       置き換えた後の誤りのうち、置き換える前になかったものの数
  same_disp   置き換えた後に、ほかのノードと同じ表示語になったノードの数（Python で数える。検査の誤りとは別）
判定（事前に決める）:
  n_replaced = n_target、py_D = 0、new_D = 0 なら支持（式から訳した表示語で、体系の検査がそのまま通る）。
  n_replaced = n_target で、new_D ≥ 1 なら反証（訳した表示語が、ほかの検査を壊す。誤りの文を開示する）。
  n_replaced < n_target なら、手順の誤りとして開示し、状態を変えない。
  same_disp は判定に使わず、記録だけする（同じ表示語が誤りかは体系の検査が決める）。
範囲: 表示語を置き換えるのは写しだけ。法則を外すことは、この手順ではしない。
行（sys_part_display_formula.json）:
  "summary 要約": 上の量
  "texts": 訳の対（先頭 30）、置き換えた後の新しい誤りの文（先頭 10）

訂正（sys_part_display_formula_fix.py。最初の実行の結果を見た後、この訂正を走らせる前に登録した）:
  最初の実行は、プローブが例外で落ち（with が文字列でない限定で、表示 None に言い方を足した）、n_target=0、err_B=1 だった。
  訂正: 表示(x) は、x がノードならその表示語、文字列ならそのまま、x がない（None）なら空の文字列、それ以外は文字列にしたもの。
  上位がないときも空の文字列。プローブが落ちたら、その版の誤りに「probe failed」を数えるのは同じ。判定は変えない。
  加えて、プローブが落ちたかを crash_B・crash_D（落ちたら 1）で数え、どちらかが 1 なら手順の誤りとして開示する。
  結果は sys_part_display_formula_fix.json に書く（最初の結果のファイルは上書きしない）。

使い方:
  python exp/experiments/sys_part_display_formula_fix.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_part_display_formula_fix.json"

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
out = {"errors": errs, "derived": {}, "displays": {}}
if T is not None:
    out["displays"] = {k: n.get("display") for k, n in T.N.items() if n.get("display")}
    parts = lambda v: {(h["from"], h["to"]) for h in T.end(v, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"} if v in T.N else set()
    def role(m):
        if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2:
            return None
        v, pos = T.q(m["of"][0]), m["of"][1]
        wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
        P = parts(v)
        return "part" if (pos, wpos) in P else "whole" if (wpos, pos) in P else None
    disp = lambda x: "" if x is None else ((T.N.get(x) or {}).get("display") or x) if isinstance(x, str) else str(x)
    for nid, n in T.N.items():
        if T.is_verb(nid):
            continue
        words = []
        for m in n.get("mod") or []:
            r = role(m)
            if r is None:
                continue
            v = T.q(m["of"][0])
            stem = (T.N[v].get("display") or "").removesuffix("になる")
            w = (f"の{stem}でない" if m.get("neg") else f"の{stem}である") if r == "part" else (f"を{stem}に持たない" if m.get("neg") else f"を{stem}に持つ")
            words.append(disp(T.q(m["with"]) if isinstance(m.get("with"), str) else m.get("with")) + w)
        if words:
            out["derived"][nid] = "".join(words) + disp(T.up(nid))
print(json.dumps(out, ensure_ascii=False))
'''


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]], "derived": {}, "displays": {}}


def main():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")
        before = probe(d)
        derived = before["derived"]
        files = [p for p in list((d / "cscl").rglob("*.yaml")) + list((d / "exp/src").rglob("*.yaml"))]
        replaced = {}
        for nid, new in derived.items():
            short = nid.split(".")[-1]
            old = before["displays"].get(nid)
            line = f"  {short}: {{display: {old}, "
            hits = [p for p in files if p.read_text(encoding="utf-8").count(line) == 1]
            if len(hits) == 1 and sum(p.read_text(encoding="utf-8").count(line) for p in files) == 1:
                p = hits[0]
                p.write_text(p.read_text(encoding="utf-8").replace(line, f"  {short}: {{display: {new}, "), encoding="utf-8")
                replaced[nid] = (old, new)
        after = probe(d)
    disp_after = after["displays"]
    count = {}
    for v in disp_after.values():
        count[v] = count.get(v, 0) + 1
    new_errs = [e for e in after["errors"] if e not in before["errors"]]
    summary = {
        "n_target": len(derived),
        "n_replaced": len(replaced),
        "py_B": sum("法則 part_display_explicit" in e for e in before["errors"]),
        "py_D": sum("法則 part_display_explicit" in e for e in after["errors"]),
        "err_B": len(before["errors"]),
        "new_D": len(new_errs),
        "crash_B": int(any(e.startswith("probe failed") for e in before["errors"])),
        "crash_D": int(any(e.startswith("probe failed") for e in after["errors"])),
        "same_disp": sum(1 for nid in replaced if count.get(disp_after.get(nid), 0) > 1),
    }
    texts = {"pairs": [f"{k}: {o} → {n}" for k, (o, n) in list(replaced.items())[:30]],
             "not replaced": [k for k in derived if k not in replaced][:30],
             "new errors": new_errs[:10]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
