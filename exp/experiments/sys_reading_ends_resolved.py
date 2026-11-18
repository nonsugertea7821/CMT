"""仮説 h_reading_ends_resolved（読みの式は宣言の範囲に依る: v_depend(reading_formula, declared_scope)）を確かめる:
v_refer の終点に書いた式（読みの式）の端の名前が、宣言された名前（ノードか個体）でなければ、検査が弾くか。
結果を見る前に、この説明と手順と判定を登録した。

対象（事前に決める）: cscl.yaml が読む体系のすべての yaml の facts のうち、動詞が v_refer で、終点が式（辞書）のもの（読みの式）。
  始点は、仮説（h_）・観察（o_）・決定（d_）・そのほかの個体。

手順:
  1. HEAD の体系（yaml と exp/experiments/results の結果のファイル）を作業場に写す。checkers は外さない（tc と ec をともに走らせる）。
  2. 読みの式ごとに、変異を1つ作る: 式の端のうち、from が文字列ならそれを、並びならその最初を、どちらでもなければ to を、
     宣言されていない名前 zz_undefined_end に置き換える。置き換えるところがない式は、変異を作らない（数を記録する）。
  3. 変異ごとに、HEAD の型検査器で作業場を検査し、弾くか（エラーが 1 以上）を記録する。エラーの文も記録する。
判定（ec が通るもとで）:
  すべての変異が弾かれれば支持（v_support）: 読みの式の端は、どこに書いても宣言された名前に照らされる。
  弾かれない変異が一つでもあれば反証（v_contradict）: 宣言されていない名前を端に置いても通る読みの式がある。

開示:
  #220 の P1 は checkers を外して走らせたので、端の確かめ（exp_check.py の triple など）が働いていなかった。この実験は checkers を入れる。
  始点が同じ個体の v_refer が2つ以上あるとき、型検査器が後のもので前のものを置き換えるかは、確かめていない
  （置き換えるなら、前のものの変異は通りうる）。行に、始点ごとの v_refer の数を記録する。
  登録の前に、測る仕組みだけを試した: 写した作業場が検査に通ること（変異は見ていない）。#220 の後の診断で、
  仮説 h_individual_scope_by_kind の読みの式の端を no_such_thing_xyz にした体系は、checkers を入れると弾かれた（1 件）。

行（sys_reading_ends_resolved.json）:
  "f <ファイル>:<番号>": subject_kind（h, o, d, other の番号 0..3）, n_refer（同じ始点の v_refer の数）, mutated, rejected
  "summary 要約": n_formulas, n_mutants, n_rejected, n_accepted, n_unmutated, n_multi（同じ始点の v_refer が2つ以上の式）, n_multi_accepted

使い方:
  python exp/experiments/sys_reading_ends_resolved.py
"""
import contextlib
import copy
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
BAD = "zz_undefined_end"
KINDS = {"h_": 0, "o_": 1, "d_": 2}


def yaml_files():
    c = yaml.safe_load((ROOT / "cscl.yaml").read_text(encoding="utf-8"))
    pats = [c["root"]] + c.get("library", []) + c.get("include", [])
    return [p.relative_to(ROOT).as_posix() for g in pats for p in sorted(ROOT.glob(g))]


def formulas():
    out = []
    for rel in yaml_files():
        D = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8")) or {}
        for i, f in enumerate(D.get("facts") or []):
            if isinstance(f, dict) and str(f.get("is", "")).split(".")[-1] == "v_refer" and isinstance(f.get("to"), dict):
                out.append((rel, i, f))
    return out


def mutate(P):
    P = copy.deepcopy(P)
    if isinstance(P.get("from"), str):
        P["from"] = BAD
    elif isinstance(P.get("from"), list) and P["from"] and isinstance(P["from"][0], str):
        P["from"][0] = BAD
    elif isinstance(P.get("to"), str):
        P["to"] = BAD
    elif isinstance(P.get("to"), list) and P["to"] and isinstance(P["to"][0], str):
        P["to"][0] = BAD
    else:
        return None
    return P


def worktree():
    d = Path(tempfile.mkdtemp(prefix="ends_"))
    subprocess.run(f"git archive HEAD cscl exp/src cscl.yaml | tar -x -C {d}", shell=True, cwd=ROOT, check=True)
    shutil.copytree(OUT, d / "exp/experiments/results", dirs_exist_ok=True)
    return d


def check(d):
    r = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=d, capture_output=True, text=True)
    m = re.search(r"検査に失敗: (\d+) 件", r.stdout)
    n = int(m.group(1)) if m else (0 if "検査に成功" in r.stdout else -1)
    return n, [ln.strip() for ln in r.stdout.splitlines() if ln.startswith(" - ")][:3]


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    base = worktree()
    n0, msg0 = check(base)
    if n0 != 0:
        raise SystemExit(f"写した作業場が検査に通らない: {msg0}")
    F = formulas()
    nref = Counter((rel, f.get("from")) for rel, _, f in F)

    def one(item):
        rel, i, f = item
        P = mutate(f["to"])
        if P is None:
            return item, None, []
        d = Path(tempfile.mkdtemp(prefix="ends_m_"))
        shutil.copytree(base, d, dirs_exist_ok=True)
        p = d / rel
        D = yaml.safe_load(p.read_text(encoding="utf-8"))
        D["facts"][i] = {**D["facts"][i], "to": P}
        p.write_text(yaml.safe_dump(D, allow_unicode=True, sort_keys=False), encoding="utf-8")
        n, msgs = check(d)
        shutil.rmtree(d)
        return item, n, msgs

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, F))
    shutil.rmtree(base)
    rows, detail = {}, []
    for (rel, i, f), n, msgs in res:
        subj = str(f.get("from"))
        multi = nref[(rel, f.get("from"))]
        rows[f"f {rel}:{i}"] = {"subject_kind": KINDS.get(subj[:2], 3), "n_refer": multi,
                                "mutated": int(n is not None), "rejected": int(bool(n)) if n is not None else -1}
        detail.append({"file": rel, "index": i, "subject": subj, "errors": n, "msgs": msgs})
    mut = [r for r in rows.values() if r["mutated"]]
    acc = [r for r in mut if not r["rejected"]]
    rows["summary 要約"] = {"n_formulas": len(F), "n_mutants": len(mut), "n_rejected": len(mut) - len(acc),
                          "n_accepted": len(acc), "n_unmutated": len(F) - len(mut),
                          "n_multi": sum(r["n_refer"] > 1 for r in mut), "n_multi_accepted": sum(r["n_refer"] > 1 for r in acc)}
    (OUT / "sys_reading_ends_resolved.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_reading_ends_resolved.py", "_commit": head, "rows": rows, "mutants": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定: 反証" if acc else "判定: 支持")


if __name__ == "__main__":
    main()
