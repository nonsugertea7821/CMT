"""E38: 型検査の誤りの種類は、法則で与えられるか（h_error_kind_is_law #705 と h_unnamed_error_is_law_given #709 の対）。

仮説（exp.yaml）:
  h_error_kind_is_law:          v_depend(type_check_result, syntax.laws)
  h_unnamed_error_is_law_given: v_depend(type_check_result, syntax.law_given)
  E37（反証）で、モデルが書いた行のうち退けられた行は、どの版の検査器でも退けられた。
  その退けられる理由の種類が、体系にすでにある法則（syntax.laws の下位: law_rule と law_given）で与えられるかを問う。
  与えられるなら「誤りの種類」の概念を足さずに済む。与えられないなら、別の概念が要る。

材料（モデルは走らせない）:
  results/e37_writing_checker_version.json の cases のうち kind が written のもの。同じ (key, line) は1つに数える。
  E37 の err_text は最初の3つだけなので、今の木（この commit の体系と検査器）でもう一度検査して、誤りをすべて得る。
  E37 のスクリプトと結果ファイルは走らせない・書き換えない。

手順（規則で決める）:
  行の検査（E37 と同じ置き換え）: 一時の場所に今の木を写し、exp/src/subj.yaml の識別子の行を書いた行に置き換え、
    type_checker.build() を呼ぶ。置き換える前の木の誤りが 0 でなければ止める（base_errors に書く）。
    検査器が落ちた行は crashed に数え、以下の分母から外す。
  単位は誤り（退けられた行の、build() が積んだ誤りの文の1つ1つ）。
  誤りの文が名指すノード: 文の中で最初に出る、体系のノードの識別子（領域.名前 の形で T.N にあるもの）。
  法則に帰せる（attributable）: 次のどちらか。
    名指す法則（named）: 文が「法則 <lid>（」で始まり、<lid> が体系の laws にある。
    掛かる法則（governed）: 体系の law_given の個体 L のうち、L の govern の先 t について、
      名指すノード n が T.is_a(n, t) を満たすものがある。
  名指さない誤り（unnamed）: named でない誤り。

判定（事前登録）:
  A = 法則に帰せる誤り / 誤り（crashed を除く）。
  h_error_kind_is_law: A ≥ 0.9 なら支持。A < 0.5 なら反証。その間は決まらない（未検証のまま、観察だけ書く）。
  U = 名指さない誤りのうち governed のもの / 名指さない誤り。
  h_unnamed_error_is_law_given: U ≥ 0.9 なら支持。U < 0.5 なら反証。その間は決まらない。
  名指さない誤りが 10 未満なら、h_unnamed_error_is_law_given は判定しない。
  参考（判定に使わない）: 行ごとに、その行の誤りがすべて法則に帰せるか。誤りの文の型（文の中の識別子を伏せた形）ごとの数。

開示（結果を見る前に分かっていること）:
  - 事前登録の前に、E37 の結果ファイルを覗いた。今の版で退けられた 65 行の最初の誤りは、
    「法則 X（…）に反する」が 9 行、「X は動詞 X の X に来られない」が約 30 行、「X は動詞でない」が 11 行、
    検査器が落ちたものが約 9 行だった。A は 0.5 を下回る見込みが高い。
  - 事前登録の前に、体系の law_given を読んだ。個体は 5 つ（unique_names, step, frame, halt, no_confusion）で、
    どれも govern の先は runtime.run だけ。書いた行の識別子は概念のノードなので、governed は 0 に近い見込みが高い。
    この手順は、その読みを、検査が実際に積んだ誤りの上で数え直すもの。
  - 最初の誤りは、書いた行そのものでなく、それに依る別の行（上位がなくなった子など）を名指すことがある。
    名指すノードは書いた行のものに限らない。
  - 誤りの文の型の分類は、名前を読む参考で、判定には使わない。

出力: results/e38_error_kind_is_law.json
使い方:
  python exp/experiments/e38_error_kind_is_law.py
"""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "exp/experiments/results"
OUT = RES / "e38_error_kind_is_law.json"
SUBJ = "exp/src/subj.yaml"
PARTS = ("cscl.yaml", "cscl", "exp/src", "exp/tests", "exp/experiments/results")
PROBE = r'''
import contextlib, io, json, re, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, Dm = tc.build()
laws = O.get("laws") or {}
given = {lid: list(l.get("govern") or []) for lid, l in laws.items() if l.get("kind") == "law_given"}
tok = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
rows = []
for e in tc.errors:
    s = str(e)
    m = re.match(r"法則 (\S+?)（", s)
    named = m.group(1) if m and m.group(1) in laws else None
    node = next((t for t in tok.findall(s) if t in T.N), None)
    gov = sorted(lid for lid, ts in given.items() for t in ts if node is not None and t in T.N and T.is_a(node, t))
    rows.append({"text": s, "named": named, "node": node, "governed": gov})
print(json.dumps({"errors": rows, "law_given": given}, ensure_ascii=False))
'''


