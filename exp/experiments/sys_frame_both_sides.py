"""h_frame_both_sides を確かめる: 前の状態の指定（pre）を書く動詞は、後の状態の指定（post）も書くか。それを法則として式で求められるか。

仮説（claims.yaml）: v_depend(syntax.pre, syntax.post)。
  登録（1db10c0）の読み: h_boundary_invariant（#325）の含意。いまの動詞はみな前後の両方を書くが、検査器は片側だけの枠を受け付ける。
  前後の両方を書くことを、式で求める。

操作: 体系のファイルも検査器も変えない。リポジトリを一時ディレクトリに写し（.git を除く）、写しの syntax.yaml を変えて、
  写しの型検査器を別のプロセスで走らせる。
  法則 L（写しの syntax.yaml に足す。検査器のコードは変えない）:
    個体 frame_both_sides: {is: law_rule, display: 前の状態の指定を書く動詞は、後の状態の指定も書く}
    {is: v_assume,  from: frame_both_sides, to: {is: pre, from: var1, to: var2}}
    {is: v_assume,  from: frame_both_sides, to: {is: post, from: var1, to: var3, neg: true}}
    {is: v_require, from: frame_both_sides, to: {is: same, from: var1, to: var1, neg: true}}
    （前提が当たれば、求める文は成り立たないので、法則に反するとして報告される。syntax は閉世界を前提に置く。）
  見本の動詞（写しの syntax.yaml の nodes に足す）:
    pre    v_probe_pre:  {..., extends: occurrent, from: continuant, to: continuant, pre: [{is: exists, from: to, neg: true}]}
    post   v_probe_post: {..., extends: occurrent, from: continuant, to: continuant, post: [{is: exists, from: to}]}
走らせる組（6 回）: {base, pre, post} × {nolaw, law}
数える:
  静的（写しで base_nolaw のときに type_checker.build() で読む）:
    n_pre       pre を書く節点の数
    pre_only    pre を書き post を書かない節点の数
    post_only   post を書き pre を書かない節点の数（記録だけ。仮説は向きを pre → post に限る）
  回ごと: exit、n_err、law_err（「法則 frame_both_sides」を含む誤りの行の数）、law_names（その行に現れる見本の動詞）
仮説からの見込み（事前に決める）:
  pre_only = 0。
  base_law の n_err = base_nolaw の n_err（= 0）。
  pre_nolaw は通る（検査器は片側の枠を受け付ける）。pre_law は pre_nolaw より 1 件多く、law_err = 1 で v_probe_pre を名指す。
  post_law は post_nolaw と n_err が同じで、law_err = 0。
判定（事前に決める）:
  base_nolaw が通らなければ、手順が壊れているので外れとし、状態を変えない。
  pre_only > 0 なら反証（いまの体系に、前だけを書く動詞がある）。
  pre_only = 0 で、法則の見込み（base_law・pre_law・post_law）がすべて当たれば支持。
  pre_only = 0 だが法則の見込みが外れれば mixed（依存は外延では成り立つが、いまの法則の書き方では求められない）。
開示（結果を見る前に分かっていること）:
  - pre と post は文法の語（nodes の語）で、名前で読んでよい。
  - 法則の形は syntax の inherit_from（否定の前提で、束縛しない変数 var4 を使う）と acyclic（v_require に same の否定）をまねた。
    pre の値はリストで、法則の前提 {is: pre, ...} がリストの属性に当たるかは確かめていない。予想が立たないのはここ。
  - 見本の動詞の中身（exists）は std.yaml の v_compute に倣った。意味が正しいかは問わない。

行（sys_frame_both_sides.json）: "static": {...}, "case <見本> <法則>": {...}, "summary 要約": {...}
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_frame_both_sides.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
LAW_IND = "  frame_both_sides: {is: law_rule, display: 前の状態の指定を書く動詞は、後の状態の指定も書く}"
LAW_FACTS = [
    "  - {is: v_assume, from: frame_both_sides, to: {is: pre, from: var1, to: var2}}",
    "  - {is: v_assume, from: frame_both_sides, to: {is: post, from: var1, to: var3, neg: true}}",
    "  - {is: v_require, from: frame_both_sides, to: {is: same, from: var1, to: var1, neg: true}}",
]
PROBES = {
    "base": None,
    "pre": ("v_probe_pre", "  v_probe_pre: {display: 見本の前だけを書く動詞, extends: occurrent, from: continuant, to: continuant, pre: [{is: exists, from: to, neg: true}]}"),
    "post": ("v_probe_post", "  v_probe_post: {display: 見本の後だけを書く動詞, extends: occurrent, from: continuant, to: continuant, post: [{is: exists, from: to}]}"),
}
STATIC = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, Dm = tc.build()
pre = [q for q, n in T.N.items() if n.get("pre")]
post = [q for q, n in T.N.items() if n.get("post")]
print(json.dumps({"n_pre": len(pre), "n_post": len(post), "pre_only": sorted(set(pre) - set(post)),
                  "post_only": sorted(set(post) - set(pre))}, ensure_ascii=False))
'''


def edited(src, probe, law):
    lines = src.split("\n")
    if probe:
        lines.insert(lines.index("nodes:") + 1, probe[1])
    if law:
        i = next(k for k, x in enumerate(lines) if x.startswith("  acyclic: {is: law_rule"))
        lines.insert(i + 1, LAW_IND)
        while lines and lines[-1] == "":
            lines.pop()
        lines += LAW_FACTS
    return "\n".join(lines) + "\n"


def run(work, src, probe, law):
    (work / SYN).write_text(edited(src, probe, law), encoding="utf-8")
    p = subprocess.run([sys.executable, TC], cwd=work, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"検査に失敗: (\d+) 件", out)
    lines = [ln for ln in out.split("\n") if ln.startswith(" -")]
    law_lines = [ln for ln in lines if "frame_both_sides" in ln]
    return {"exit": p.returncode, "n_err": int(m.group(1)) if m else 0, "trace": 1 if "Traceback" in out else 0,
            "law_err": len(law_lines), "law_names": sorted({v for v in ("v_probe_pre", "v_probe_post") for ln in law_lines if v in ln}),
            "lines": lines[:6]}


def main():
    src = (ROOT / SYN).read_text(encoding="utf-8")
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        (work / SYN).write_text(src, encoding="utf-8")
        p = subprocess.run([sys.executable, "-c", STATIC], cwd=work, capture_output=True, text=True)
        try:
            rows["static"] = json.loads(p.stdout.strip().split("\n")[-1])
        except (ValueError, IndexError):
            rows["static"] = {"failed": p.stderr.strip()[-300:]}
        print("static", json.dumps(rows["static"], ensure_ascii=False), flush=True)
        for name, probe in PROBES.items():
            for law in (False, True):
                r = run(work, src, probe, law)
                rows[f"case {name} {'law' if law else 'nolaw'}"] = r
                print(name, law, json.dumps(r, ensure_ascii=False), flush=True)
    g = lambda n, l: rows[f"case {n} {l}"]
    st = rows["static"]
    s = {"base_ok": 1 if g("base", "nolaw")["exit"] == 0 else 0,
         "n_pre": st.get("n_pre", -1), "pre_only": len(st.get("pre_only", [])) if "pre_only" in st else -1,
         "post_only": len(st.get("post_only", [])) if "post_only" in st else -1,
         "law_base_same": 1 if g("base", "law")["n_err"] == g("base", "nolaw")["n_err"] else 0,
         "pre_accepted": 1 if g("pre", "nolaw")["exit"] == 0 else 0,
         "law_catches_pre": 1 if (g("pre", "law")["n_err"] == g("pre", "nolaw")["n_err"] + 1 and g("pre", "law")["law_err"] == 1
                                  and g("pre", "law")["law_names"] == ["v_probe_pre"]) else 0,
         "law_spares_post": 1 if (g("post", "law")["n_err"] == g("post", "nolaw")["n_err"] and g("post", "law")["law_err"] == 0) else 0}
    s["law_ok"] = 1 if s["law_base_same"] and s["pre_accepted"] and s["law_catches_pre"] and s["law_spares_post"] else 0
    s["verdict_support"] = 1 if s["base_ok"] and s["pre_only"] == 0 and s["law_ok"] else 0
    s["verdict_refute"] = 1 if s["base_ok"] and s["pre_only"] > 0 else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
