"""h_fact_slot_keeps_each_verb を確かめる: 検査器が事実を (端の種類, 動詞) ごとの欄にも入れれば、二つめの事実も残り、体系の残りは壊れないか。

仮説（claims.yaml）: v_depend(type_checker, [syntax.refer_from_occurrent, syntax.position])。
  出どころ: sys_fact_slot_by_verb（#389、支持）で、衝突の判定を動詞で分けると c3・c4 は通ったが、
  欄 I[個体][端の種類] の値は最初の事実のままで、二つめの事実は下流から読めなかった。

操作: 体系のファイルも検査器も変えない。リポジトリを一時ディレクトリに写し（.git を除く）、写しの検査器の gather を変える
  （文字列の置き換え。どれもちょうど一回現れることを確かめてから置き換える）:
    K1 (個体, 端の種類, 動詞) ごとに事実を BV に集める。
    K2 many でない欄の衝突を「同じ動詞の事実が2つ以上」にする（#389 と同じ）。
    K3 集め終えたら、BV のどの組も、欄 I[個体]["<端の種類>.<動詞>"] に入れる（many なら全部、そうでなければ一つ）。
       欄 I[個体][端の種類] は、これまでどおり（最初の事実）。
  写しの exp/src/exp.yaml には、見本の個体 d_probe（design_dec_tentative）とその中身
  {is: v_refer, from: d_probe, to: {is: v_depend, from: decision, to: basis}} と、見本の事実を足す。
  写しの中で別のプロセスを立て、type_checker.build() と exp_check の検査を走らせ、d_probe の集めた欄を読む。
見本（#389 と同じ。始点は d_probe）:
  base、c1_one、c2_same_verb、c3_two_verbs、c4_siblings、c5_many、c6_two_ends
  対照: c1・c5・c6 を、変えていない検査器でも走らせ、端の種類の欄の値を比べる。
数える（見本ごと）:
  errors     build() と exp_check の誤りの数の和
  slot_err   d_probe の「関係 continuant の事実が2つ以上ある」の誤りがあれば 1
  n_facts    見本の事実の数
  kept       d_probe の "<端>.<動詞>" の欄に入った値の数（リストは要素を数える）
  kept_ok    kept = n_facts で、どの見本の事実の終点もどこかの "<端>.<動詞>" の欄にあれば 1
  same_slot  （対照のある見本）端の種類の欄の値が、変えていない検査器と同じなら 1
仮説からの見込み（事前に決める）:
  base: errors = 0。c2: errors = 1、slot_err = 1。ほかの見本: errors = 0、kept_ok = 1。c1・c5・c6: same_slot = 1。
判定（事前に決める）:
  置き換えのどれかが一回でなければ、手順が壊れているので外れとし、状態を変えない。
  見込みがすべて当たれば支持。
  base の errors が 0 でない（足した欄で下流が壊れる）か、c3・c4 で kept_ok = 0 なら反証。それ以外の外れは mixed。
開示（結果を見る前に分かっていること）:
  - 見込みは gather と #389 の結果から立てた。足した欄を読む下流はまだない。だから支持でも、
    「残せて、残しても壊れない」までで、下流が使えば役立つかは測らない。
  - base で下流が足した欄（名前に "." を含む）をどう扱うかは、読んでいない。予想が立たないのはここ。

行（sys_fact_slot_keeps_each_verb.json）: "case <名前> <検査器>": {...}, "summary 要約": {...}

訂正（一回目の結果を見た後に書き足す。開示する）:
  一回目は 7 つのうち 6 つが見込みどおりで、外れたのは c2 だけだった（errors = 2。見込みは 1）。
  2 件は、同じ「d_probe: 関係 continuant の事実が2つ以上ある」の行が二つ並んだもの。
  原因: exp_check.build() は中で tc.build() をもう一度呼ぶ（exp_check.py の 345 行目）。手順は、言語の誤りを消さずに
  exp_check を走らせたので、言語の誤りを二度数えた。sys_rule_roles_by_frame の手順は、間で tc.errors を消していた。写しそこねた。
  見込みの理由（検査器の欄の扱い）とは関係しない、数え方の誤り。
  訂正の手順: exp_check を走らせる前に、言語の誤りを取っておいて tc.errors を消す。errors は、言語の誤りと、exp_check が足した誤りの和にする。
  見本・見込み・判定は一回目と同じ。一回目の結果ファイルは書き換えず、訂正は sys_fact_slot_keeps_each_verb_fix.json に書く。
二度目の訂正（訂正の結果を見た後に書き足す。開示する）:
  訂正（_fix.json）でも c2 は errors = 2 のままで、ほかは一回目と同じだった。
  原因: 訂正は、取っておいた言語の誤り（1 件）に、exp_check の中の tc.build() がもう一度出した同じ言語の誤り（1 件）を足していた。
  訂正の考えちがいで、二度数えることは直っていなかった。
  二度目の訂正の手順: exp_check を走らせる前に tc.errors を消し、errors は exp_check を走らせた後の tc.errors だけにする
  （exp_check.build() が言語の検査を一度と exp の検査をするので、どちらも一度ずつ数える）。
  見本・見込み・判定は変えない。一回目と訂正の結果ファイルは書き換えず、二度目は sys_fact_slot_keeps_each_verb_fix2.json に書く。
使い方:
  python exp/experiments/sys_fact_slot_keeps_each_verb.py        （一回目）
  python exp/experiments/sys_fact_slot_keeps_each_verb.py fix    （訂正）
  python exp/experiments/sys_fact_slot_keeps_each_verb.py fix2   （二度目の訂正）
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_fact_slot_keeps_each_verb.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
PROBE = "d_probe"
CONTENT = f"  - {{is: v_refer, from: {PROBE}, to: {{is: v_depend, from: decision, to: basis}}}}"
CASES = {
    "base": ([], False),
    "c1_one": ([("v_depend", "d_metric")], False),
    "c2_same_verb": ([("v_depend", "d_metric"), ("v_depend", "d_road_region")], True),
    "c3_two_verbs": ([("v_depend", "d_metric"), ("v_raise", "d_road_region")], False),
    "c4_siblings": ([("v_raise", "d_metric"), ("v_lower", "d_road_region")], False),
    "c5_many": ([("v_ground", "h_ambiguity_is_region_choice"), ("v_ground", "h_writing_depends_checker")], False),
    "c6_two_ends": ([("v_depend", "d_metric"), ("v_ground", "h_ambiguity_is_region_choice")], False),
}
CONTROL = ("c1_one", "c5_many", "c6_two_ends")
FIX = len(sys.argv) > 1 and sys.argv[1] in ("fix", "fix2")
FIX2 = len(sys.argv) > 1 and sys.argv[1] == "fix2"
PATCH = [
    ('    for i, f in enumerate(D.get("facts") or []):\n        where = f"{name} facts[{i}]"\n        if not isinstance(f, dict) or set(f) - set(T.G["facts"]) or "is" not in f:',
     '    BV = {}\n    for i, f in enumerate(D.get("facts") or []):\n        where = f"{name} facts[{i}]"\n        if not isinstance(f, dict) or set(f) - set(T.G["facts"]) or "is" not in f:'),
    ('        I[subj].setdefault(rel, []).append(val)\n',
     '        I[subj].setdefault(rel, []).append(val)\n        BV.setdefault((subj, rel, short(verb)), []).append(val)\n'),
    ('                if rel not in T.many and len(vs) > 1:',
     '                if rel not in T.many and any(len(w) > 1 for (s2, r2, _), w in BV.items() if s2 == subj and r2 == rel):'),
    ('                x[rel] = vs if rel in T.many else vs[0]\n',
     '                x[rel] = vs if rel in T.many else vs[0]\n'
     '    for (s2, r2, v2), w in BV.items():\n        I[s2][f"{r2}.{v2}"] = w if r2 in T.many else w[0]\n'),
]
RUN = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker", "exp/src"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, Dm = tc.build()
errs = [str(e) for e in tc.errors]
if FIXFLAG:
    del tc.errors[:]
with contextlib.redirect_stdout(io.StringIO()):
    import exp_check
    try:
        exp_check.build()
    except SystemExit:
        pass
    except Exception as e:
        tc.errors.append(f"exception {type(e).__name__}: {e}")
errs = (([] if FIX2FLAG else errs) + [str(e) for e in tc.errors]) if FIXFLAG else [str(e) for e in tc.errors]
x = Dm["exp"][1]["individuals"].get("PROBE", {})
print(json.dumps({"errs": errs, "slots": {k: v for k, v in x.items() if k not in ("is", "s", "p", "o")}},
                 ensure_ascii=False, default=str))
'''.replace("PROBE", PROBE).replace("FIX2FLAG", "True" if FIX2 else "False").replace("FIXFLAG", "True" if FIX else "False")


def patched(src, facts):
    lines = src.split("\n")
    lines.insert(lines.index("individuals:") + 1, f"  {PROBE}: {{is: design_dec_tentative}}")
    while lines and lines[-1] == "":
        lines.pop()
    lines += [CONTENT] + [f"  - {{is: {v}, from: {PROBE}, to: {t}}}" for v, t in facts]
    return "\n".join(lines) + "\n"


def flat(v):
    return v if isinstance(v, list) else [v]


def run_case(work, src, facts):
    (work / "exp/src/exp.yaml").write_text(patched(src, facts), encoding="utf-8")
    p = subprocess.run([sys.executable, "-c", RUN], cwd=work, capture_output=True, text=True)
    try:
        d = json.loads(p.stdout.strip().split("\n")[-1])
    except (ValueError, IndexError):
        d = {"errs": [f"probe failed: {p.stderr.strip()[-300:]}"], "slots": {}}
    slots = d["slots"]
    vkeys = {k: v for k, v in slots.items() if "." in k}
    kept_vals = [y for v in vkeys.values() for y in flat(v)]
    targets = [t for _, t in facts]
    return {"errors": len(d["errs"]), "err_text": [e[:200] for e in d["errs"][:5]],
            "slot_err": 1 if any(PROBE in e and "関係 continuant の事実が2つ以上ある" in e for e in d["errs"]) else 0,
            "n_facts": len(facts), "kept": len(kept_vals),
            "kept_ok": 1 if len(kept_vals) == len(facts) and all(any(t in str(y) for y in kept_vals) for t in targets) else 0,
            "end_slots": {k: v for k, v in slots.items() if "." not in k}, "verb_slots": vkeys}


def main():
    src = (ROOT / "exp/src/exp.yaml").read_text(encoding="utf-8")
    tc_src = (ROOT / TC).read_text(encoding="utf-8")
    counts = [tc_src.count(a) for a, _ in PATCH]
    tc_new = tc_src
    for a, b in PATCH:
        tc_new = tc_new.replace(a, b)
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git"))
        for checker, text, names in (("keep", tc_new, list(CASES)), ("orig", tc_src, list(CONTROL))):
            (work / TC).write_text(text, encoding="utf-8")
            for name in names:
                r = run_case(work, src, CASES[name][0])
                rows[f"case {name} {checker}"] = r
                print(name, checker, json.dumps(r, ensure_ascii=False), flush=True)
    for name in CONTROL:
        k, o = rows[f"case {name} keep"], rows[f"case {name} orig"]
        k["same_slot"] = 1 if k["end_slots"] == o["end_slots"] else 0
    hit = {}
    for name, (facts, expect_fail) in CASES.items():
        r = rows[f"case {name} keep"]
        if name == "base":
            hit[name] = 1 if r["errors"] == 0 else 0
        elif expect_fail:
            hit[name] = 1 if r["errors"] == 1 and r["slot_err"] == 1 else 0
        else:
            hit[name] = 1 if r["errors"] == 0 and r["kept_ok"] == 1 and r.get("same_slot", 1) == 1 else 0
    s = {"patch_ok": 1 if counts == [1] * len(PATCH) else 0, "n_case": len(hit), "n_hit": sum(hit.values()),
         "base_ok": hit["base"],
         "kept_two": rows["case c3_two_verbs keep"]["kept_ok"] + rows["case c4_siblings keep"]["kept_ok"],
         "same_slot": sum(rows[f"case {n} keep"]["same_slot"] for n in CONTROL)}
    s["verdict_support"] = 1 if s["patch_ok"] and s["n_hit"] == s["n_case"] else 0
    s["verdict_refute"] = 1 if s["patch_ok"] and (not s["base_ok"] or s["kept_two"] < 2) else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = OUT.with_name("sys_fact_slot_keeps_each_verb_fix2.json") if FIX2 else OUT.with_name("sys_fact_slot_keeps_each_verb_fix.json") if FIX else OUT
    out.write_text(json.dumps({"rev": rev, "patch_counts": counts, "hit": hit, "rows": rows}, ensure_ascii=False,
                              indent=1, default=str), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
