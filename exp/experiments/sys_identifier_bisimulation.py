"""h_identifier_by_bisimulation を確かめる: 循環を分割の細分（双模倣）で扱うと、衝突は予測した 4 類だけになるか。

仮説（claims.yaml）: v_depend(syntax.identifier, [signature_class, syntax.identifier])。
  登録（877ace5）の読み: h_identifier_by_expansion（#328）の 5 類の衝突のうち、region/warehouse は
  循環の途中の値を memo に残す手順の欠点による。循環を正しく扱えば、名前でしか分かれない
  相互再帰の組だけが残る。

手順（体系のファイルは変えない。tc.build() の T.N を読むだけ）:
  前の実験（sys_identifier_expansion）と同じく、ノードの値から display と gloss を除いて比べる。
  文字列が T.N のノードなら、名前の代わりに、そのノードがいま属する類の番号を置く。
  T.N のノードでない文字列（基礎の関係・位置・文法の語・値）は、そのまま残す。
  辞書は鍵の順、並びは要素の正規の形で並べ替える（前の実験と同じ）。
  分割の細分:
    初めは全ノードを 1 類にする。
    各回、各ノードの鍵 =（いまの類の番号, 上の正規の形）で分け直す。
    類の数が増えなくなったら止める。
  これは最大の双模倣で、たどり始める場所によらない。
  集計:
    n_nodes, n_classes, n_collide_class, n_collide_nodes, n_rounds, base_errors
    match_prediction  衝突の類の集合が、予測した 4 類と一致すれば 1
  予測した 4 類:
    {subj.approval, subj.payment}, {subj.v_approve, subj.v_pay},
    {syntax.derived, syntax.required}, {syntax.v_derive, syntax.v_require}
  行（sys_identifier_bisimulation.json）: "class <i>": {size, members}、"summary 要約": {...}
判定（事前に決める）: match_prediction が 1 なら支持。0 なら反証。

開示（結果を見る前に分かっていること）:
  - 前の実験の結果（5 類の衝突）を見たあとに立てた予測である。
  - region/warehouse が分かれると見る根拠は、land の mod が [v_located, from]、goods の mod が
    [v_sell, to] で、形が違うこと。
  - 型検査は 1 回だけ（軽い）。
使い方:
  python exp/experiments/sys_identifier_bisimulation.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_identifier_bisimulation.json"
DROP = ("display", "gloss")
PRED = [{"subj.approval", "subj.payment"}, {"subj.v_approve", "subj.v_pay"},
        {"syntax.derived", "syntax.required"}, {"syntax.v_derive", "syntax.v_require"}]


def main():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    base_errors = len(tc.errors)
    N = T.N
    names = sorted(N)
    cls = {q: 0 for q in names}

    def canon(x):
        if isinstance(x, str):
            return f"<{cls[x]}>" if x in N else json.dumps(x, ensure_ascii=False)
        if isinstance(x, dict):
            return "{" + ",".join(f"{json.dumps(k)}:{canon(v)}" for k, v in sorted(x.items())) + "}"
        if isinstance(x, list):
            return "[" + ",".join(sorted(canon(v) for v in x)) + "]"
        return json.dumps(x)

    rounds, n = 0, 1
    while True:
        rounds += 1
        keys = {q: (cls[q], canon({k: v for k, v in N[q].items() if k not in DROP})) for q in names}
        ids = {k: i for i, k in enumerate(sorted(set(keys.values())))}
        cls = {q: ids[keys[q]] for q in names}
        m = len(ids)
        if m == n:
            break
        n = m

    by = {}
    for q in names:
        by.setdefault(cls[q], []).append(q)
    classes = sorted((v for v in by.values() if len(v) > 1), key=lambda v: (-len(v), v))
    got = sorted(sorted(v) for v in classes)
    match = int(got == sorted(sorted(p) for p in PRED))
    rows = {f"class {i}": {"size": len(v), "members": v} for i, v in enumerate(classes)}
    s = {"n_nodes": len(names), "n_classes": len(by), "n_collide_class": len(classes),
         "n_collide_nodes": sum(len(v) for v in classes), "n_rounds": rounds,
         "base_errors": base_errors, "match_prediction": match}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in classes[:30]:
        print(len(v), v[:8])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "支持" if match else "反証")


if __name__ == "__main__":
    main()
