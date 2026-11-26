"""h_identifier_by_residue_differentia を確かめる: 名前でしか分かれない残りに種差を書けば、識別子は式で決まるか。

仮説（claims.yaml）: v_depend(syntax.identifier, [signature_class, syntax.mod])。
  読み: 名前でしか分かれなかった残りの組に、分ける中身を限定（mod）として書き足せば、
  どの識別子も、名前を見ずに式だけで分かれる。

手順:
  分割の細分は sys_identifier_bisimulation（#331）と同じ（関数をそのまま写した）。
    ノードの値から display と gloss を除く。T.N のノードを指す文字列は、そのノードがいま属する類の番号に置く。
    初めは全ノードを 1 類にし、（いまの類, 正規の形）で分け直す。類の数が増えなくなったら止める。
  段は二つ。引数で選び、結果のファイルを段ごとに分ける（同じ段を二度走らせない）。
    before  いまの体系（main）で数える。
    after   種差を書き足した体系で数える。書き足しは before の結果を見たあと、下の決まりで行い、別の commit にする。
  種差の書き足しの決まり（結果を見る前に決める）:
    - 衝突した類の各ノードに、限定を一つずつ足す。名前・表示語・extends・既存の限定は変えない。
    - 足す限定は、体系にすでに書かれている文から読めるものに限る（新しい概念・関係を足さない）。
    - 予測している類と、足す限定（いま決めておく）:
        subj.payment  : {of: [v_measure, to], with: money}
            根拠: subj.sales が「金額（money）で、入金（payment）を測る」と書いている（mod: v_measure from, with payment）。
        subj.approval : {of: [v_stage, from], with: inspection}
            根拠: subj.approved_inspection が「承認（approval）まで済んだ検収（inspection）」を、v_stage to, with approval で書いている。
      動詞 v_pay / v_approve は、到達点（to）の名詞が分かれれば、細分で分かれる見込み。分かれなければ、動詞にも限定を足さず、そのまま記録する。
    - 予測にない類が before に出たら、同じ決まり（既存の文から読める限定を一つ）で足し、何を根拠にしたかを after の commit に書く。
      根拠になる文が体系にない類は、足さずに残す。
  集計（段ごと）: n_nodes, n_classes, n_collide_class, n_collide_nodes, n_rounds, base_errors, 衝突の類の一覧。
  行（sys_identifier_residue_differentia_<段>.json）: "class <i>": {size, members}、"summary 要約": {...}
判定（事前に決める）:
  before で n_collide_class = 0 なら、書き足しなしで支持（#331 の後の変更で、もう閉じていた）。
  そうでなければ after で決める: n_collide_class = 0 かつ base_errors = 0 なら支持。
    衝突が残れば反証（残った類は、既存の文から種差を読めなかった組として記録する）。
    base_errors > 0 なら、書き足しが体系を壊したので反証。

開示（結果を見る前に分かっていること）:
  - #331 の衝突は 4 類 10 ノード（subj.approval/payment、subj.v_approve/v_pay、syntax の derived/premise/required、
    v_assume/v_derive/v_require）。その後、syntax の v_assume・v_derive・v_require は pre・post・holds で書き分けられた
    （syntax.yaml の 122〜124 行）。だから syntax の 2 類は、before でもう分かれている見込み。
  - subj.approval と subj.payment は、いまも extends: process、mod: {of: [v_<動詞>, to]} の同じ形（subj.yaml 75・84 行）。
  - 型検査は段ごとに 1 回だけ（軽い）。
使い方:
  python exp/experiments/sys_identifier_residue_differentia.py before
  python exp/experiments/sys_identifier_residue_differentia.py after
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
    out = ROOT / f"exp/experiments/results/sys_identifier_residue_differentia_{stage}.json"
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
