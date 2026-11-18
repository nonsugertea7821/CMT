"""仮説 h_gloss_formula（に依存しない(最上位の置き場, 説明文)）を確かめる: 最上位の3つ（any, continuant, occurrent）の
説明文（gloss）の中身を、式に移せるか。結果を見る前に、この説明と手順と判定と、移す先の式（候補）を登録した（issue #141）。

説明文を節に分ける（登録の時点で固定）:
  any         a_range    自分が動く範囲そのもの
              a_free     何も限定しない
  continuant  c_same     時間を通じて同一性を保つ
              c_exists   存在するもの
  occurrent   o_happen   時間の中で起こる
              o_unfold   展開する

節ごとの候補（ノードの定義に足す式。今の文法 syntax.yaml の語だけで書く。登録のときに書いた）:
  a_free     {}（表示語のほかに何も持たない。限定のない種類）
  c_same     mod: {of: [v_stage, to], neg: true}（時間的な部分を持たない。BFO の持続体の公理の形）
  o_happen   pre: [{is: exists, from: self, neg: true}], post: [{is: exists, from: self}]（在らなかったものが在るようになる）
  o_unfold   mod: {of: [v_stage, to]}（時間的な部分を持つ）
  a_range    候補なし。「自分（変数）が動く範囲」を、ノードの定義の語（mod・holds・pre・post）で述べる形を書けなかった。
  c_exists   候補なし。基礎の関係 exists は動詞でないので of で指せず、法則（v_require）で書くには、どの歩みでも在ることを
             述べる量化（歩みを動く変数）が今の文法にない。

確かめ方:
  体系のファイル（cscl.yaml, cscl/, exp/src, 結果のファイル）を一時の場所に写し、最上位のノードの行を書き換え、
  そこで型検査器（tc）を別のプロセスで走らせる。書き換えでは gloss を除き、候補の式を足す。
  型検査器の規則「最上位は gloss だけを持つ」の誤りは数えない（この仮説は、その規則を外すことを前提にする）。
  それ以外の誤りが 0 で、候補が使う語がすべて許した語（下）なら、その節は移せた（accepted = 1）。
  許した語: syntax の grammar の語、シグネチャと存在論の基礎の関係、シグネチャと存在論のノード、位置（from, to, new）、self、
  真偽と数。
  節ごとに一つずつ書き換えて走らせ、最後に全部の候補を同時に入れて走らせる（候補のない節は gloss ごと消える）。

行（sys_gloss_formula.json）:
  "clause <id>":   has_candidate, vocab_ok, n_errors（数えない規則を除いた tc の誤り）, accepted（0 か 1）
  "all 全部":       n_errors, accepted
  "summary 要約":   n_clauses, n_accepted, n_left = n_clauses − n_accepted

判定（ec が通るもとで）:
  n_left = 0 かつ 全部を入れたときに accepted = 1 なら支持（v_support）。
  n_left ≥ 1 なら反証（v_contradict）: 説明文には、今の文法の式に移せない中身が残る。
  そのほか（節ごとには移せるが、全部を入れると誤りが出る）は mixed。

登録の前に分かっていること（開示）:
  候補のない節が 2 つ（a_range, c_exists）あるので、反証は登録の時点で決まっている。この実験が測るのは、残る節が
  どれか（文法に欠けているものの記録）と、書いた候補が型検査を通るかどうか。
  候補が型検査を通っても、それが説明文と同じ意味かは機械では確かめていない。同じ意味だと読んだのは、登録したときの
  読み（上の括弧）で、利用者が確かめる。
  sys_tops と sys_w_from_frames（どちらも反証）で、生起体の名詞の多くが pre・post を持つ動詞に届かないのを見ている。
  o_happen の候補は、生起体の下のすべての動詞を動的にする（静的な動詞を関係として分ける h_w_from_frames の読みとぶつかる）。
  それでも、ここでの判定は型検査を通るかだけで決める。

使い方:
  python exp/experiments/sys_gloss_formula.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
TOP_RULE = "最上位は gloss だけを持つ"

LINES = {
    "any": ("cscl/library/signature/signature.yaml",
            "  any: {display: 何でも, gloss: 自分が動く範囲そのもの。何も限定しない, many: true}",
            "  any: {display: 何でも, many: true"),
    "continuant": ("cscl/library/ontology/ontology.yaml",
                   "  continuant: {display: 持続体, gloss: 時間を通じて同一性を保って存在するもの}",
                   "  continuant: {display: 持続体"),
    "occurrent": ("cscl/library/ontology/ontology.yaml",
                  "  occurrent: {display: 生起体, gloss: 時間の中で起こり、展開するもの}",
                  "  occurrent: {display: 生起体"),
}
CLAUSES = {
    "a_range": ("any", None),
    "a_free": ("any", ""),
    "c_same": ("continuant", "mod: {of: [v_stage, to], neg: true}"),
    "c_exists": ("continuant", None),
    "o_happen": ("occurrent", "pre: [{is: exists, from: self, neg: true}], post: [{is: exists, from: self}]"),
    "o_unfold": ("occurrent", "mod: {of: [v_stage, to]}"),
}


def allowed_words():
    words = {"from", "to", "new", "self", "true", "false"}
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


def vocab_ok(cand, words):
    if not cand:
        return True
    return all(isinstance(a, (bool, int, float)) or a in words for a in atoms(yaml.safe_load("{" + cand + "}")))


def run_tc(patch):
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        shutil.copy(ROOT / "cscl.yaml", t / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", t / "cscl")
        shutil.copytree(ROOT / "exp/src", t / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", t / "exp/experiments/results")
        by_file = {}
        for top, cands in patch.items():
            f, old, head = LINES[top]
            body = ", ".join(c for c in cands if c)
            by_file.setdefault(f, []).append((old, head + (", " + body if body else "") + "}"))
        for f, subs in by_file.items():
            p = t / f
            s = p.read_text(encoding="utf-8")
            for old, new in subs:
                assert s.count(old) == 1, old
                s = s.replace(old, new)
            p.write_text(s, encoding="utf-8")
        r = subprocess.run([sys.executable, str(t / "cscl/bootstrap/type_checker/type_checker.py")],
                           cwd=t, capture_output=True, text=True)
    errs = [ln[3:] for ln in r.stdout.splitlines() if ln.startswith(" - ")]
    if r.returncode != 0 and not errs:
        errs = ["tc が誤りの一覧なしに失敗: " + (r.stderr.strip().splitlines() or ["?"])[-1]]
    return [e for e in errs if TOP_RULE not in e]


def main():
    words = allowed_words()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows, detail = {}, {}
    for cid, (top, cand) in CLAUSES.items():
        if cand is None:
            rows[f"clause {cid}"] = {"has_candidate": 0, "vocab_ok": 0, "n_errors": 0, "accepted": 0}
            continue
        errs = run_tc({top: [cand]})
        ok = vocab_ok(cand, words)
        rows[f"clause {cid}"] = {"has_candidate": 1, "vocab_ok": int(ok), "n_errors": len(errs),
                                 "accepted": int(ok and not errs)}
        detail[cid] = errs[:20]
    allp = {}
    for top in LINES:
        allp[top] = [c for (t, c) in CLAUSES.values() if t == top and c]
    errs = run_tc(allp)
    rows["all 全部"] = {"n_errors": len(errs), "accepted": int(not errs)}
    detail["all"] = errs[:20]
    n_acc = sum(r["accepted"] for k, r in rows.items() if k.startswith("clause "))
    rows["summary 要約"] = {"n_clauses": len(CLAUSES), "n_accepted": n_acc, "n_left": len(CLAUSES) - n_acc}
    (OUT / "sys_gloss_formula.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_gloss_formula.py", "_commit": commit, "rows": rows, "errors": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")
    for k, r in rows.items():
        print(k, r)
    for k, e in detail.items():
        if e:
            print(k, e[:5])
    left = rows["summary 要約"]["n_left"]
    print("判定:", "支持" if left == 0 and rows["all 全部"]["accepted"] else "反証" if left else "mixed")


if __name__ == "__main__":
    main()
