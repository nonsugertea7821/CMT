"""h_base_verb_found_by_shape を確かめる: 型検査が「依存する」を形（holds・from・to）だけで見つければ、v_rely の持ち上げは解けるか。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, [syntax.holds, syntax.from, syntax.to]))。登録 #898。
  出どころ: #897（h_domain_sep_by_lifting、反証）で、exp.v_rely を ontology へ移し ontology.v_depend の extends を v_rely にすると、
  tc が「役割だが、根拠となる定義（依存する定義）がない」で落ちた。型検査（anchor）は「依存する」を、
  生起体（occurrent）を直に extends するもの（under_o）の中から、holds・from・to の形で選ぶ。v_depend が v_rely の下位になると、
  under_o から外れて見つからない。
  問い: 位置の条件（under_o）を外し、形の条件だけで選べば、今の体系でも 1 つに決まり、v_rely の持ち上げで tc が通り、分かれるか。

操作（一時の写し。体系のファイルも型検査も書き換えない）:
  1. 写し（.git・__pycache__・.wt_* を除く）を作り、写しの type_checker.py の 1 行を替える:
     「self.v_depend = one("依存する", [x for x in under_o if」→「self.v_depend = one("依存する", [x for x in N if」。
     形の条件（holds が depend from→to だけ、from と to が持続体）はそのまま残す。替える文字列がちょうど 1 つでなければ外れ。
  2. 対照: 替えた写しで tc が通り、写しの上で sys_domain_sep_by_lifting.py --probe の sep が、元（替えない読み）の sep と同じこと。
  3. 替えた写しの上で sys_domain_sep_by_lifting.py をそのまま走らせる（#897 と同じ手順。結果は写しの中に書かれ、リポジトリの結果は上書きしない）。
     写しの結果から、W ごとの tc_ok・solved と要約を読む。
行（sys_base_verb_by_shape.json）: "control 替えた写し"・"lift <W>"（写しでの持ち上げ）・"summary 要約"

判定（事前に決める）:
  替える文字列が 1 つでない、対照が落ちる（tc が落ちる、または sep が変わる）、写しの持ち上げが走らないのどれかなら外れ（状態を変えない）。
  支持: 写しで exp.v_rely の持ち上げが解ける（tc が通り、solved）。
  反証: 写しで exp.v_rely の持ち上げが解けない。
  記述: 3 つの W それぞれの tc_ok・solved・tc の末尾、写しの持ち上げの要約（n_w_solved・n_tc_fail）。
開示:
  - #897 の結果と、type_checker.py の anchor を読んでから書いた。形の条件に当たるノードを grep で数えた:
    holds が depend from→to だけのものは ontology.v_depend（from・to が continuant）と exp.v_rely（any）、
    syntax.v_measure は holds に refer も持つ。だから形だけでも 1 つに決まると予想している。
  - 落ちうる所として、v_depend が v_rely を extends したとき、ほかの法則（狭める・役割の根拠）が別の所で位置に頼っていることを予想している。
    その場合は反証で、落ちた検査の文を記述に残す。
  - 支持でも、型検査そのものを替える採用は別の PR（手で見る）。この PR は写しの上で確かめるだけ。
使い方:
  python exp/experiments/sys_base_verb_by_shape.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_base_verb_by_shape.json"
sys.path[:0] = [str(Path(__file__).resolve().parent)]
from sys_domain_sep_by_extends import IGNORE, run_tc  # noqa: E402

OLD = 'self.v_depend = one("依存する", [x for x in under_o if'
NEW = 'self.v_depend = one("依存する", [x for x in N if'
LIFT = "exp/experiments/sys_domain_sep_by_lifting.py"


def probe(dst):
    p = subprocess.run([sys.executable, str(dst / LIFT), "--probe"], cwd=dst, capture_output=True, text=True)
    lines = [l for l in p.stdout.splitlines() if l.startswith("PROBE ")]
    return json.loads(lines[-1][6:]) if lines else {"error": (p.stdout + p.stderr).strip().splitlines()[-3:]}


def main():
    rows = {}
    base = probe(ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "repo"
        shutil.copytree(ROOT, dst, ignore=IGNORE)
        tcf = dst / "cscl/bootstrap/type_checker/type_checker.py"
        src = tcf.read_text(encoding="utf-8")
        n_old = src.count(OLD)
        c = {"n_old": n_old, "base_n_sep": len(base.get("sep", [])) if "sep" in base else None}
        ok = same = False
        if n_old == 1:
            tcf.write_text(src.replace(OLD, NEW), encoding="utf-8")
            ok, tail = run_tc(dst)
            pr = probe(dst)
            same = "sep" in base and pr.get("sep") == base["sep"]
            c.update(tc_ok=ok, tc_tail=tail, probe_same=int(same))
        rows["control 替えた写し"] = c
        control = bool(n_old == 1 and ok and same)
        lifted = None
        if control:
            p = subprocess.run([sys.executable, str(dst / LIFT)], cwd=dst, capture_output=True, text=True)
            lf = dst / "exp/experiments/results/sys_domain_sep_by_lifting.json"
            if p.returncode == 0 and lf.exists():
                lifted = json.loads(lf.read_text(encoding="utf-8"))["rows"]
            else:
                c["lift_error"] = (p.stdout + p.stderr).strip().splitlines()[-5:]
    if lifted:
        for k, v in lifted.items():
            if k.startswith("lift "):
                rows[k] = {kk: v.get(kk) for kk in ("U", "retarget", "fit", "tc_ok", "tc_tail", "solved", "left", "new_sep")}
        rely = lifted.get("lift exp.v_rely") or {}
        ls = lifted.get("summary 要約") or {}
    if not control or not lifted or "lift exp.v_rely" not in lifted:
        verdict = "外れ"
    else:
        verdict = "支持" if rely.get("solved") else "反証"
    s = {"control_ok": int(control), "lift_ran": int(bool(lifted)),
         "rely_tc_ok": int(bool(lifted and rely.get("tc_ok"))), "rely_solved": int(bool(lifted and rely.get("solved"))),
         "n_w_solved": ls.get("n_w_solved") if lifted else None, "n_tc_fail": ls.get("n_tc_fail") if lifted else None,
         "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
