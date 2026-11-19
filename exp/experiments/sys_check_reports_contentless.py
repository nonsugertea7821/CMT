"""h_check_reports_contentless を確かめる: exp の検査器は、中身（v_refer で述べる文）のない決定・仮説を、止まらずに誤りとして報告できるか。

仮説（exp.yaml）: v_depend(type_check_result, syntax.refer_to_sentence)。
  読み: 検査の結果は、決定や仮説が文を指していることに依存する。だから、文が欠けていれば、それは検査の結果（誤りの一件）として出るべきで、
  検査器が止まって（例外で）何も報告しないのは、依存が結果に写っていないということ。
  出どころ: sys_fact_slot_by_end の一回目で、中身のない決定 d_probe に exp_check.py の triple が KeyError で止まった。

操作: 体系のファイルも検査器も変えない。リポジトリを一時ディレクトリに写し（.git を除く）、写しで型検査器を別のプロセスで走らせる。
  検査器は二つ:
    orig   いまの exp_check.py。
    patch  exp_check.py の triple の頭に一行足したもの:
           s・p・o のどれかがなければ「<名前>: 中身（v_refer で述べる文）がない」を誤りとして数え、その先を読まない。
           置き換えの文字列がちょうど一回現れることを確かめてから置き換える。
  写しの exp/src/exp.yaml に、見本を足す（見本ごとに、もとの exp.yaml から写し直す）。
見本:
  base         何も足さない
  d_nocontent  決定 d_probe: {is: design_dec_tentative}（中身なし）
  h_nocontent  仮説 h_probe: {is: hyp_untested}（中身なし）
  それぞれを orig と patch で走らせる（6 回）。
数える（回ごと）:
  exit       終了コード
  n_err      「検査に失敗: N 件」の N（なければ 0）
  trace      出力に Traceback があれば 1
  named      誤りの行（" -" で始まる行）に見本の名前（d_probe か h_probe）を含むものがあれば 1
  reported   exit が 0 でなく、trace = 0、named = 1 なら 1
仮説からの見込み（事前に決める）:
  orig:  base は通る。d_nocontent と h_nocontent は Traceback で止まる（trace = 1、reported = 0）。
  patch: base は通る（いまの体系に中身のない決定・仮説はない）。d_nocontent と h_nocontent は reported = 1、n_err = 1。
判定（事前に決める）:
  置き換えが一回でなければ、または orig の base が通らなければ、手順が壊れているので外れとし、状態を変えない。
  patch の base が通り、patch の d_nocontent と h_nocontent がどちらも reported = 1 で n_err = 1、
    かつ orig の二つが trace = 1 なら支持（いまは依存が結果に写っておらず、一行で写せる）。
  patch の base が落ちる（いまの体系に中身のない個体がある）か、patch でも trace = 1 が残れば反証。
  それ以外（orig が止まらない、n_err が 1 でない等）は mixed。
開示（結果を見る前に分かっていること）:
  - d_nocontent の orig の止まり方は、sys_fact_slot_by_end の一回目で一度見ている（記録はその実験の結果ファイル）。
    h_nocontent は走らせていない。triple が仮説にも呼ばれることを exp_check.py の 236 行目で読んで見込みを立てた。
  - この実験は「止まらずに報告できる」を確かめるもので、検査器そのものを直す変更ではない。直すなら、手で見てもらう PR で別に出す。

行（sys_check_reports_contentless.json）: "case <見本> <検査器>": {exit, n_err, trace, named, reported, lines},
  "summary 要約": {patch_ok, base_ok, orig_trace, patch_reported, patch_base_ok, verdict_support, verdict_refute}
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_check_reports_contentless.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
EC = "exp/src/exp_check.py"
OLD = '    def triple(x, where, structural_ok=False):\n'
NEW = OLD + '        if any(k not in x for k in ("s", "p", "o")):\n            return err(f"{where}: 中身（v_refer で述べる文）がない")\n'
CASES = {"base": None, "d_nocontent": ("d_probe", "design_dec_tentative"), "h_nocontent": ("h_probe", "hyp_untested")}


def patched(src, add):
    if not add:
        return src
    lines = src.split("\n")
    i = lines.index("individuals:")
    lines.insert(i + 1, f"  {add[0]}: {{is: {add[1]}}}")
    return "\n".join(lines)


def run(work, src, add):
    (work / "exp/src/exp.yaml").write_text(patched(src, add), encoding="utf-8")
    p = subprocess.run([sys.executable, TC], cwd=work, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"検査に失敗: (\d+) 件", out)
    lines = [ln for ln in out.split("\n") if ln.startswith(" -")]
    named = 1 if add and any(add[0] in ln for ln in lines) else 0
    trace = 1 if "Traceback" in out else 0
    return {"exit": p.returncode, "n_err": int(m.group(1)) if m else 0, "trace": trace, "named": named,
            "reported": 1 if p.returncode != 0 and not trace and named else 0,
            "lines": lines[:5], "tail": out.strip().split("\n")[-1][:200]}


def main():
    src = (ROOT / "exp/src/exp.yaml").read_text(encoding="utf-8")
    ec = (ROOT / EC).read_text(encoding="utf-8")
    count = ec.count(OLD)
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        for checker, text in (("orig", ec), ("patch", ec.replace(OLD, NEW))):
            (work / EC).write_text(text, encoding="utf-8")
            for name, add in CASES.items():
                r = run(work, src, add)
                rows[f"case {name} {checker}"] = r
                print(name, checker, json.dumps(r, ensure_ascii=False), flush=True)
    g = lambda n, c: rows[f"case {n} {c}"]
    probes = ("d_nocontent", "h_nocontent")
    s = {"patch_ok": 1 if count == 1 else 0,
         "base_ok": 1 if g("base", "orig")["exit"] == 0 else 0,
         "orig_trace": sum(g(n, "orig")["trace"] for n in probes),
         "patch_reported": sum(g(n, "patch")["reported"] == 1 and g(n, "patch")["n_err"] == 1 for n in probes),
         "patch_base_ok": 1 if g("base", "patch")["exit"] == 0 else 0}
    s["verdict_support"] = 1 if (s["patch_ok"] and s["base_ok"] and s["patch_base_ok"] and s["patch_reported"] == 2
                                 and s["orig_trace"] == 2) else 0
    s["verdict_refute"] = 1 if (s["patch_ok"] and s["base_ok"]
                                and (not s["patch_base_ok"] or any(g(n, "patch")["trace"] for n in probes))) else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "patch_count": count, "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
