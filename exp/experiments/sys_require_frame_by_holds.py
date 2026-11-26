"""h_require_frame_by_holds を確かめる: 動詞を概念から外したうえで（concept_kind に r_verb の否定、#406 の E）、
法則の役割の枠を v_assume に pre、v_derive に post、v_require に holds で書き、
型検査が役割を名前の並び RULE_VERBS でなく枠から読んでも、誤りと導いた関係が変わらないか。

仮説（claims.yaml）: v_refer(h, v_depend(type_checker, [syntax.pre, syntax.post, syntax.holds, syntax.law_relation]))。登録 #875。
系列:
  h_rule_verbs_unhardcode（#339、反証）: 同じ枠（holds）と読み替えで errors 0、導いた関係が 355 減った。
    差は法則 concept_kind が動詞を概念から外していなかったため（#344、#406）。
  h_rule_roles_read_by_frame（#875、反証）: E の上で、v_require の枠を always にすると、
    「always の原子は基礎の関係と項 self で書く」の検査に 1 件かかった。法則と関係（枠の鍵を除く）は E と同じだった。
  ここでは、#875 の EFR の always を holds に戻す（= #339 の U に E を足す）。

手順（体系のファイルも型検査器も変えない。写しの上で変える）:
  E    写しの syntax.yaml の concept_kind に E の一行を足す（main に既にあれば足さない）。
  EF   E に、枠を足す: v_assume に pre、v_derive に post、v_require に holds（中身は 3 つとも {is: v_refer, from: from, to: to}）。
  EFR  EF に、型検査器の写しの読み替えを足す（sys_rule_verbs_unhardcode の edit_checker をそのまま使う。枠の鍵は pre・post・holds）。
  E0R  E に、読み替えだけを足す（枠なし）。対照。
  測るもの（各変種）: errors、ec_errors、err_text、laws_hash、n_rel と rel_hash（法則の評価で導いた関係。
    枠の鍵 pre・post・holds の関係は除く）、rel_all_hash と n_rel_all（何も除かない）、n_role。
  行（sys_require_frame_by_holds.json）: "variant E/EF/EFR/E0R"、"summary 要約"。

判定（事前に決める）:
  対照: E0R の errors・laws_hash・rel_hash が E とすべて同じなら外れ（読み替えが効いていない。状態は変えない）。
  E の errors が 0 でなければ外れ。
  支持: EFR の errors = 0、ec_errors = 0、laws_hash と rel_hash が E と同じ。
  反証: それ以外。
  EF と E の比べ、rel_all_hash の比べは記述。

開示（結果を見る前に分かっていること）:
  - #339 の U（E なし、holds）は errors 0 で関係が 355 減った。#406 の E+f（v_assume に holds の枠）で関係が同じだった。
  - #875 の E・EF・EFR・E0R の値（E の n_rel 419475、E0R の errors 203）。main がその後に動いていれば値は変わりうる。
  - holds の鍵の関係を rel_hash から除くのは、#875 で always を除いたのと同じ理由（枠の鍵が関係に入る）。
  - 文法の語の照合（KEYWORDS の rule_word が RULE_VERBS を使う所）は変えない。
使い方:
  python exp/experiments/sys_require_frame_by_holds.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_require_frame_by_holds.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_rule_verbs_unhardcode as U

SYN = "cscl/library/syntax/syntax.yaml"
PRE_LINE = "  - {is: v_assume, from: concept_kind, to: {is: pre, from: var1, to: var3, neg: true}}\n"
E_ADD = "  - {is: v_assume, from: concept_kind, to: {is: r_verb, from: var1, neg: true}}\n"
FRAMES = {"v_assume": "pre", "v_derive": "post", "v_require": "holds"}
assert 'frozenset({"holds"}): "require"' in U.ROLE_BLOCK

PROBE = U.PROBE.replace(
    '''    keep = []
    for r, xs in sorted(F.by.items()):
        if r.split(".")[-1] in ("pre", "post"):
            continue
        keep += [f"{r}:{x}" for x in sorted(str(x) for x in xs)]
    rel = hashlib.sha256("\\n".join(keep).encode()).hexdigest()[:16]''',
    '''    keep, alls = [], []
    for r, xs in sorted(F.by.items()):
        row = [f"{r}:{x}" for x in sorted(str(x) for x in xs)]
        alls += row
        if r.split(".")[-1] in ("pre", "post", "holds"):
            continue
        keep += row
    rel = hashlib.sha256("\\n".join(keep).encode()).hexdigest()[:16]
    rel_all = hashlib.sha256("\\n".join(alls).encode()).hexdigest()[:16]''').replace(
    '"rel_hash": rel, "n_rel": n_rel,', '"rel_hash": rel, "n_rel": n_rel, "rel_all_hash": rel_all, "n_rel_all": len(alls),')
assert "rel_all" in PROBE and '"rel_all_hash"' in PROBE


def edit_e(d):
    p = d / SYN
    t = p.read_text(encoding="utf-8")
    if E_ADD in t:
        return 0
    assert t.count(PRE_LINE) == 1
    p.write_text(t.replace(PRE_LINE, PRE_LINE + E_ADD), encoding="utf-8")
    return 1


def edit_frames(d):
    p = d / SYN
    X = "{is: v_refer, from: from, to: to}"
    lines = p.read_text(encoding="utf-8").split("\n")
    n = 0
    for i, l in enumerate(lines):
        for v, k in FRAMES.items():
            if l.startswith(f"  {v}: {{") and l.endswith("}"):
                lines[i] = l[:-1] + f", {k}: [{X}]}}"
                n += 1
    p.write_text("\n".join(lines), encoding="utf-8")
    return n


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "ec_errors": -1, "stderr": r.stderr[-800:]}
    return json.loads(out[-1])


def main():
    res = {}
    for k in ("E", "EF", "EFR", "E0R"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            U.copy_tree(d)
            e = {"e": edit_e(d)}
            if k in ("EF", "EFR"):
                e["frames"] = edit_frames(d)
            if k in ("EFR", "E0R"):
                e["checker"] = U.edit_checker(d)
            res[k] = {**probe(d), "edits": e}
    E, EF, EFR, E0R = res["E"], res["EF"], res["EFR"], res["E0R"]
    same = lambda a, b: all(a.get(m) == b.get(m) for m in ("errors", "laws_hash", "rel_hash"))
    s = {"E_errors": E.get("errors"), "E_ec_errors": E.get("ec_errors"),
         "EF_rel_same_E": int(EF.get("rel_hash") == E.get("rel_hash")),
         "EF_rel_all_same_E": int(EF.get("rel_all_hash") == E.get("rel_all_hash")),
         "EFR_errors": EFR.get("errors"), "EFR_ec_errors": EFR.get("ec_errors"),
         "EFR_laws_same_E": int(EFR.get("laws_hash") == E.get("laws_hash")),
         "EFR_rel_same_E": int(EFR.get("rel_hash") == E.get("rel_hash")),
         "EFR_rel_all_same_E": int(EFR.get("rel_all_hash") == E.get("rel_all_hash")),
         "EFR_n_role": EFR.get("n_role"), "E0R_errors": E0R.get("errors"),
         "control_differs": int(not same(E0R, E)),
         "E_n_rel": E.get("n_rel"), "EF_n_rel": EF.get("n_rel"), "EFR_n_rel": EFR.get("n_rel"), "E0R_n_rel": E0R.get("n_rel")}
    ok = (s["EFR_errors"] == 0 and s["EFR_ec_errors"] == 0 and s["EFR_laws_same_E"] == 1 and s["EFR_rel_same_E"] == 1)
    s["verdict"] = ("外れ" if (s["E_errors"] != 0 or not s["control_differs"]) else "支持" if ok else "反証")
    rows = {f"variant {k}": v for k, v in res.items()}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False)[:700])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


if __name__ == "__main__":
    main()
