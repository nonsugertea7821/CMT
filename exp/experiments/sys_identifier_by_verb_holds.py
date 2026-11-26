"""h_identifier_by_verb_holds を確かめる: 名前でしか分かれない残りの組を、動詞の成り立つ状態（pre・post・new_kind）で書き分ければ、識別子は式で決まるか。

仮説（claims.yaml、#978）: v_depend(syntax.identifier, [signature_class, syntax.holds])。
  読み: 名詞に限定を足すのでなく（#976 で法則 single に反した）、名詞の種差になっている動詞の側に、
  成り立つ状態を書き足せば、どの識別子も名前を見ずに式だけで分かれ、型検査も通る。

手順:
  分割の細分は sys_identifier_residue_differentia（#976）・sys_identifier_bisimulation（#331）と同じ（関数をそのまま写した）。
  段は二つ。before（いまの main）と after（書き足した体系）。結果のファイルを段ごとに分ける。
  書き足しの決まり（結果を見る前に決める）:
    - 動詞 subj.v_pay（入金する）だけに、次を足す。名前・表示語・extends・from・to は変えない。名詞には触らない。
        new_kind: money
        post: [{is: part, from: new, to: from}, {is: exists, from: new}]
      根拠: subj.v_sell（販売する）が new_kind: money と、同じ post の二つの文を持つ（お金が生まれ、行う者の部分になる）。
            subj.sales（売上）が、入金（payment）を金額（money）で測る文を持つ。新しい概念・関係は足さない。
    - subj.v_approve（承認する）には足さない。片側が分かれれば組は分かれる見込みなので、最小の書き足しにする。
    - 予測: 動詞の組（v_approve/v_pay）が分かれ、それを種差にする名詞の組（approval/payment）も細分で分かれる。
  集計（段ごと）: n_nodes, n_classes, n_collide_class, n_collide_nodes, n_rounds, base_errors, 衝突の類の一覧。
判定（事前に決める）:
  before で n_collide_class = 0 なら、書き足しなしで支持。
  そうでなければ after で決める: n_collide_class = 0 かつ base_errors = 0 なら支持。
    衝突が残れば反証。base_errors > 0 なら、書き足しが体系を壊したので反証（誤りの中身を記録する）。
  base_errors は手元の型検査の数。ランナーの tc が別の誤りを出したら、それも反証の根拠として開示する。

開示（結果を見る前に分かっていること）:
  - #976 の before: 796 ノード、794 類、衝突 2 類（approval/payment、v_approve/v_pay）、base_errors 0。その後 main は claims.yaml だけが変わった。
  - #976 の after では、名詞の限定を足すと衝突 0 になったが、法則 single（限定は1つだけ）に 6 件反した。
  - pre・post・new_kind は限定（mod）ではないので、法則 single には当たらない見込み。v_perform の上位の法則と当たるかは知らない。
使い方:
  python exp/experiments/sys_identifier_by_verb_holds.py before
  python exp/experiments/sys_identifier_by_verb_holds.py after
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DROP = ("display", "gloss")
STAGES = ("before", "after")


def partition(N):
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
    return names, by, rounds


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    assert stage in STAGES, f"段は {STAGES} のどれか"
    out = ROOT / f"exp/experiments/results/sys_identifier_by_verb_holds_{stage}.json"
    assert not out.exists(), f"{out.name} はもう記録してある（走らせ直さない）"
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    base_errors = len(tc.errors)
    names, by, rounds = partition(T.N)
    classes = sorted((v for v in by.values() if len(v) > 1), key=lambda v: (-len(v), v))
    rows = {f"class {i}": {"size": len(v), "members": v} for i, v in enumerate(classes)}
    s = {"n_nodes": len(names), "n_classes": len(by), "n_collide_class": len(classes),
         "n_collide_nodes": sum(len(v) for v in classes), "n_rounds": rounds, "base_errors": base_errors}
    if stage == "before":
        s["verdict_support"] = 1 if not classes else None
    else:
        s["verdict_support"] = 1 if not classes and base_errors == 0 else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out.write_text(json.dumps({"rev": rev, "stage": stage, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in classes:
        print(len(v), v)
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
