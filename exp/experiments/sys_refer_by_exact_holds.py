"""h_refer_by_exact_holds を確かめる: 型検査器が名前で読む v_refer の区別は、holds の原子（関係と位置）の全体が
等しいことで読めるか。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, syntax.holds))。登録 8bfc38a。
  出どころ h_checker_words_by_formula（#300、mixed）: v_refer を「属 occurrent で、holds に関係 refer がある」で読むと、
  名前の集合（19）より 7 多かった（26）。余る 7 は、refer に別の関係を足す（exp.v_answer、syntax.v_measure）か、
  refer の位置が違う（syntax.v_agree と下位の exp.v_support・v_contradict・v_prior_same）か、subj.v_weekday_of。

操作: 体系のファイルも検査器も変えない。いまのリポジトリで type_checker.build() を呼び、木と節点を読むだけ（静的）。
  eff(x): x と x の上位を近い順にたどり、最初に holds を持つ節点の holds。holds を持つ節点がなければ空。
  atoms(x): eff(x) の各要素（dict）を、(is, from, to) と、ほかの鍵があればその (鍵, 値) の組を足した tuple にした集合。
  W = v_refer、G = W の extends。
  S_name = {x : is_a(x, W)}（W 自身を含む）。
  S_exact = {x : is_a(x, G) かつ atoms(x) = atoms(W)}。
  数える: n_name、n_exact、missing = |S_name − S_exact|、extra = |S_exact − S_name|、名（先頭 20）も残す。
  参考（判定の外）: #300 の読み（holds の関係の集合に refer がある）の S_form も同じく数え、#300 の 26 を再現するか見る。
行（sys_refer_by_exact_holds.json）: "word v_refer": {...}、"summary 要約": {...}

判定（事前に決める）:
  build が失敗すれば外れ（状態を変えない）。
  支持: missing = 0 かつ extra = 0。
  1 つでも外れれば反証。
開示: #300 の余る 7 の名を見ている。v_refer・v_agree・v_measure・v_answer の holds の行も見た（v_refer は
  [{is: refer, from: from, to: to}]）。名前の集合 19 の各々の holds は見ていない。
使い方:
  python exp/experiments/sys_refer_by_exact_holds.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_refer_by_exact_holds.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]


def main():
    os.chdir(ROOT)
    rows = {}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            import type_checker as tc
            T, O, Dm = tc.build()
    except Exception as e:
        rows["summary 要約"] = {"build_ok": 0, "error": str(e)[:300]}
        OUT.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(rows)
        return
    N = T.N
    res = lambda w: w if (not isinstance(w, str) or w in N) else (T.resolve(w, "signature") or w)

    def eff(x):
        for y in [x] + T.ancestors(x):
            if "holds" in N.get(y, {}):
                return N[y].get("holds") or []
        return []

    def atoms(x):
        out = set()
        for h in eff(x):
            if isinstance(h, dict):
                out.add((h.get("is"), h.get("from"), h.get("to"),
                         tuple(sorted((k, json.dumps(v, sort_keys=True, ensure_ascii=False)) for k, v in h.items() if k not in ("is", "from", "to")))))
        return out

    def rels(x):
        return {h.get("is") for y in [x] + T.ancestors(x) for h in (N[y].get("holds") or []) if isinstance(h, dict)}

    W = res("v_refer")
    G = res(N[W].get("extends"))
    aw = atoms(W)
    s_name = {x for x in N if T.is_a(x, W)}
    s_exact = {x for x in N if T.is_a(x, G) and atoms(x) == aw}
    s_form = {x for x in N if T.is_a(x, G) and {a[0] for a in aw} <= rels(x)}
    missing, extra = sorted(s_name - s_exact), sorted(s_exact - s_name)
    r = {"node": W, "genus": G, "atoms": sorted(map(str, aw)), "n_name": len(s_name), "n_exact": len(s_exact),
         "missing": len(missing), "extra": len(extra), "missing_names": missing[:20], "extra_names": extra[:20],
         "missing_atoms": {x: sorted(map(str, atoms(x))) for x in missing[:20]},
         "n_form_300": len(s_form), "extra_300": sorted(s_form - s_name)[:20]}
    rows["word v_refer"] = r
    s = {"build_ok": 1, "n_name": len(s_name), "n_exact": len(s_exact), "missing": len(missing), "extra": len(extra),
         "n_form_300": len(s_form), "verdict": "支持" if not missing and not extra else "反証"}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
