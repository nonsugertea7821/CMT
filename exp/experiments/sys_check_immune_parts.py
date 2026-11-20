"""h_check_immune_parts を確かめる: 領域を部分のファイルに分けても、検査（tc と ec）の結果は変わらないか。

仮説（claims.yaml）: v_refer(h, v_not_depend(type_checker, syntax.passage))。登録 #494（わき道）。
  利用者の示唆: 個体の数そのものが実験のデータなので、削るより、claude_session_log と同じ方法で
  ファイルを分けた方が早い。

前提の確認（結果を見る前）: 部分を読む仕組み merge_parts は、ブランチ claude/session-log-<利用者> の
  型検査器にだけあり、main の型検査器にはない。よって写しの型検査器に移す（次の変種 P0・P）。

手順（体系のファイルも型検査器も変えない。写しの上で変える）:
  変種 L: main の写しをそのまま。
  変種 P0（対照）: 型検査器の写しに merge_parts を移すだけ。体系は変えない。
    移す箇所: (1) load の前に merge_parts と read_file（session-log の版と同じ本文）を足す。
    (2) load の root でない枝の yaml.load を merge_parts で包む。
    (3) 体系のファイルを読み直す箇所 yload((SPEC / name).read_text(...)) と yload(open(SPEC / name)) を read_file(name) にする。
  変種 P: P0 に加えて、exp.yaml の測定の族を部分のファイルに移す。
    族 F = {F: {is: measurement_family}} の個体。族の個体の集まり ids(F) は、F と、v_axis_of で F へ向かう軸、
    v_value_of でその軸へ向かう値。ids(F) の個体の行と、from か to が ids(F) にある事実の行を、
    行のまま（書き換えずに）exp/src/families/<F>.yaml の individuals と facts に移す。
    exp.yaml の domain の行の次に parts: exp/src/families/*.yaml を足す。
  測るもの（各変種）: errors、ec_errors、laws_hash、rel_hash（法則を評価した関係の行の集まりのハッシュ。
    #478 の PROBE の rel を使う）、n_rel。P では、exp.yaml の行数、部分のファイルの数、移した行の数も。
  行（sys_check_immune_parts.json）: "variant L/P0/P": {...}、"summary 要約"。

判定（事前に決める）:
  外れ: P0 の errors・ec_errors・laws_hash・rel_hash のどれかが L と違う（移した仕組みが中立でない）。
  支持: P の errors・ec_errors・laws_hash・rel_hash がすべて L と同じで、L の errors = 0、ec_errors = 0。
  1 つでも違えば反証。

開示:
  - 族は 217（数えるために exp.yaml の行を読んだ。結果は見ていない）。個体の行はどれも 1 行で書かれている。
  - 運用への影響（判定の外）: auto_merge.py は状態の変わるファイルを claims.yaml と exp.yaml に限る（R2）。
    分けると、結果の commit が families/*.yaml を触るので、auto_merge も合わせて変える必要がある。
訂正 1（1 回目の実行の後。結果 sys_check_immune_parts.json は残す）:
  1 回目は P0・P とも RecursionError で検査が走らず、判定は外れ。原因は (3) の置き換えが、(1) で足した
  read_file の本文の yload((SPEC / name)...) まで read_file(name) にしたこと（自分を呼び続ける）。
  訂正: (3) の置き換えを (1) の挿入の前に行う。ほかの手順と判定は変えない。出力は
  sys_check_immune_parts_fix1.json。1 回目で L の値（errors 0、ec_errors 0、laws_hash、rel_hash）を見ている。
  P の行数（exp.yaml 8601 → 1707、部分 217、移した行 6895、部分の最大 144 行）も見ている。
使い方:
  python exp/experiments/sys_check_immune_parts.py
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_check_immune_parts_fix1.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_roles_by_signature as PREV

CHECKER = "cscl/bootstrap/type_checker/type_checker.py"
MERGE = '''def merge_parts(D, name, read):
    if not isinstance(D, dict) or not D.get("parts"):
        return D
    for p in sorted(ROOT.glob(D["parts"])):
        P = read(p) or {}
        if set(P) - {"individuals", "facts"}:
            err(f"{name} の部分 {p.relative_to(ROOT)}: individuals と facts のほかを書いている（{sorted(set(P) - {'individuals', 'facts'})}）")
        for k, v in (P.get("individuals") or {}).items():
            if k in (D.get("individuals") or {}):
                err(f"{name} の部分 {p.relative_to(ROOT)}: 個体 {k} が、ほかでも定義されている")
            D.setdefault("individuals", {})[k] = v
        D.setdefault("facts", []).extend(P.get("facts") or [])
    return D


def read_file(name):
    return merge_parts(yload((SPEC / name).read_text(encoding="utf-8")) or {}, name, lambda p: yload(p.read_text(encoding="utf-8")))


def load(name):'''
LOAD_OLD = '        return yaml.load((SPEC / name).read_text(encoding="utf-8"), Loader=_Unique)\n'
LOAD_NEW = ('        return merge_parts(yaml.load((SPEC / name).read_text(encoding="utf-8"), Loader=_Unique), name,\n'
            '                           lambda p: yaml.load(p.read_text(encoding="utf-8"), Loader=_Unique))\n')
READS = ['yload((SPEC / name).read_text(encoding="utf-8"))', 'yload(open(SPEC / name))']


def edit_checker(d):
    p = d / CHECKER
    t = p.read_text(encoding="utf-8")
    n = 0
    assert t.count("\ndef load(name):") == 1 and t.count(LOAD_OLD) == 1
    for r in READS:
        n += t.count(r)
        t = t.replace(r, "read_file(name)")
    t = t.replace("\ndef load(name):", "\n" + MERGE, 1).replace(LOAD_OLD, LOAD_NEW, 1)
    n += 2
    p.write_text(t, encoding="utf-8")
    return n


def split_exp(d):
    p = d / "exp/src/exp.yaml"
    L = p.read_text(encoding="utf-8").split("\n")
    key = lambda l: (re.match(r"  (\w+):", l) or [None, None])[1]
    fams = [key(l) for l in L if re.fullmatch(r"  \w+: \{is: measurement_family\}", l)]
    facts = [(i, yaml.safe_load(l[4:])) for i, l in enumerate(L) if l.startswith("  - {")]
    ids = {F: {F} for F in fams}
    for v in ("v_axis_of", "v_value_of"):
        for F in fams:
            ids[F] |= {f["from"] for _, f in facts if f.get("is") == v and isinstance(f.get("from"), str) and f.get("to") in ids[F]}
    owner = {x: F for F in fams for x in ids[F]}
    parts, moved = {F: ([], []) for F in fams}, set()
    for i, l in enumerate(L):
        k = key(l) if not l.startswith("  - ") else None
        if k in owner and re.fullmatch(r"  \w+: \{.*\}", l):
            parts[owner[k]][0].append(l)
            moved.add(i)
    for i, f in facts:
        hit = [owner[x] for x in (f.get("from"), f.get("to")) if isinstance(x, str) and x in owner]
        if hit:
            parts[hit[0]][1].append(L[i])
            moved.add(i)
    rest = [l for i, l in enumerate(L) if i not in moved]
    j = next(i for i, l in enumerate(rest) if l.startswith("domain:"))
    rest[j + 1:j + 1] = ["parts: exp/src/families/*.yaml"]
    p.write_text("\n".join(rest), encoding="utf-8")
    fd = d / "exp/src/families"
    fd.mkdir()
    for F, (ind, fac) in parts.items():
        (fd / f"{F}.yaml").write_text("individuals:\n" + "\n".join(ind) + "\nfacts:\n" + "\n".join(fac) + "\n", encoding="utf-8")
    return {"n_families": len(fams), "n_moved": len(moved), "exp_lines_before": len(L), "exp_lines_after": len(rest),
            "max_part_lines": max(len(a) + len(b) + 2 for a, b in parts.values())}


def main():
    res, info = {}, {}
    for k in ("L", "P0", "P"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            PREV.copy_tree(d)
            e = {}
            if k in ("P0", "P"):
                e["checker"] = edit_checker(d)
            if k == "P":
                e.update(split_exp(d))
            r = PREV.probe(d)
            r["rel_hash"] = hashlib.sha256("\n".join(r.get("rel") or []).encode()).hexdigest()[:16]
            r.pop("rel", None)
            res[k], info[k] = r, e
    M = ("errors", "ec_errors", "laws_hash", "rel_hash")
    L, P0, P = res["L"], res["P0"], res["P"]
    s = {"L_errors": L.get("errors"), "L_ec_errors": L.get("ec_errors"),
         "P0_same": int(all(P0.get(m) == L.get(m) for m in M)),
         "P_same": int(all(P.get(m) == L.get(m) for m in M)),
         "P_errors": P.get("errors"), "P_ec_errors": P.get("ec_errors"),
         **{f"P_{k}": v for k, v in info["P"].items() if k != "checker"}}
    s["verdict"] = ("外れ" if not s["P0_same"] else
                    "支持" if s["P_same"] and s["L_errors"] == 0 and s["L_ec_errors"] == 0 else "反証")
    rows = {f"variant {k}": {**res[k], "edits": info[k]} for k in res}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:600])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
