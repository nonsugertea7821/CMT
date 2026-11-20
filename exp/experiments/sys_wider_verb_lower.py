"""h_wider_verb_lower を確かめる: 端の広い動詞を下の層に置けば、狭い動詞からの extends が書ける。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.domain, [syntax.from, syntax.to]))。登録 #534（issue #535）。
  出どころ: #533（h_kind_in_shape、反証）で、下の領域の動詞が上の領域の端の広い同じ式の動詞に包含された:
  ontology.v_depend・syntax.v_use・subj の 3 つ < exp.v_rely、ontology.v_design < std.v_compute。

操作（一時の写し。体系のファイルは書き換えない）:
  写し（.git と __pycache__ を除く）を作り、次の移し替えを 1 つずつ行う。
  M1: exp.yaml の v_rely の行を ontology.yaml の v_depend の行の前へ移し、v_depend の extends を v_rely にする。
  M2: std.yaml の v_compute の行を ontology.yaml の v_design の行の前へ移し、v_design の extends を v_compute にする。
  各写しで tc を走らせ、つづけて写しの exp/experiments/sys_kind_in_shape.py（#533 の読み: 形・端・new_kind、領域の条件なし）を走らせ、
  写しの結果を読む（本物の結果ファイルには触れない）。対照: 書き換えない写しで tc が通ること。
行（sys_wider_verb_lower.json）: "control"・"move <M>"・"summary 要約"

判定（事前に決める）:
  対照の tc が落ちるか、移し替えの文字列が見つからなければ外れ（状態を変えない）。
  支持: M1・M2 のどちらでも、tc が通り、写しの読みで全対象・参考の missing = 0、かつ
    M1 では ontology.v_rely の extra が {exp.v_ground, exp.v_scope} のうちだけ、M2 では ontology.v_compute の extra が 0。
  1 つでも外れれば反証。
開示: #533 で、両動詞の端と extra の名を見ている。v_rely の名は exp の事実（決定の v_refer）で 6 回使われ、
  v_compute は std の computed・artifact_compute_from で使われる。名の解決が層をまたいで届くかはこの手順を書く前に確かめていない。
使い方:
  python exp/experiments/sys_wider_verb_lower.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_wider_verb_lower.json"
ONT = "cscl/library/ontology/ontology.yaml"
MOVES = {
    "M1": {"src": "exp/src/exp.yaml", "name": "v_rely", "before": "v_depend", "sub": "v_depend", "W": "ontology.v_rely", "row": "ref ontology.v_rely",
           "allowed": {"exp.v_ground", "exp.v_scope"}},
    "M2": {"src": "cscl/library/std/std.yaml", "name": "v_compute", "before": "v_design", "sub": "v_design", "W": "ontology.v_compute", "row": "word ontology.v_compute",
           "allowed": set()},
}


def copy():
    tmp = tempfile.mkdtemp()
    dst = Path(tmp) / "repo"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return tmp, dst


def tc_ok(dst):
    p = subprocess.run([sys.executable, str(dst / "cscl/bootstrap/type_checker/type_checker.py")], cwd=dst, capture_output=True, text=True)
    return int("検査に成功" in p.stdout), (p.stdout + p.stderr).strip().splitlines()[-4:]


def line_of(text, name):
    m = re.search(rf"^  {re.escape(name)}: \{{.*\}}\n", text, re.M)
    return m


def main():
    rows = {}
    tmp, dst = copy()
    ok, tail = tc_ok(dst)
    shutil.rmtree(tmp)
    rows["control"] = {"tc_ok": ok, "tail": tail}
    found = 1
    good = 0
    for k, m in MOVES.items():
        tmp, dst = copy()
        try:
            src = (dst / m["src"]).read_text(encoding="utf-8")
            ont = (dst / ONT).read_text(encoding="utf-8")
            a, b = line_of(src, m["name"]), line_of(ont, m["before"])
            s2 = line_of(ont, m["sub"])
            if not (a and b and s2) or "extends: occurrent" not in s2.group(0):
                found = 0
                rows[f"move {k}"] = {"found": 0}
                continue
            moved = a.group(0)
            (dst / m["src"]).write_text(src[:a.start()] + src[a.end():], encoding="utf-8")
            sub_line = s2.group(0).replace("extends: occurrent", f"extends: {m['name']}", 1)
            ont = ont.replace(s2.group(0), sub_line, 1)
            b = line_of(ont, m["before"])
            ont = ont[:b.start()] + moved + ont[b.start():]
            (dst / ONT).write_text(ont, encoding="utf-8")
            t_ok, t_tail = tc_ok(dst)
            r = {"found": 1, "tc_ok": t_ok, "tc_tail": t_tail}
            if t_ok:
                subprocess.run([sys.executable, str(dst / "exp/experiments/sys_kind_in_shape.py")], cwd=dst, capture_output=True, text=True)
                res = json.loads((dst / "exp/experiments/results/sys_kind_in_shape.json").read_text(encoding="utf-8"))["rows"]
                s = res.get("summary 要約", {})
                w = res.get(m["row"], {})
                ex = w.get("extra_names", None)
                r.update({"n_targets_off": s.get("n_targets_off"), "n_refs_off": s.get("n_refs_off"), "row_found": int(bool(w)),
                          "w_missing": w.get("missing"), "w_extra": ex, "outside": s.get("outside")})
                r["pass"] = int(s.get("n_targets_off") == 0 and s.get("n_refs_off") == 0 and bool(w) and w.get("missing") == 0
                                and ex is not None and set(ex) <= m["allowed"])
            else:
                r["pass"] = 0
            good += r["pass"]
            rows[f"move {k}"] = r
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if not ok or not found:
        verdict = "外れ"
    else:
        verdict = "支持" if good == len(MOVES) else "反証"
    s = {"control_tc_ok": ok, "found": found, "n_moves": len(MOVES), "n_pass": good,
         "m1_tc_ok": rows.get("move M1", {}).get("tc_ok", 0), "m2_tc_ok": rows.get("move M2", {}).get("tc_ok", 0), "verdict": verdict}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
