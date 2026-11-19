"""h_fact_slot_by_end を確かめる: 検査器は、個体についての事実を、動詞ではなく、位置と端の種類と many で区別するか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.position, syntax.many])。
  読み: 個体の事実の欄は「もう一方の端の種類」で決まり、その種類が many でなければ一つしか入らない。
  動詞が違っても、もう一方の端の種類が同じなら、同じ欄に入って衝突する。

操作: 体系のファイルは変えない。リポジトリを一時ディレクトリに写し（.git を除く）、写しの exp/src/exp.yaml に
  見本の個体 d_probe（design_dec_tentative）と、見本の事実を足して、写しの型検査器を別のプロセスで走らせる。
  見本ごとに、もとの exp.yaml から写し直す。
見本（どれも始点は d_probe。終点はもとからある個体）:
  c1_one        v_depend → d_metric                                   （欄 continuant に 1 つ）
  c2_same_verb  v_depend → d_metric、v_depend → d_road_region          （同じ動詞で continuant に 2 つ）
  c3_two_verbs  v_depend → d_metric、v_raise → d_road_region           （違う動詞、終点はどちらも continuant）
  c4_siblings   v_raise → d_metric、v_lower → d_road_region            （違う動詞、終点はどちらも continuant）
  c5_many       v_ground → h_ambiguity_is_region_choice、v_ground → h_writing_depends_checker（basis は many）
  c6_two_ends   v_depend → d_metric、v_ground → h_ambiguity_is_region_choice（終点の種類が違う）
  base          見本の個体だけ（事実なし）
仮説からの見込み（事前に決める）:
  落ちる: c2、c3、c4（d_probe について「関係 continuant の事実が2つ以上ある」）
  通る:   base、c1、c5、c6
  c3・c4 が、動詞の区別が欄で潰れることを問う中心の見本。c2 は同じ動詞の対照、c5 は many の対照、c6 は端の種類の対照。
数える（見本ごと）:
  exit       写しの型検査器の終了コード
  n_err      「検査に失敗: N 件」の N（なければ 0）
  slot_err   d_probe についての「関係 continuant の事実が2つ以上ある」の行があれば 1
  other_err  d_probe に触れる、それ以外の誤りの行の数
  fails      exit が 0 でなければ 1
  match      fails が見込みと一致すれば 1
判定（事前に決める）:
  base の exit が 0 でなければ、写しの手順が壊れているので外れとし、状態を変えない。
  7 つの見本すべてで match = 1、かつ落ちる見本の誤りが slot_err だけ（other_err = 0、n_err = 1）なら支持。
  一つでも match = 0 なら反証。
開示（結果を見る前に分かっていること）:
  - 見込みは、type_checker.py の gather（個体の事実を I[個体][short(T.end(verb, other))] に入れ、
    many でない欄に 2 つ以上あれば誤りにする）を読んで立てた。
  - c2 と同じ形（d_metric から v_depend を 2 つ）と、c3 と同じ形（d_road_japanese から v_depend と v_raise）は、
    #379 を作るときに体系のファイルで一度落ちている（記録はしていない）。だから c2・c3 の見込みは、ほぼ知った上での確かめ。
    予想が立たないのは c4（v_raise と v_lower。どちらも continuant を終点に持つ兄弟）と c6。
  - 終了コードだけでなく誤りの行を数えるのは、見本が別の理由（端を占められない等）で落ちるのを分けるため。

行（sys_fact_slot_by_end.json）: "case <名前>": {facts, expect_fail, exit, n_err, slot_err, other_err, fails, match},
  "summary 要約": {n_case, n_match, base_ok, clean（落ちる見本の誤りが slot_err だけか）, verdict_support}
使い方:
  python exp/experiments/sys_fact_slot_by_end.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_fact_slot_by_end.json"
PROBE = "d_probe"
CASES = {
    "base": ([], False),
    "c1_one": ([("v_depend", "d_metric")], False),
    "c2_same_verb": ([("v_depend", "d_metric"), ("v_depend", "d_road_region")], True),
    "c3_two_verbs": ([("v_depend", "d_metric"), ("v_raise", "d_road_region")], True),
    "c4_siblings": ([("v_raise", "d_metric"), ("v_lower", "d_road_region")], True),
    "c5_many": ([("v_ground", "h_ambiguity_is_region_choice"), ("v_ground", "h_writing_depends_checker")], False),
    "c6_two_ends": ([("v_depend", "d_metric"), ("v_ground", "h_ambiguity_is_region_choice")], False),
}


def patched(src, facts):
    lines = src.split("\n")
    i = lines.index("individuals:")
    lines.insert(i + 1, f"  {PROBE}: {{is: design_dec_tentative}}")
    while lines and lines[-1] == "":
        lines.pop()
    lines += [f"  - {{is: {v}, from: {PROBE}, to: {t}}}" for v, t in facts]
    return "\n".join(lines) + "\n"


def run_case(work, src, facts):
    (work / "exp/src/exp.yaml").write_text(patched(src, facts), encoding="utf-8")
    p = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=work,
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"検査に失敗: (\d+) 件", out)
    lines = [ln for ln in out.split("\n") if ln.startswith(" -")]
    slot = [ln for ln in lines if PROBE in ln and "関係 continuant の事実が2つ以上ある" in ln]
    other = [ln for ln in lines if PROBE in ln and ln not in slot]
    return {"exit": p.returncode, "n_err": int(m.group(1)) if m else 0, "slot_err": 1 if slot else 0,
            "other_err": len(other), "lines": lines[:5]}


def main():
    src = (ROOT / "exp/src/exp.yaml").read_text(encoding="utf-8")
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        for name, (facts, expect) in CASES.items():
            r = run_case(work, src, facts)
            fails = 1 if r["exit"] != 0 else 0
            rows[f"case {name}"] = {"facts": [f"{v} {t}" for v, t in facts], "expect_fail": 1 if expect else 0,
                                    **r, "fails": fails, "match": 1 if fails == (1 if expect else 0) else 0}
            print(name, json.dumps(rows[f"case {name}"], ensure_ascii=False), flush=True)
    cs = list(rows.values())
    failing = [r for r in cs if r["expect_fail"]]
    s = {"n_case": len(cs), "n_match": sum(r["match"] for r in cs),
         "base_ok": 1 if rows["case base"]["exit"] == 0 else 0,
         "clean": 1 if all(r["slot_err"] == 1 and r["other_err"] == 0 and r["n_err"] == 1 for r in failing) else 0}
    s["verdict_support"] = 1 if s["base_ok"] and s["n_match"] == s["n_case"] and s["clean"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
