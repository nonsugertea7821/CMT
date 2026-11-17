"""体系そのものを数える: フレーム（実行の各時点）の間で、宣言と存在がどう変わるか。

利用者の見立て「各フレームの存在論は閉じている。開いているのは時間の方向で、フレームからフレームへの概念の差分は増え続ける。
消える動詞（v_freeze）は真偽の軸だけを操作する。宣言が減るのはスタックの巻き戻しのときだけ」を判断する材料を、観察として取る。
仮説の確かめではない（判定の基準を置かない）。

sys_frames.json  2種類の行。どの値も 0 か 1。
  動詞の行（"verb 動詞"）: 動的な動詞ごと。
    creates        pre で exists を「述べられていない」とし、post で真と述べる（在るようにする）
    removes        post で exists を「述べられていない」にする（在らないようにする）
    truth_only     removes の動詞で、post が exists 以外の文を取り除かない（その個体についての文を残す）
  歩みの行（"step 記録 番号 動詞"）: 実行の記録の歩みごと（今の実行器で、閉世界）。
    declared_grows   宣言された個体の数が増える（今の実行器は名前を最初に全部宣言する）
    declared_shrinks 宣言された個体の数が減る
    exists_grows     exists を真と述べた個体の数が増える
    exists_shrinks   exists を真と述べた個体の数が減る
    about_absent     歩みの後に、在らない（exists が真でない）個体についての文が残っている
  記録は exp/tests の実行の記録すべてと、sys_declaration.py の RECORD（生まれる・消える動詞を含む）。

使い方:
  python exp/experiments/sys_frames.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/runtime"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import runtime as rt  # noqa: E402
    import sys_declaration  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def reading(a):
    return "unstated" if a.get("neg") else "false" if (a.get("val") or {}).get("truth") is False else "true"


def verb_rows(T):
    rows = {}
    for vid, n in T.N.items():
        if "pre" not in n:
            continue
        pre = {(a["is"], a.get("from")): reading(a) for a in n["pre"]}
        post = [(a["is"], a.get("from"), reading(a)) for a in n["post"]]
        creates = any(r == "true" and pre.get((rel, x)) == "unstated" for rel, x, r in post if rel == "exists")
        removes = any(r == "unstated" for rel, _, r in post if rel == "exists")
        row = {"creates": int(creates), "removes": int(removes)}
        if removes:
            row["truth_only"] = int(not any(r == "unstated" for rel, _, r in post if rel != "exists"))
        rows[f"verb {vid}"] = row
    return rows


def existing(m):
    return {a[0] for (rel, a), v in m.facts.items() if rel == "exists" and v is True}


def step_rows(T, name, run):
    m = rt.Machine(T, run, name, "closed_world")
    rows = {}
    for i, st in enumerate(run.get("steps", [])):
        n0, e0 = len(m.ind), existing(m)
        verb, b = st["is"], {k: v for k, v in st.items() if k != "is"}
        m.step(verb, b, f"steps[{i}]")
        e1 = existing(m)
        absent = [k for k in m.facts if k[0] != "exists" and any(a not in e1 for a in k[1])]
        rows[f"step {name} {i} {verb}"] = {
            "declared_grows": int(len(m.ind) > n0), "declared_shrinks": int(len(m.ind) < n0),
            "exists_grows": int(len(e1) > len(e0)), "exists_shrinks": int(len(e1) < len(e0)),
            "about_absent": int(bool(absent))}
    if m.errors:
        raise SystemExit(f"{name} が今の実行器で歩めない: {m.errors}")
    return rows


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = verb_rows(T)
    for path in sorted((ROOT / "exp/tests").glob("*.yaml")):
        rows |= step_rows(T, path.stem, yaml.safe_load(path.read_text(encoding="utf-8")))
    rows |= step_rows(T, "sys_declaration", sys_declaration.RECORD)
    for k, r in rows.items():
        print(k, r)
    (OUT / "sys_frames.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_frames.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    cols = sorted({c for r in rows.values() for c in r})
    print({c: f"{sum(r.get(c, 0) for r in rows.values())}/{sum(c in r for r in rows.values())}" for c in cols})


if __name__ == "__main__":
    main()
