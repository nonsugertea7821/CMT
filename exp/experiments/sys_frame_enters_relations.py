"""h_frame_enters_relations を確かめる: #339 の関係の差は、足した枠そのものから来るか。

仮説（claims.yaml）: v_depend(syntax.law_relation, [syntax.pre, syntax.holds])。
  登録（ac16e65）の読み: h_rule_verbs_unhardcode（#339）の変種 U は、枠を足すことと、型検査の読み方を
  枠へ置き換えることを重ねていた。法則の集まりは同じで、導いた関係だけが 302004 → 301649 と変わった。
  その差は、足した枠そのものから来る。

手順（体系のファイルは変えない。写しの上で変える。#339 のスクリプトの関数を読み込んで使い、
     その main は走らせない。記録済みの結果ファイルは書き換えない）:
  変種（どれも今の main の写しから、この実験の中で新しく作る）:
    L   そのまま。
    F   枠だけを足す（#339 の edit_syntax と同じ: v_assume に pre、v_derive に post、v_require に holds、
        中身は {is: v_refer, from: from, to: to}）。型検査は変えない。
    U   枠を足し、読み方を置き換える（#339 の edit_syntax と edit_checker）。
  測るもの（各変種）: errors, ec_errors, laws_hash, rel_hash, n_rel（#339 の PROBE と同じ）。
  行（sys_frame_enters_relations.json）: "variant L/F/U": {...}, "summary 要約": {...}
    summary: F_rel_eq_U（F と U の rel_hash が同じなら 1）、F_rel_ne_L（F と L が違えば 1）、
             U_rel_ne_L、F_laws_eq_L、F_errors、n_rel_L、n_rel_F、n_rel_U
判定（事前に決める）:
  U と L の rel_hash が同じなら、#339 の差が今の main で再現しないので外れ（状態は変えない）。
  再現するとき: F_rel_eq_U = 1 かつ F_rel_ne_L = 1 なら支持。どちらかが 0 なら反証。

開示（結果を見る前に分かっていること）:
  - #339 の記録: L 302004、U 301649。#339 から main には登録の行が足されたが、syntax と法則は変わっていない。
  - 型検査は 3 回走る。
使い方:
  python exp/experiments/sys_frame_enters_relations.py
"""
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_frame_enters_relations.json"


def base():
    spec = importlib.util.spec_from_file_location("unhardcode", ROOT / "exp/experiments/sys_rule_verbs_unhardcode.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    B = base()
    res, edits = {}, {}
    for k in ("L", "F", "U"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            B.copy_tree(d)
            e = {}
            if k in ("F", "U"):
                e["syntax"] = B.edit_syntax(d)
            if k == "U":
                e["checker"] = B.edit_checker(d)
            edits[k] = e
            res[k] = B.probe(d)
    L, F, U = res["L"], res["F"], res["U"]
    s = {"F_rel_eq_U": int(F.get("rel_hash") == U.get("rel_hash")),
         "F_rel_ne_L": int(F.get("rel_hash") != L.get("rel_hash")),
         "U_rel_ne_L": int(U.get("rel_hash") != L.get("rel_hash")),
         "F_laws_eq_L": int(F.get("laws_hash") == L.get("laws_hash")),
         "F_errors": F.get("errors"), "F_ec_errors": F.get("ec_errors"),
         "n_rel_L": L.get("n_rel"), "n_rel_F": F.get("n_rel"), "n_rel_U": U.get("n_rel")}
    s["verdict_support"] = int(s["U_rel_ne_L"] == 1 and s["F_rel_eq_U"] == 1 and s["F_rel_ne_L"] == 1)
    rows = {f"variant {k}": {**res[k], "edits": edits[k]} for k in res}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in res:
        print(k, json.dumps(rows[f"variant {k}"], ensure_ascii=False)[:400])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "外れ（差が再現しない）" if not s["U_rel_ne_L"] else ("支持" if s["verdict_support"] else "反証"))


if __name__ == "__main__":
    main()
