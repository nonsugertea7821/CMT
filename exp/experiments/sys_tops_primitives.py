"""仮説 h_tops_from_primitives（依存する(最上位の置き場, 歩みを動く量化・種類について在ることを述べる場所・変数の範囲)）を
確かめる: 三つを書く形を文法に足すと、最上位の3つ（any, continuant, occurrent）の説明文の 6 節が、どれも式になるか。
結果を見る前に、この説明と、足す形と、節ごとの式と、判定を登録した（issue #191）。

足す形（この登録のあとの commit で、文法と型検査器に入れる）:
  種類について在ることを述べる場所   ノードの定義の原子で、項に self を使える（その種類の個体を指す）。
                                    位置（from, to, new）の一覧は変えず、新しい3つの欄の中だけで許す。
  歩みを動く量化                   always: [原子]            どの歩みでも成り立つ
                                    sometime: [{pre: [原子], post: [原子]}]   ある歩みで、pre から post に変わる（並びの各要素が一つの変化）
  変数の範囲                       ranges: <変数>            その種類は、変数が動く範囲そのもの
  原子は、基礎の関係と項（self だけ。ノードの定義には端がないので from・to・new は使わない）で書く。
  型検査器の「最上位は gloss だけを持つ」は、「最上位と any は display・many・mod・always・sometime・ranges と gloss だけを持つ」に変える。

節と式（登録の時点で固定。h_gloss_formula と同じ節）:
  any         a_range    自分が動く範囲そのもの         ranges: self
              a_free     何も限定しない                 （display と many と ranges のほかに何も持たない）
  continuant  c_same     時間を通じて同一性を保つ        mod: {of: [v_stage, to], neg: true}（h_gloss_formula で通った式）
              c_exists   存在するもの                   always: [{is: exists, from: self}]
  occurrent   o_happen   時間の中で起こる               sometime の要素 {pre: [{is: exists, from: self, neg: true}], post: [{is: exists, from: self}]}
              o_unfold   展開する                       sometime の要素 {pre: [{is: exists, from: self}], post: [{is: exists, from: self, neg: true}]}
  o_unfold の読み: 始まって終わる（在るようになり、在らなくなる）。h_gloss_formula の「時間的な部分を持つ」は ontology.process と
  重なったので、別の読みにした。読みを変えたことは開示する。

確かめ方（体系をそのまま読む。写しは作らない）:
  節ごとに: その最上位のノードの定義に、上の式がそのまま入っている（has_formula）。a_free は、ノードが display・many・ranges の
  ほかを持たないこと。
  vocab_ok: 式が使う語が、文法の語、シグネチャと存在論の基礎の関係とノード、self、真偽のどれか。
  gloss_gone: 3つのどれも gloss を持たない（全体で一つ）。
  tc の誤りの数（errors）。
  accepted = has_formula かつ vocab_ok かつ errors = 0 かつ gloss_gone。

行（sys_tops_primitives.json）:
  "clause <id>":  has_formula, vocab_ok, accepted
  "summary 要約":  n_clauses, n_accepted, n_left, gloss_gone, errors

判定（ec が通るもとで）:
  n_left = 0 なら支持（v_support）: 三つの形があれば、最上位の説明文はすべて式に移る。
  n_left ≥ 3 なら反証（v_contradict）。
  そのほか（1〜2 節残る）は mixed。

開示:
  この確かめは、最上位の意味が三つの形で「書ける」かを見る。式が説明文と同じ意味かは機械で確かめない（登録のときの読み）。
  また、ほかのノードの置き場が、この式から導かれるか（sys_tops, sys_w_from_frames で反証された問い）は、この実験の外。
  足す形は私が設計し、型検査器の変更は私が書く。型検査器が新しい欄を「受け入れるだけ」なら支持は易しい。
  そのため、型検査器は新しい欄の原子を check_state と同じ規則（基礎の関係・項数・項の語）で検査することにする。
  c_exists の always は、宣言された個体が減らない（閉じた世界、sys_tops の D1）ことと合う読み。走りの中で作られる個体
  （v_design の post）とどう合うかは、確かめていない。

使い方:
  python exp/experiments/sys_tops_primitives.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
OUT = ROOT / "exp/experiments/results"

EX_NOT = {"is": "exists", "from": "self", "neg": True}
EX = {"is": "exists", "from": "self"}
TOP_FILES = {"any": "cscl/library/signature/signature.yaml",
             "continuant": "cscl/library/ontology/ontology.yaml",
             "occurrent": "cscl/library/ontology/ontology.yaml"}
CLAUSES = {
    "a_range": ("any", lambda n: n.get("ranges") == "self"),
    "a_free": ("any", lambda n: set(n) <= {"display", "many", "ranges"}),
    "c_same": ("continuant", lambda n: n.get("mod") == {"of": ["v_stage", "to"], "neg": True}),
    "c_exists": ("continuant", lambda n: EX in (n.get("always") or [])),
    "o_happen": ("occurrent", lambda n: {"pre": [EX_NOT], "post": [EX]} in (n.get("sometime") or [])),
    "o_unfold": ("occurrent", lambda n: {"pre": [EX], "post": [EX_NOT]} in (n.get("sometime") or [])),
}
FIELDS = {"any": ("ranges",), "continuant": ("mod", "always"), "occurrent": ("sometime",)}


def raw_tops():
    out = {}
    for top, f in TOP_FILES.items():
        out[top] = yaml.safe_load((ROOT / f).read_text(encoding="utf-8"))["nodes"][top]
    return out


def allowed_words():
    words = {"self", True, False}
    syn = yaml.safe_load((ROOT / "cscl/library/syntax/syntax.yaml").read_text(encoding="utf-8"))
    for v in syn["grammar"].values():
        words |= set(v)
    for f in ("cscl/library/signature/signature.yaml", "cscl/library/ontology/ontology.yaml"):
        d = yaml.safe_load((ROOT / f).read_text(encoding="utf-8"))
        words |= set(d.get("base") or {}) | set(d.get("nodes") or {})
    return words


def atoms(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from atoms(v)
    elif isinstance(x, list):
        for v in x:
            yield from atoms(v)
    else:
        yield x


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        tc.check_all()
    errors = len(tc.errors)
    tops = raw_tops()
    words = allowed_words()
    gloss_gone = int(all("gloss" not in n for n in tops.values()))
    rows = {}
    for cid, (top, pred) in CLAUSES.items():
        n = tops[top]
        has = int(bool(pred(n)))
        body = {k: n[k] for k in FIELDS[top] if k in n}
        ok = int(all(a in words for a in atoms(body)))
        rows[f"clause {cid}"] = {"has_formula": has, "vocab_ok": ok,
                                 "accepted": int(has and ok and errors == 0 and gloss_gone)}
    n_acc = sum(r["accepted"] for r in rows.values())
    rows["summary 要約"] = {"n_clauses": len(CLAUSES), "n_accepted": n_acc, "n_left": len(CLAUSES) - n_acc,
                          "gloss_gone": gloss_gone, "errors": errors}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_tops_primitives.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_tops_primitives.py", "_commit": commit, "rows": rows,
         "tops": tops, "tc_errors": tc.errors[:20]}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, r in rows.items():
        print(k, r)
    if tc.errors:
        print(tc.errors[:5])
    left = rows["summary 要約"]["n_left"]
    print("判定:", "支持" if left == 0 else "反証" if left >= 3 else "mixed")


if __name__ == "__main__":
    main()
