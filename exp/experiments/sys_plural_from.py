"""仮説 h_plural_from（複数を許す指定は、終点の位置と同じく始点の位置にも掛かる: v_refer(many, [from, to])）を確かめる:
読みの式（v_refer の終点に書いた式）の始点に並びを書いたとき、終点に並びを書いたときと同じに扱われるか。
結果を見る前に、この説明と手順と判定を登録した。

対象（事前に決める）: cscl.yaml が読む体系のすべての yaml の facts のうち、動詞が v_refer で、終点が式（辞書）であり、
  式の from と to がともに文字列のもの（読みの式）。

手順:
  1. HEAD の体系（yaml と exp/experiments/results の結果のファイル）を作業場に写す。checkers は外さない。
  2. 読みの式ごとに、変異を2つ作る。
     A（始点を並びに）: 式の from を [from, from] にする。
     B（終点を並びに）: 式の to を [to, to] にする。
     同じ名を2度並べるので、端の種類は変わらず、変わるのは数だけ。
  3. 変異ごとに、HEAD の型検査器で作業場を検査し、弾くか（エラーが 1 以上）を記録する。エラーの文も記録する。
  4. 記述として、体系の最上位の事実（読みの式でないもの）のうち、個体でない側の値が並びであるものを、
     その並びが始点にあるか終点にあるかで数える（型検査器は走らせない。体系が検査に通ることは手順 1 で確かめる）。
判定（ec が通るもとで）:
  すべての読みの式で、A と B の結果（弾くか通すか）が同じなら支持（v_support）: 並びの扱いは位置によらない。
  A と B の結果が違う式が一つでもあれば反証（v_contradict）: 並びを許すかが、始点と終点で違う。

開示:
  登録の前に見たこと: 型検査器 gather は、読みの式の始点を関係 s、終点を関係 o として個体に集め、
  最後の確かめで o（と _at）だけを、数の確かめ（many）から外している。読みの式の始点に並びを書いた式は、いまの体系にない
  （終点に並びを書いた式は 9 個ある）。最上位の事実では、並びは始点に 113 個、終点に 6 個あり、どれも many でない関係。
  これらは、反証を予想させる。仮説の登録の元は、始点に並びを書いて「関係 s の事実が2つ以上ある」と弾かれたこと。
  変異の数は少なくとも数百あり、h_reading_ends_resolved の実験と同じ時刻に走らせる。

行（sys_plural_from.json）:
  "f <ファイル>:<番号>": subject_kind（h, o, d, other の番号 0..3）, from_rejected, to_rejected, asym
  "summary 要約": n_formulas, n_from_rejected, n_to_rejected, n_asym, n_top_list_from, n_top_list_to

使い方:
  python exp/experiments/sys_plural_from.py
"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
KINDS = {"h_": 0, "o_": 1, "d_": 2}


def yaml_files():
    c = yaml.safe_load((ROOT / "cscl.yaml").read_text(encoding="utf-8"))
    pats = [c["root"]] + c.get("library", []) + c.get("include", [])
    return [p.relative_to(ROOT).as_posix() for g in pats for p in sorted(ROOT.glob(g))]


def check(d):
    r = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=d, capture_output=True, text=True)
    m = re.search(r"検査に失敗: (\d+) 件", r.stdout)
    n = int(m.group(1)) if m else (0 if "検査に成功" in r.stdout else -1)
    return n, [ln.strip() for ln in r.stdout.splitlines() if ln.startswith(" - ")][:3]


def formulas():
    out = []
    for rel in yaml_files():
        D = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8")) or {}
        for i, f in enumerate(D.get("facts") or []):
            if (isinstance(f, dict) and str(f.get("is", "")).split(".")[-1] == "v_refer" and isinstance(f.get("to"), dict)
                    and isinstance(f["to"].get("from"), str) and isinstance(f["to"].get("to"), str)):
                out.append((rel, i, f))
    return out


def top_lists(T, Dm):
    n = {"from": 0, "to": 0}
    for dom, (name, X) in Dm.items():
        I, local = X["individuals"], X["_local"]
        for f in X.get("facts") or []:
            if not isinstance(f, dict) or "at" in f:
                continue
            verb = tc.qualify(f["is"], local, dom)
            if tc.is_kind_fact(f, T, dom, I) or not T.is_verb(verb):
                continue
            if tc.short(verb) == "v_refer" and isinstance(f.get("to"), dict):
                continue
            sides = [p for p in ("from", "to") if isinstance(f.get(p), str) and f[p] in I
                     and T.is_a(T.I.get(f[p]), T.end(verb, p))][:1]
            if sides:
                other = {"from": "to", "to": "from"}[sides[0]]
                n[other] += isinstance(f.get(other), list)
    return n


def worktree():
    d = Path(tempfile.mkdtemp(prefix="plural_"))
    subprocess.run(f"git archive HEAD cscl exp/src cscl.yaml | tar -x -C {d}", shell=True, cwd=ROOT, check=True)
    shutil.copytree(OUT, d / "exp/experiments/results", dirs_exist_ok=True)
    return d


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, Dm = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    base = worktree()
    n0, msg0 = check(base)
    if n0 != 0:
        raise SystemExit(f"写した作業場が検査に通らない: {msg0}")
    F = formulas()
    jobs = [(item, pos) for item in F for pos in ("from", "to")]

    def one(job):
        (rel, i, f), pos = job
        d = Path(tempfile.mkdtemp(prefix="plural_m_"))
        shutil.copytree(base, d, dirs_exist_ok=True)
        p = d / rel
        D = yaml.safe_load(p.read_text(encoding="utf-8"))
        P = dict(D["facts"][i]["to"])
        P[pos] = [P[pos], P[pos]]
        D["facts"][i] = {**D["facts"][i], "to": P}
        p.write_text(yaml.safe_dump(D, allow_unicode=True, sort_keys=False), encoding="utf-8")
        n, msgs = check(d)
        shutil.rmtree(d)
        return job, n, msgs

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    shutil.rmtree(base)
    by = {}
    detail = []
    for ((rel, i, f), pos), n, msgs in res:
        by.setdefault((rel, i), {"subject": str(f.get("from"))})[pos] = int(bool(n))
        detail.append({"file": rel, "index": i, "pos": pos, "errors": n, "msgs": msgs})
    rows = {}
    for (rel, i), r in by.items():
        rows[f"f {rel}:{i}"] = {"subject_kind": KINDS.get(r["subject"][:2], 3), "from_rejected": r["from"],
                                "to_rejected": r["to"], "asym": int(r["from"] != r["to"])}
    tl = top_lists(T, Dm)
    R = [r for k, r in rows.items()]
    rows["summary 要約"] = {"n_formulas": len(R), "n_from_rejected": sum(r["from_rejected"] for r in R),
                          "n_to_rejected": sum(r["to_rejected"] for r in R), "n_asym": sum(r["asym"] for r in R),
                          "n_top_list_from": tl["from"], "n_top_list_to": tl["to"]}
    (OUT / "sys_plural_from.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_plural_from.py", "_commit": head, "rows": rows, "mutants": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定: 反証" if rows["summary 要約"]["n_asym"] else "判定: 支持")


if __name__ == "__main__":
    main()
