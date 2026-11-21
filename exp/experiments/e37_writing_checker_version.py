"""E37: モデルが書いた行が受け付けられるかは、型検査器の版に依存するか（h_writing_depends_checker、#265）。

仮説（exp.yaml）: v_depend(formalization_accuracy, lang.type_checker)。
  E29・E30・E31 は、モデルが書いた cscl の行を、その時点の型検査器と体系で受け付けられるかで数えた。
  体系と検査器は今も変わり続けている。同じ行の判定が版で変われば、測った正しさはモデルの力だけでなく
  検査器（と、それが読む体系）の版を写している。

材料（モデルは走らせない。記録した結果ファイルから読む）:
  e29_model_writes_cscl.json   rows の written（書いた行）、typechecks（記録した判定）、gold（体系の元の行）。rev
  e30_typecheck_feedback.json  rows の fb_written / ctl_written と fb_typechecks / ctl_typechecks（before=0 の行だけ。書き直した行）。rev
  e31_glossary_writing.json    rows の written と typechecks（before=0 の行だけ）。rev
  同じ (rev, 識別子, 行) は1つに数える。gold は参考（判定に使わない）。

手順（規則で決める）:
  版ごとの木: 記録の rev を git archive で一時の場所に出す（cscl.yaml, cscl, exp/src, exp/tests, exp/experiments/results）。
    今の版は、このスクリプトのある木（この commit の体系と検査器）。
  行の判定（E29 と同じ）: 木の exp/src/subj.yaml で、識別子の行（2字下げで始まる最初の行）を書いた行に置き換え、
    type_checker.build() の誤りが 0 なら受け付けた（1）、それ以外（誤り、または検査器が落ちた）は 0。
    置き換える前の木の誤りが 0 でなければ、その木は使わない（base_errors に書く）。
  再現（記録の rev の木で判定し、記録した判定と比べる）: 書いた行ごとに一致するかを数える。
  今（今の木で判定）: 識別子が今の subj.yaml の nodes にない行は、今は判定できない（n_missing に数える）。
  反転: 今も判定できる行のうち、記録の rev での判定（再現の値）と今の判定が違う行。

判定（事前登録。書いた行だけ。gold は使わない）:
  前提（再現）: 記録の rev で判定した値が、記録した判定と 90% 以上一致する。
  前提（数）: 今も判定できる行が 10 以上ある。
  前提のどちらかが崩れたら、判定しない（仮説は未検証のまま、観察だけ書く）。
  反転が 3 以上なら支持（依存する）。反転が 0 なら反証。1 か 2 なら決まらない（未検証のまま）。

開示（結果を見る前に分かっていること）:
  - 版は、検査器のコードと体系のファイルをまとめて変える。反転が検査器のコードによるのか体系によるのかは、
    この手順では分けない。反転した行ごとに、両方の版の誤りの文を記録し、読むのは後にする。
  - E30 と E31 は E29 と同じ識別子を多く使う。書いた行が違えば別に数える。

出力: results/e37_writing_checker_version.json
使い方:
  python exp/experiments/e37_writing_checker_version.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "exp/experiments/results"
OUT = RES / "e37_writing_checker_version.json"
SUBJ = "exp/src/subj.yaml"
PARTS = ("cscl.yaml", "cscl", "exp/src", "exp/tests", "exp/experiments/results")
PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    tc.build()
print(json.dumps({"errors": len(tc.errors), "err_text": [str(e) for e in tc.errors[:5]]}, ensure_ascii=False))
'''


def lines_of(text):
    nodes = (yaml.safe_load(text) or {}).get("nodes") or {}
    out = {}
    for ln in text.split("\n"):
        k = ln.strip().split(":", 1)[0]
        if ln.startswith("  ") and not ln.startswith("   ") and k in nodes and k not in out:
            out[k] = ln
    return out


def export(rev, dst):
    have = [p for p in PARTS if subprocess.run(["git", "cat-file", "-e", f"{rev}:{p}"], cwd=ROOT).returncode == 0]
    tar = subprocess.run(["git", "archive", rev, *have], cwd=ROOT, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar, check=True)
    (dst / "exp/experiments/results").mkdir(parents=True, exist_ok=True)


def copy_now(dst):
    tar = subprocess.run(["tar", "-c", *[p for p in PARTS if (ROOT / p).exists()]], cwd=ROOT,
                         capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar, check=True)


def check(tree, key=None, line=None):
    f = tree / SUBJ
    orig = f.read_text(encoding="utf-8")
    try:
        if key is not None:
            cur = lines_of(orig).get(key)
            if cur is None or orig.count(cur + "\n") != 1:
                return None
            f.write_text(orig.replace(cur + "\n", line + "\n"), encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=tree, capture_output=True, text=True)
        if out.returncode != 0:
            return {"ok": 0, "errors": -1, "err_text": [out.stderr[-300:]]}
        r = json.loads(out.stdout.strip().splitlines()[-1])
        return {"ok": int(r["errors"] == 0), "errors": r["errors"], "err_text": r["err_text"][:3]}
    finally:
        f.write_text(orig, encoding="utf-8")


def collect():
    cases = {}

    def add(src, rev, key, line, rec, kind):
        if not line:
            return
        k = (rev, key, line)
        if k not in cases:
            cases[k] = {"rev": rev, "key": key, "line": line, "recorded": rec, "kind": kind, "src": [src]}
        elif src not in cases[k]["src"]:
            cases[k]["src"].append(src)

    d = json.loads((RES / "e29_model_writes_cscl.json").read_text(encoding="utf-8"))
    for name, r in d["rows"].items():
        key = name.split(" ", 1)[1]
        add("e29", d["rev"], key, r.get("written"), r.get("typechecks"), "written")
        add("e29_gold", d["rev"], key, r.get("gold"), 1, "gold")
    d = json.loads((RES / "e30_typecheck_feedback.json").read_text(encoding="utf-8"))
    for name, r in d["rows"].items():
        if r.get("before"):
            continue
        key = name.split(" ", 1)[1]
        for c in ("fb", "ctl"):
            add(f"e30_{c}", d["rev"], key, r.get(f"{c}_written"), r.get(f"{c}_typechecks"), "written")
    d = json.loads((RES / "e31_glossary_writing.json").read_text(encoding="utf-8"))
    for name, r in d["rows"].items():
        if r.get("before"):
            continue
        key = name.split(" ", 1)[1]
        add("e31", d["rev"], key, r.get("written"), r.get("typechecks"), "written")
    return list(cases.values())


def main():
    cases = collect()
    revs = sorted({c["rev"] for c in cases})
    base_errors = {}
    with tempfile.TemporaryDirectory() as tmp:
        trees = {}
        for rev in revs:
            t = Path(tmp) / rev
            t.mkdir()
            export(rev, t)
            b = check(t)
            base_errors[rev] = b["errors"]
            if b["errors"] == 0:
                trees[rev] = t
        now = Path(tmp) / "now"
        now.mkdir()
        copy_now(now)
        b = check(now)
        base_errors["now"] = b["errors"]
        for i, c in enumerate(cases):
            then = check(trees[c["rev"]], c["key"], c["line"]) if c["rev"] in trees else None
            cur = check(now, c["key"], c["line"]) if base_errors["now"] == 0 else None
            c["then"] = then
            c["now"] = cur
            print(i, c["kind"], c["key"], c["recorded"], then and then["ok"], cur and cur["ok"], flush=True)

    W = [c for c in cases if c["kind"] == "written"]
    G = [c for c in cases if c["kind"] == "gold"]

    def tally(rows):
        rep = [c for c in rows if c["then"] is not None]
        ev = [c for c in rep if c["now"] is not None]
        flips = [c for c in ev if c["then"]["ok"] != c["now"]["ok"]]
        return {
            "n": len(rows),
            "n_reproduced_checked": len(rep),
            "n_reproduced_match": sum(c["then"]["ok"] == c["recorded"] for c in rep),
            "n_missing": sum(c["now"] is None for c in rep),
            "n_now": len(ev),
            "n_then_ok": sum(c["then"]["ok"] for c in ev),
            "n_now_ok": sum(c["now"]["ok"] for c in ev),
            "n_flip": len(flips),
            "n_flip_to_ok": sum(c["now"]["ok"] for c in flips),
            "n_flip_to_ng": sum(1 - c["now"]["ok"] for c in flips),
        }

    sw, sg = tally(W), tally(G)
    rep_rate = sw["n_reproduced_match"] / sw["n_reproduced_checked"] if sw["n_reproduced_checked"] else 0.0
    pre_rep = rep_rate >= 0.9
    pre_n = sw["n_now"] >= 10
    verdict = ("not_judged" if not (pre_rep and pre_n)
               else "depend" if sw["n_flip"] >= 3 else "not_depend" if sw["n_flip"] == 0 else "undecided")
    rev_now = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {
        "rev_now": rev_now,
        "revs": revs,
        "base_errors": base_errors,
        "summary": {"written": sw, "gold": sg, "reproduce_rate": rep_rate},
        "judgment": {"pre_reproduce": pre_rep, "pre_n": pre_n, "verdict": verdict},
        "cases": cases,
    }
    print(json.dumps(out["summary"], ensure_ascii=False), json.dumps(out["judgment"]), flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
