"""仮説 h_draw_on_with_shallow（読みの式は表示語に依存しない）を確かめる: sys_draw_on で外れた読み R2 の中身を、
法則の関係 syntax.r_shallow（浅い端だけで定義される）を使って書けば、named_mod の誤りなく式で書けるか。
結果を見る前に、この説明と手順を登録した。

系列: sys_draw_on（5dd30d4）の after は errors 1 で外れた。誤りは「法則 named_mod に反する: ontology.role,
  lang.shallow_definition が同じ限定を足している」。R2 の中身の語 shallow_definition の式
  {of: [v_depend, from], with: definition} が役割の限定と同じで、「浅い」が式に入っていなかった。
  そのあと体系のファイルは戻された。この仮説は、浅いことを r_shallow で書けば足りるかを問う。
操作（一時の写しで行う。体系のファイルは書き換えない）:
  共通 X: sys_draw_on の after と同じ追加を、今の main の写しに入れる。
    exp.yaml: v_draw_on（v_ground の次）、inspiration（basis の次）。
    claims.yaml: temporal_order, overextension（case_frame の次）、仮説 h_after_unordered, h_shallow_collects,
      h_syntax_uses_ontology（未検証）、その v_refer と v_draw_on（着想のもとは sys_draw_on と同じ 6 つの観察）。
  三つの版で、R2 の中身だけを変える:
    A（再現）: shallow_definition: {extends: quality, mod: {of: [v_depend, from], with: definition}}。
       R2 の中身は v_depend(overextension, shallow_definition)。
    B（限定に r_shallow）: shallow_definition: {extends: quality, mod: {of: [syntax.r_shallow, from], with: definition}}。
       R2 の中身は A と同じ。
    C（語を足さない）: shallow_definition を足さず、R2 の中身を
       v_depend(overextension, {is: syntax.r_shallow, from: definition}) と書く。
  display は A と B の shallow_definition に「浅い端だけの定義」を付ける（sys_draw_on と同じ）。
数える量（版ごと。tc の build を写しで 1 回）:
  errors     tc の誤りの数
  named_mod  そのうち named_mod を含む誤りの数
  V          違反の組の数（sys_draw_on と同じ数え方）
  base_V     何も足さない写しでの V
  ec_errors  exp_check の誤りの数（記述。判定に使わない）
判定（事前に決める）:
  A が errors ≥ 1 で再現し、B か C のどちらかが errors 0 かつ V = base_V なら支持。
  B と C のどちらも errors ≥ 1 か V > base_V なら反証。
  A が再現しない（errors 0）なら、判定は保留し mixed と書く（前の外れの理由が今の main では消えている）。
見込み: B は、r_shallow が動詞でも関係の位置でもないので、限定の of として受け入れられず誤りが出る見込み。
  C は、v_refer の中身の端に式を入れる書き方が既にあるので（v_level など）、通る見込みがある。
  ただし C で r_shallow が中身に入っても、浅いことは式の上で読まれるだけで、overextension の側は薄いまま（記述）。

行（sys_draw_on_with_shallow.json）:
  "summary 要約": base_V と、版ごとの errors_<v>, named_mod_<v>, V_<v>, ec_errors_<v>
  "texts": 版ごとの誤りの文（先頭 10）

使い方:
  python exp/experiments/sys_draw_on_with_shallow.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_draw_on_with_shallow.json"
CLAIMS, EXPY = "cscl/design/claims.yaml", "exp/src/exp.yaml"

EXP_ADD = [
    ("  v_ground: {display: 根拠にする, extends: v_depend, from: decision, to: basis}\n",
     "  v_draw_on: {display: から着想する, extends: v_depend, from: hypothesis, to: inspiration}\n"),
    ("  basis: {display: 根拠となる仮説, extends: hypothesis, mod: {of: [v_depend, to], with: decision}, many: true}\n",
     "  inspiration: {display: 着想のもとの観察, extends: observation, mod: {of: [v_depend, to], with: hypothesis}, many: true}\n"),
]
NODE_ANCHOR = "  case_frame: {display: 動詞の格の枠, extends: quality, mod: {of: [v_depend, from], with: syntax.position}}\n"
NODES = ("  temporal_order: {display: 時間の順序としての読み, extends: quality, mod: {of: [v_refer, from], with: syntax.base}}\n"
         "  overextension: {display: 過大拡張, extends: quality, mod: {of: [v_depend, from], with: kind}}\n")
SHALLOW = {
    "A": "  shallow_definition: {display: 浅い端だけの定義, extends: quality, mod: {of: [v_depend, from], with: definition}}\n",
    "B": "  shallow_definition: {display: 浅い端だけの定義, extends: quality, mod: {of: [syntax.r_shallow, from], with: definition}}\n",
    "C": "",
}
IND_ANCHOR = "  h_case_frame_by_signature: {is: exp.hyp_refuted}\n"
INDS = ("  h_after_unordered: {is: exp.hyp_untested}\n  h_shallow_collects: {is: exp.hyp_untested}\n"
        "  h_syntax_uses_ontology: {is: exp.hyp_untested}\n")
FACT_ANCHOR = "  - {is: exp.v_check, from: b_case_frame_by_signature, to: h_case_frame_by_signature}\n"
R2 = {
    "A": "  - {is: v_refer, from: h_shallow_collects, to: {is: v_depend, from: overextension, to: shallow_definition}}\n",
    "B": "  - {is: v_refer, from: h_shallow_collects, to: {is: v_depend, from: overextension, to: shallow_definition}}\n",
    "C": "  - {is: v_refer, from: h_shallow_collects, to: {is: v_depend, from: overextension, to: {is: syntax.r_shallow, from: definition}}}\n",
}
FACTS = ("  - {is: v_refer, from: h_after_unordered, to: {is: v_not_depend, from: temporal_order, to: syntax.form}}\n"
         "  - {is: exp.v_draw_on, from: h_after_unordered, to: o_sys_after_time_rare}\n"
         "  - {is: exp.v_draw_on, from: h_after_unordered, to: o_sys_after_mostly_used}\n"
         "{R2}"
         "  - {is: exp.v_draw_on, from: h_shallow_collects, to: o_sys_specific_depth_v_mostly_shallow}\n"
         "  - {is: exp.v_draw_on, from: h_shallow_collects, to: o_sys_specific_depth_c_rarely_shallow}\n"
         "  - {is: v_refer, from: h_syntax_uses_ontology, to: {is: v_depend, from: syntax, to: ontology}}\n"
         "  - {is: exp.v_draw_on, from: h_syntax_uses_ontology, to: o_sys_lower_syntax_uses_ontology}\n"
         "  - {is: exp.v_draw_on, from: h_syntax_uses_ontology, to: o_sys_lower_base_in_ontology}\n")

PROBE = r'''
import collections, contextlib, io, json, subprocess, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
errs = [str(e) for e in tc.errors]
V = None
if not errs:
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rel = lambda r: F.by.get(r, set())
    def two(r):
        d = collections.defaultdict(set)
        for t in rel(r):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    acc, has = two("r_acc"), two("r_has")
    V = sum(1 for x, y in rel("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
ec = subprocess.run([sys.executable, "exp/src/exp_check.py"], capture_output=True, text=True)
ec_err = sum(1 for l in (ec.stdout + ec.stderr).splitlines() if "誤り" in l or "error" in l.lower())
print(json.dumps({"errors": len(errs), "named_mod": sum("named_mod" in e for e in errs), "V": V,
                  "ec_errors": ec_err if ec.returncode else 0, "texts": errs[:10]}, ensure_ascii=False))
'''


def put(s, anchor, add, after=True):
    assert s.count(anchor) == 1, anchor
    return s.replace(anchor, anchor + add if after else add + anchor)


def run(version):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        if version:
            e = Path(d) / EXPY
            s = e.read_text(encoding="utf-8")
            for a, add in EXP_ADD:
                s = put(s, a, add)
            e.write_text(s, encoding="utf-8")
            c = Path(d) / CLAIMS
            s = c.read_text(encoding="utf-8")
            s = put(s, NODE_ANCHOR, NODES + SHALLOW[version])
            s = put(s, IND_ANCHOR, INDS)
            s = put(s, FACT_ANCHOR, FACTS.replace("{R2}", R2[version]))
            c.write_text(s, encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    base = run(None)
    summ, texts = {"base_errors": base["errors"], "base_V": base["V"]}, {"base": base["texts"]}
    for v in "ABC":
        r = run(v)
        summ |= {f"errors_{v}": r["errors"], f"named_mod_{v}": r["named_mod"], f"V_{v}": r["V"], f"ec_errors_{v}": r["ec_errors"]}
        texts[v] = r["texts"]
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ}, "texts": texts}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, t in texts.items():
        for e in t:
            print(k, e)


if __name__ == "__main__":
    main()
