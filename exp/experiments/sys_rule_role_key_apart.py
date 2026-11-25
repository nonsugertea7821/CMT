"""h_rule_role_key_apart_from_state を確かめる: 法則の役割（前提・導く・求める）の鍵を、実行器が状態の変化として読む
pre・post から離しても、型検査・実験の検査・実行器・世界の検査の結果が、#880（v_assume に pre、v_derive に post、
v_require に holds）と同じになるか。

仮説（claims.yaml）: v_refer(h, v_not_depend(syntax.law_rule, [syntax.pre, syntax.post]))。登録 #881。
系列:
  h_rule_roles_read_by_frame（#875、反証）: v_require の枠を always にすると、always の原子の検査に 1 件かかった。
  h_require_frame_by_holds（#879、支持）: v_require を holds にすると、誤り 0、法則と導いた関係が同じ。
  #880（採用）: 役割を枠の鍵の集まりで読む（{pre} → 前提、{post} → 導く、{holds} → 求める）。
    実行器が pre を持つ節を状態を変える動詞として読むため、post のない v_assume で applicable が落ち、
    n.get("post", []) で直した。役割の鍵と状態の鍵が重なっていることが、この仮説の出どころ。

手順（体系のファイルも検査器も変えない。写しの上で変える）:
  A   #880 のまま（このブランチの HEAD。#880 の上に main を合わせたもの）。基準。
  K   3 つの動詞の枠をすべて holds にする（pre・post の鍵を holds に置き換える）。
      型検査器の写しの役割の読みを、枠の鍵の集まりでなく、動詞の to（文法の節 premise・derived・required）から読むものに替える。
      役割の鍵は to の型になり、pre・post は使わない。
  K0  K の枠だけ（読み替えなし）。対照。3 つとも {holds} なので、役割は 3 つとも「求める」になるはず。
  測るもの（各変種）: errors、ec_errors、err_text、laws_hash、n_laws、rel_hash（法則の評価で導いた関係。
    枠の鍵 pre・post・holds の関係は除く）、rel_all_hash、n_role、roles（動詞ごとの役割）、
    n_pre_nodes（syntax の節で pre を持つものの数。実行器が状態を変える動詞として読む候補）、
    runtime と test_worlds の終了コード（rc）と出力の hash（out_hash）と末尾。
  行（sys_rule_role_key_apart.json）: "variant A/K/K0"、"summary 要約"。

判定（事前に決める）:
  外れ: A の errors・ec_errors が 0 でない、A の runtime・test_worlds の rc が 0 でない、
        または K0 の errors・laws_hash・rel_hash・runtime の rc がすべて A と同じ（対照が効いていない）。
  支持: K の errors = 0、ec_errors = 0、laws_hash と rel_hash が A と同じ、
        runtime と test_worlds の rc が 0 で out_hash が A と同じ。
  反証: それ以外。
  rel_all_hash の比べ、n_pre_nodes の差は記述（枠の鍵が変わるので rel_all は変わりうる）。

開示（結果を見る前に分かっていること）:
  - K の読み替えは、premise・derived・required という文法の節の名前を役割に写す。名前で読むのは文法の語に限る
    という取り決めの内だが、この 3 つの節を区別するのは名前と mod の of（[v_assume, to] など）だけで、
    of の動詞名をたどると、役割が動詞名から来ることになる。読み替えは to の節名で書く。
  - #879 の測りで、E（concept_kind に r_verb の否定）の上の誤り 0 は分かっている。いまの main ではその行の有無を見ない。
  - 実行器（runtime.py）は law_rules と core_sections を通して役割を読む。runtime と test_worlds の出力に、
    時刻のような走るたびに変わる値があれば out_hash は A 同士でも合わない。そのときは out_hash を記述に回し、rc で判定する
    （その場合は訂正として開示する）。
使い方:
  python exp/experiments/sys_rule_role_key_apart.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_rule_role_key_apart.json"
sys.path.insert(0, str(ROOT / "exp/experiments"))
import sys_require_frame_by_holds as R

SYN = "cscl/library/syntax/syntax.yaml"
TC = "cscl/bootstrap/type_checker/type_checker.py"
VERBS = ("v_assume", "v_derive", "v_require")
OLD_READ = '''                _has = frozenset(k for k in ("pre", "post", "holds") if _n.get(k))
                _r = {frozenset({"pre"}): "assume", frozenset({"post"}): "derive", frozenset({"holds"}): "require"}.get(_has)
'''
NEW_READ = '''                _r = {"premise": "assume", "derived": "derive", "required": "require"}.get(_n.get("to"))
'''

PROBE = R.PROBE.replace(
    '"n_role": len(getattr(tc, "RULE_ROLE", {}) or {})}',
    '"n_role": len(getattr(tc, "RULE_ROLE", {}) or {}), "roles": dict(sorted((getattr(tc, "RULE_ROLE", {}) or {}).items())),'
    ' "n_pre_nodes": sum(1 for _, D in [("", __import__("yaml").safe_load(open("cscl/library/syntax/syntax.yaml", encoding="utf-8")))]'
    ' for n in (D.get("nodes") or {}).values() if isinstance(n, dict) and n.get("pre"))}')
assert '"roles"' in PROBE and '"n_pre_nodes"' in PROBE


def copy_tree(d):
    for p in ("cscl.yaml", "cscl", "exp/src", "exp/tests"):
        s, t = ROOT / p, d / p
        if not s.exists():
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if s.is_dir() else shutil.copy2)(s, t)
    (d / "exp/experiments").mkdir(parents=True, exist_ok=True)
    os.symlink(ROOT / "exp/experiments/results", d / "exp/experiments/results")


def edit_frames(d):
    p = d / SYN
    lines = p.read_text(encoding="utf-8").split("\n")
    n = 0
    for i, l in enumerate(lines):
        for v in VERBS:
            if l.startswith(f"  {v}: {{"):
                new = l.replace(", pre: [", ", holds: [").replace(", post: [", ", holds: [")
                n += int(new != l)
                lines[i] = new
    p.write_text("\n".join(lines), encoding="utf-8")
    return n


def edit_checker(d):
    p = d / TC
    t = p.read_text(encoding="utf-8")
    assert t.count(OLD_READ) == 1
    p.write_text(t.replace(OLD_READ, NEW_READ), encoding="utf-8")
    return 1


def run(d, script):
    r = subprocess.run([sys.executable, script], cwd=d, capture_output=True, text=True)
    out = r.stdout + r.stderr
    return {"rc": r.returncode, "out_hash": hashlib.sha256(out.encode()).hexdigest()[:16], "tail": out.strip()[-400:]}


def main():
    res = {}
    for k in ("A", "K", "K0"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            copy_tree(d)
            e = {}
            if k in ("K", "K0"):
                e["frames"] = edit_frames(d)
            if k == "K":
                e["checker"] = edit_checker(d)
            res[k] = {**probe(d), "edits": e,
                      "runtime": run(d, "cscl/bootstrap/runtime/runtime.py"),
                      "test_worlds": run(d, "cscl/bootstrap/runtime/test_worlds.py")}
    A, K, K0 = res["A"], res["K"], res["K0"]
    same = lambda a, b, ms: all(a.get(m) == b.get(m) for m in ms)
    s = {"A_errors": A.get("errors"), "A_ec_errors": A.get("ec_errors"),
         "A_runtime_rc": A["runtime"]["rc"], "A_worlds_rc": A["test_worlds"]["rc"],
         "K_errors": K.get("errors"), "K_ec_errors": K.get("ec_errors"),
         "K_laws_same_A": int(K.get("laws_hash") == A.get("laws_hash")),
         "K_rel_same_A": int(K.get("rel_hash") == A.get("rel_hash")),
         "K_rel_all_same_A": int(K.get("rel_all_hash") == A.get("rel_all_hash")),
         "K_runtime_rc": K["runtime"]["rc"], "K_worlds_rc": K["test_worlds"]["rc"],
         "K_runtime_out_same_A": int(K["runtime"]["out_hash"] == A["runtime"]["out_hash"]),
         "K_worlds_out_same_A": int(K["test_worlds"]["out_hash"] == A["test_worlds"]["out_hash"]),
         "K_roles_same_A": int(K.get("roles") == A.get("roles")),
         "A_n_pre_nodes": A.get("n_pre_nodes"), "K_n_pre_nodes": K.get("n_pre_nodes"),
         "K0_errors": K0.get("errors"), "K0_runtime_rc": K0["runtime"]["rc"],
         "control_differs": int(not (same(K0, A, ("errors", "laws_hash", "rel_hash")) and K0["runtime"]["rc"] == A["runtime"]["rc"]))}
    bad = (s["A_errors"] != 0 or s["A_ec_errors"] != 0 or s["A_runtime_rc"] != 0 or s["A_worlds_rc"] != 0 or not s["control_differs"])
    ok = (s["K_errors"] == 0 and s["K_ec_errors"] == 0 and s["K_laws_same_A"] == 1 and s["K_rel_same_A"] == 1
          and s["K_runtime_rc"] == 0 and s["K_worlds_rc"] == 0 and s["K_runtime_out_same_A"] == 1 and s["K_worlds_out_same_A"] == 1)
    s["verdict"] = "外れ" if bad else "支持" if ok else "反証"
    rows = {f"variant {k}": v for k, v in res.items()}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False)[:900])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", s["verdict"])


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    out = [l for l in r.stdout.strip().split("\n") if l.startswith("{")]
    if not out:
        return {"errors": -1, "ec_errors": -1, "stderr": r.stderr[-800:]}
    return json.loads(out[-1])


if __name__ == "__main__":
    main()
