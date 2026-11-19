"""h_fact_slot_by_verb を確かめる: 検査器が事実の欄を動詞でも分ければ、一つの個体から、終点の種類が同じ二つの動詞を出せるか。

仮説（claims.yaml）: v_depend(type_checker, syntax.refer_from_occurrent)。
  読み: 欄を決めるのに、もう一方の端の種類だけでなく、事実の動詞（occurrent の側）も読むべき。
  前の実験 sys_fact_slot_by_end（支持）で、欄は端の種類で決まり、v_depend と v_raise が同じ欄 continuant で衝突すると分かった。

操作: 体系のファイルも検査器も変えない。リポジトリを一時ディレクトリに写し（.git を除く）、写しの型検査器の gather に
  次の変更を入れる（文字列の置き換え。どれもちょうど一回現れることを確かめてから置き換える）:
    - 事実を集めるとき、欄 I[個体][端の種類] に入れるのに加えて、(個体, 端の種類, 動詞) ごとの数を BV に数える。
    - many でない欄の衝突を「欄の事実が2つ以上」から「同じ動詞の事実が2つ以上」に変える。
    - 欄 I[個体][端の種類] の値は、これまでどおり最初の事実（many なら全部）。下流の読み方は変えない。
  写しの exp/src/exp.yaml には、見本の個体 d_probe（design_dec_tentative）と、その中身
  {is: v_refer, from: d_probe, to: {is: v_depend, from: decision, to: basis}}（前の実験の訂正と同じ）と、見本の事実を足す。
見本（前の実験と同じ 7 つ。始点は d_probe）:
  base、c1_one、c2_same_verb、c3_two_verbs、c4_siblings、c5_many、c6_two_ends
  対照 ctrl_c3: c3 を、変えていない写しの検査器で走らせる（落ちるはず。前の実験の再現）。
仮説からの見込み（事前に決める）:
  変えた検査器で: 落ちる c2（同じ動詞が continuant に 2 つ）。通る base、c1、c3、c4、c5、c6。
  変えていない検査器で: ctrl_c3 は落ちる。
数える（見本ごと）: exit、n_err、slot_err（d_probe の「関係 continuant の事実が2つ以上ある」の行）、other_err、fails、match。
判定（事前に決める）:
  置き換えのどれかが一回でなければ、または base の exit が 0 でなければ、手順が壊れているので外れとし、状態を変えない。
  8 つすべてで match = 1、かつ落ちる見本（c2、ctrl_c3）の誤りが slot_err だけ（other_err = 0、n_err = 1）なら支持。
  c3 か c4 が落ちれば反証（動詞で分けても通らない）。それ以外の不一致は mixed。
開示（結果を見る前に分かっていること）:
  - 見込みは、gather を読んで立てた。見本と数え方は前の実験の写し。
  - この変更では、c3・c4 の二つめの事実は欄に入らない（欄の値は最初の一つ）。検査は通っても、下流がその事実を読めるかは測らない。
    だから支持でも「欄を動詞で分ければ足りる」とは言えず、「衝突の判定を動詞で分けると、体系の残りは壊れない」までを言う。
  - 体系の側の直し方（h_decision_link_by_role、#387 で支持）とは別の道。どちらを入れるかは、この結果と下流の読み方で決める。

行（sys_fact_slot_by_verb.json）: "case <名前>": {facts, checker, expect_fail, exit, n_err, slot_err, other_err, fails, match},
  "summary 要約": {n_case, n_match, patch_ok, base_ok, clean, refute（c3 か c4 が落ちた）, verdict_support}
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_fact_slot_by_verb.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
PROBE = "d_probe"
CONTENT = f"  - {{is: v_refer, from: {PROBE}, to: {{is: v_depend, from: decision, to: basis}}}}"
CASES = {
    "base": ([], False, "verb"),
    "c1_one": ([("v_depend", "d_metric")], False, "verb"),
    "c2_same_verb": ([("v_depend", "d_metric"), ("v_depend", "d_road_region")], True, "verb"),
    "c3_two_verbs": ([("v_depend", "d_metric"), ("v_raise", "d_road_region")], False, "verb"),
    "c4_siblings": ([("v_raise", "d_metric"), ("v_lower", "d_road_region")], False, "verb"),
    "c5_many": ([("v_ground", "h_ambiguity_is_region_choice"), ("v_ground", "h_writing_depends_checker")], False, "verb"),
    "c6_two_ends": ([("v_depend", "d_metric"), ("v_ground", "h_ambiguity_is_region_choice")], False, "verb"),
    "ctrl_c3": ([("v_depend", "d_metric"), ("v_raise", "d_road_region")], True, "orig"),
}
PATCH = [
    ('    for i, f in enumerate(D.get("facts") or []):\n        where = f"{name} facts[{i}]"\n        if not isinstance(f, dict) or set(f) - set(T.G["facts"]) or "is" not in f:',
     '    BV = {}\n    for i, f in enumerate(D.get("facts") or []):\n        where = f"{name} facts[{i}]"\n        if not isinstance(f, dict) or set(f) - set(T.G["facts"]) or "is" not in f:'),
    ('        I[subj].setdefault(rel, []).append(val)\n',
     '        I[subj].setdefault(rel, []).append(val)\n        BV.setdefault((subj, rel, short(verb)), []).append(val)\n'),
    ('                if rel not in T.many and len(vs) > 1:',
     '                if rel not in T.many and any(len(w) > 1 for (s2, r2, _), w in BV.items() if s2 == subj and r2 == rel):'),
]


def patched(src, facts):
    lines = src.split("\n")
    i = lines.index("individuals:")
    lines.insert(i + 1, f"  {PROBE}: {{is: design_dec_tentative}}")
    while lines and lines[-1] == "":
        lines.pop()
    lines += [CONTENT] + [f"  - {{is: {v}, from: {PROBE}, to: {t}}}" for v, t in facts]
    return "\n".join(lines) + "\n"


def run_case(work, src, facts):
    (work / "exp/src/exp.yaml").write_text(patched(src, facts), encoding="utf-8")
    p = subprocess.run([sys.executable, TC], cwd=work, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"検査に失敗: (\d+) 件", out)
    lines = [ln for ln in out.split("\n") if ln.startswith(" -")]
    slot = [ln for ln in lines if PROBE in ln and "関係 continuant の事実が2つ以上ある" in ln]
    other = [ln for ln in lines if PROBE in ln and ln not in slot]
    return {"exit": p.returncode, "n_err": int(m.group(1)) if m else 0, "slot_err": 1 if slot else 0,
            "other_err": len(other), "lines": lines[:5]}


def main():
    src = (ROOT / "exp/src/exp.yaml").read_text(encoding="utf-8")
    tc_src = (ROOT / TC).read_text(encoding="utf-8")
    counts = [tc_src.count(a) for a, _ in PATCH]
    tc_new = tc_src
    for a, b in PATCH:
        tc_new = tc_new.replace(a, b)
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        for name, (facts, expect, checker) in CASES.items():
            (work / TC).write_text(tc_new if checker == "verb" else tc_src, encoding="utf-8")
            r = run_case(work, src, facts)
            fails = 1 if r["exit"] != 0 else 0
            rows[f"case {name}"] = {"facts": [f"{v} {t}" for v, t in facts], "checker": checker,
                                    "expect_fail": 1 if expect else 0, **r, "fails": fails,
                                    "match": 1 if fails == (1 if expect else 0) else 0}
            print(name, json.dumps(rows[f"case {name}"], ensure_ascii=False), flush=True)
    cs = list(rows.values())
    failing = [r for r in cs if r["expect_fail"]]
    s = {"n_case": len(cs), "n_match": sum(r["match"] for r in cs),
         "patch_ok": 1 if counts == [1, 1, 1] else 0,
         "base_ok": 1 if rows["case base"]["exit"] == 0 else 0,
         "clean": 1 if all(r["slot_err"] == 1 and r["other_err"] == 0 and r["n_err"] == 1 for r in failing) else 0,
         "refute": 1 if rows["case c3_two_verbs"]["fails"] or rows["case c4_siblings"]["fails"] else 0}
    s["verdict_support"] = 1 if s["patch_ok"] and s["base_ok"] and s["n_match"] == s["n_case"] and s["clean"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "patch_counts": counts, "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