def lines_of(text):
    import yaml
    nodes = (yaml.safe_load(text) or {}).get("nodes") or {}
    out = {}
    for ln in text.split("\n"):
        k = ln.strip().split(":", 1)[0]
        if ln.startswith("  ") and not ln.startswith("   ") and k in nodes and k not in out:
            out[k] = ln
    return out


def copy_now(dst):
    tar = subprocess.run(["tar", "-c", *[p for p in PARTS if (ROOT / p).exists()]], cwd=ROOT,
                         capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar, check=True)


def probe(tree, key=None, line=None):
    f = tree / SUBJ
    orig = f.read_text(encoding="utf-8")
    try:
        if key is not None:
            cur = lines_of(orig).get(key)
            if cur is None or orig.count(cur + "\n") != 1:
                return {"missing": True}
            f.write_text(orig.replace(cur + "\n", line + "\n"), encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=tree, capture_output=True, text=True)
        if out.returncode != 0:
            return {"crashed": True, "stderr": out.stderr[-300:]}
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        f.write_text(orig, encoding="utf-8")


def shape(text):
    return re.sub(r"[A-Za-z_][A-Za-z0-9_.\[\]]*", "X", text)


def main():
    e37 = json.loads((RES / "e37_writing_checker_version.json").read_text(encoding="utf-8"))
    cases = {}
    for c in e37["cases"]:
        if c["kind"] == "written":
            cases.setdefault((c["key"], c["line"]), c)
    with tempfile.TemporaryDirectory() as td:
        tree = Path(td)
        copy_now(tree)
        base = probe(tree)
        if base.get("crashed") or base["errors"]:
            OUT.write_text(json.dumps({"base_errors": base}, ensure_ascii=False, indent=1), encoding="utf-8")
            sys.exit("base tree has errors")
        law_given = base["law_given"]
        rows = []
        for (key, line), c in sorted(cases.items()):
            r = probe(tree, key, line)
            rows.append({"key": key, "line": line, "src": c["src"], **r})
            print(key, "crashed" if r.get("crashed") else "missing" if r.get("missing") else len(r["errors"]), flush=True)

    rejected = [r for r in rows if not r.get("missing") and (r.get("crashed") or r["errors"])]
    judged = [r for r in rejected if not r.get("crashed")]
    errs = [e for r in judged for e in r["errors"]]
    named = [e for e in errs if e["named"]]
    unnamed = [e for e in errs if not e["named"]]
    governed_unnamed = [e for e in unnamed if e["governed"]]
    attributable = [e for e in errs if e["named"] or e["governed"]]
    A = len(attributable) / len(errs) if errs else None
    U = len(governed_unnamed) / len(unnamed) if unnamed else None

    def verdict(x, enough=True):
        if x is None or not enough:
            return "not_judged"
        return "support" if x >= 0.9 else "refute" if x < 0.5 else "undecided"

    summary = {
        "n_cases": len(rows),
        "n_missing": sum(1 for r in rows if r.get("missing")),
        "n_accepted": sum(1 for r in rows if not r.get("missing") and not r.get("crashed") and not r["errors"]),
        "n_rejected": len(rejected),
        "n_crashed": sum(1 for r in rejected if r.get("crashed")),
        "n_errors": len(errs),
        "n_named": len(named),
        "n_unnamed": len(unnamed),
        "n_governed_unnamed": len(governed_unnamed),
        "n_attributable": len(attributable),
        "attributable_rate": A,
        "governed_unnamed_rate": U,
        "n_lines_all_attributable": sum(1 for r in judged if all(e["named"] or e["governed"] for e in r["errors"])),
        "named_laws": dict(Counter(e["named"] for e in named).most_common()),
        "shapes": dict(Counter(shape(e["text"]) for e in errs).most_common()),
    }
    judgment = {
        "h_error_kind_is_law": verdict(A),
        "h_unnamed_error_is_law_given": verdict(U, len(unnamed) >= 10),
    }
    out = {"law_given": law_given, "summary": summary, "judgment": judgment, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "shapes"}, ensure_ascii=False))
    print(json.dumps(judgment))


if __name__ == "__main__":
    main()
