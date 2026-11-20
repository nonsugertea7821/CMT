"""h_required_by_laws を確かめる: 法則が求める文（syntax.required）の中身に、法則の集まり（laws）への指定を足すと、
法則を確かめる時点（runtime.law_check）と一致し、ほかは変わらないか。

仮説（claims.yaml）: v_refer(h, v_depend(syntax.required, syntax.laws))。登録 #489。
  出どころ #488（h_rule_nouns_agree_runtime、反証）: 変種 N で required は always を、law_check は laws を指し、
  共通の相手がなかった。対の h_law_check_by_always（#490）は逆向き（law_check を always に）で、別の PR（#500）。

手順（体系のファイルは変えない。写しの上で変える）:
  変種 N: #484 の変種 N（sys_rule_roles_by_named_mod の edit_system と edit_checker）。基準。
  変種 B: N に加えて、syntax.yaml の required の mod を refer_from_always から
    [refer_from_always, refer_from_laws] に変える（mod を列で書く。体系のデータに前例はない。
    N の検査器の RULE_ROLE は列を読む）。
  測るもの: sys_law_check_by_always の measure と同じ（errors、ec_errors、laws_hash、R、9 つの対）。
  行（sys_required_by_laws.json）: "variant N/B"、"summary 要約"。

判定（事前に決める。B について）:
  支持: B の errors = 0、ec_errors = 0、laws_hash が N と同じ、対角の一致が 3、対角でない一致が 0、
    laws が R(required) にある。
  1 つでも外れれば反証。N の errors が 0 でなければ外れ（判定しない）。

開示: #500 で A（law_check → always）の結果（支持）を見たあとに書いた。N の値も #488・#500 で見ている。
使い方:
  python exp/experiments/sys_required_by_laws.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_required_by_laws.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_law_check_by_always as LCA

OLD = "mod: refer_from_always"
NEW = "mod: [refer_from_always, refer_from_laws]"


def edit_required(d):
    p = d / "cscl/library/syntax/syntax.yaml"
    lines = p.read_text(encoding="utf-8").split("\n")
    n = 0
    for i, l in enumerate(lines):
        if l.startswith("  required: {") and OLD in l:
            lines[i] = l.replace(OLD, NEW)
            n += 1
    p.write_text("\n".join(lines), encoding="utf-8")
    return n


def main():
    res, s = LCA.run(edit_required, OUT)
    s["X_laws_in_R"] = int("syntax.laws" in res["X"]["R"]["syntax.required"])
    s["verdict"] = ("外れ" if s["N_errors"] != 0 else
                    "支持" if (s["X_errors"] == 0 and s["X_ec_errors"] == 0 and s["X_laws_same"] == 1 and s["X_diag_agree"] == 3
                              and s["X_off_agree"] == 0 and s["X_laws_in_R"] == 1) else "反証")
    LCA.write(OUT, res, s, {"N": "N", "X": "B"})


if __name__ == "__main__":
    main()
