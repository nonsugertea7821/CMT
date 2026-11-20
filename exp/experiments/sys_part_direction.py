"""仮説 h_part_direction_by_facts（part_fact_direction は、個体の事実と動詞の holds（部分の文）を文にすれば規則で書ける:
v_depend(syntax.law_relation, [syntax.facts, syntax.holds])）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: h_law_given_by_facts（#436）を、残りの law_given ごとに確かめる四つ目（named_mod、definition_stratified、world_declared の次）。
  part_fact_direction（check_parts の前半）は、ファイルに書いた事実のうち「from が to の部分」を述べる動詞の事実 a→b について、
  b の種類が「X の部分」と限定され a の種類が X の下なら、または a の種類が「X を部分に持つ」と限定され b の種類が X の下なら咎める。
  限定の役割（部分か全体か）は、限定の動詞の holds の部分の文と、限定の位置と、相手の位置（第三のものを作る動詞なら new、
  そうでなければ反対の位置）から決まる。種類の限定は上位（T.up）から受け継ぐ。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  検査器の写しの syntax_facts に文を足す（Python の検査はそのまま残し、比べる）:
    動詞 v の holds（T.end(v, "holds")、受け継ぎを含む）の i 番目の部分の文 {is: part, from: pf, to: pt} ごとに、
      h = "holds_part v i" として part_of_verb(h, v)、part_from(h, h+" from")、part_to(h, h+" to")、
      position(h+" from", pf)、position(h+" to", pt)
      （位置の語は position の文にだけ書く。規則で位置の語を項に書けるのは position だけのため）
    各ファイルの事実（動詞が解決でき、from と to が語のもの）を t = "ifact ファイル j" として
      fact_verb(t, 動詞)、fact_from(t, a)、fact_to(t, b)（a、b は Python と同じく、個体ならそのまま、そうでなければ解決した語）
  syntax.yaml の写しに、関係と規則を足す（関係はすべて law_relation。表示語は「試しの関係」「試しの規則」に、いろはの一字を付ける）:
    r_vpart_XY(v): v の holds に「X の位置が Y の位置の部分」がある（XY は ft・tf・fn・tn・nf・nt。f=from、t=to、n=new）
    r_t_part(t)・r_t_whole(t): 限定 t の役割。
      位置 from・新しい種類なし: ft なら部分、tf なら全体。位置 to・新しい種類なし: tf なら部分、ft なら全体。
      位置 from・新しい種類あり: fn なら部分、nf なら全体。位置 to・新しい種類あり: tn なら部分、nt なら全体。
    r_mod_part(k, X)・r_mod_whole(k, X): mod(k, t)、with(t, X)、neg(t) でない、t の役割
    r_mod_part_up・r_mod_whole_up: 自分の限定と、r_parent をたどった上位の限定
    r_kind(x, k): is(x, k)（個体）か、exists(x) なら k = x
    r_part_fact(a, b): fact_verb(t, v)、r_vpart_ft(v)、fact_from(t, a)、fact_to(t, b)
    r_kmp(x, X)・r_kmw(x, X): r_kind(x, k) と r_mod_part_up(k, X)（r_mod_whole_up(k, X)）
    part_dir_part:  r_part_fact(var1, var2)、r_kmp(var2, var3)、r_kind(var1, var4) なら、r_below(var4, var3) でないことを求める
    part_dir_whole: r_part_fact(var1, var2)、r_kmw(var1, var3)、r_kind(var2, var4) なら、r_below(var4, var3) でないことを求める
版（claims の写しにノード・個体・事実を足す。種類はどれも quality の下、動詞は v_compose）:
  B 何も足さない
  P 部分の向きに反する: zz_a は「zz_b の部分」（{of: [v_compose, from], with: zz_b}）。zz_ia: zz_a、zz_ib: zz_b。事実 zz_ib は zz_ia の部分
  W 全体の向きに反する: zz_b は「zz_a を部分に持つ」（{of: [v_compose, to], with: zz_a}）。個体と事実は P と同じ
  S 下位を通る: P に、zz_c（zz_b の下位）、zz_ic: zz_c、事実 zz_ic は zz_ia の部分 を足す
  K 向きが合う: P の種類と個体で、事実 zz_ia は zz_ib の部分
  版ごとに、文と規則を足した写しと、足さない対照（版の書き換えだけ）で、tc.build() を 1 回ずつ走らせる。
数える量（版 v ごと）:
  py_<v>     法則 part_fact_direction（Python）の誤りの数
  rule_<v>   規則 part_dir_part と part_dir_whole の誤りの数
  agree_<v>  Python の誤りの (向き, a, b, X) の集まりと、規則の誤りの (向き, var1, var2, var3) の集まりが等しければ 1
  other_<v>  足した写しの誤りのうち、上の三つの法則の誤りでも、同じ版の対照の誤りでもないものの数
  ctrl_<v>   対照の誤りの数
判定（事前に決める）:
  すべての版で agree = 1 かつ other = 0 で、py_P ≥ 1、py_W ≥ 1、py_S ≥ 2 なら支持。
  other がどれも 0 で、agree = 0 の版が一つでもあれば反証。
  other ≥ 1 の版があれば、手順の誤りとして開示し、状態を変えない。
範囲: part_fact_direction の一つだけ。part_display_explicit と h_law_given_by_facts の状態は、この手順では変えない。
行（sys_part_direction.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 6）と、対照の誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_part_direction.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_part_direction.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
CLAIMS = "cscl/design/claims.yaml"
TC_ANCHOR = '        for did, d in self.O["domains"].items():\n'
TC_ADD = '''        for v in self.N:
            if not self.is_verb(v):
                continue
            for i, h in enumerate(self.end(v, "holds") or []):
                if isinstance(h, dict) and h.get("is") == "part":
                    hp = f"holds_part {v} {i}"
                    add("part_of_verb", hp, v)
                    add("part_from", hp, hp + " from")
                    add("part_to", hp, hp + " to")
                    add("position", hp + " from", h.get("from"))
                    add("position", hp + " to", h.get("to"))
        for name, dom in lib_and_domain_files():
            for j, f in enumerate(yload((SPEC / name).read_text(encoding="utf-8")).get("facts") or []):
                if not isinstance(f, dict) or not isinstance(f.get("is"), str):
                    continue
                v = self.resolve(f["is"], dom)
                r = lambda x: (x if x in self.I else (self.resolve(x, dom) or x)) if isinstance(x, str) else None
                a, b = r(f.get("from")), r(f.get("to"))
                if v and a and b:
                    t = f"ifact {name} {j}"
                    add("fact_verb", t, v)
                    add("fact_from", t, a)
                    add("fact_to", t, b)
'''
NODE_ANCHOR = "  is_from_lang_decision: {display: 言語の設計の決定へ属する（始点）, extends: quality, of: [is, from], with: lang_decision}\n"
IND_ANCHOR = "  h_part_direction_by_facts: {is: exp.hyp_untested}\n"
FACT_ANCHOR = "  - {is: exp.v_check, from: b_part_direction_by_facts, to: h_part_direction_by_facts}\n"
A_PART = "  zz_a: {display: 試しA, extends: quality, mod: {of: [v_compose, from], with: zz_b}}\n  zz_b: {display: 試しB, extends: quality}\n"
B_WHOLE = "  zz_a: {display: 試しA, extends: quality}\n  zz_b: {display: 試しB, extends: quality, mod: {of: [v_compose, to], with: zz_a}}\n"
IND_AB = "  zz_ia: {is: zz_a}\n  zz_ib: {is: zz_b}\n"
F_BA = "  - {is: v_compose, from: zz_ib, to: zz_ia}\n"
CASES = {
    "B": ("", "", ""),
    "P": (A_PART, IND_AB, F_BA),
    "W": (B_WHOLE, IND_AB, F_BA),
    "S": (A_PART + "  zz_c: {display: 試しC, extends: zz_b}\n", IND_AB + "  zz_ic: {is: zz_c}\n",
          F_BA + "  - {is: v_compose, from: zz_ic, to: zz_ia}\n"),
    "K": (A_PART, IND_AB, "  - {is: v_compose, from: zz_ia, to: zz_ib}\n"),
}
SYN_IND_ANCHOR = "  part_fact_direction: {is: law_given, display: 部分の事実は、種類の限定と向きが逆にならない}\n"
SYN_FACTS_ANCHOR = "  - {is: v_govern, from: part_fact_direction, to: concept_expression}\n"
IROHA = "いろはにほへとちりぬるをわかよたれそつねならむうゐのおくやまけふこえてあさきゆめみしゑひもせす"
PAIRS = {"f": "from", "t": "to", "n": "new"}
VP = ["ft", "tf", "fn", "tn", "nf", "nt"]
ROLE = [
    ("part", "from", False, "ft"), ("part", "to", False, "tf"), ("part", "from", True, "fn"), ("part", "to", True, "tn"),
    ("whole", "from", False, "tf"), ("whole", "to", False, "ft"), ("whole", "from", True, "nf"), ("whole", "to", True, "nt"),
]
REL = ["part_of_verb", "part_from", "part_to", "fact_verb", "fact_from", "fact_to", "r_t_part", "r_t_whole",
       "r_mod_part", "r_mod_whole", "r_mod_part_up", "r_mod_whole_up", "r_kind", "r_part_fact", "r_kmp", "r_kmw"] + [f"r_vpart_{p}" for p in VP]


def syn_ind():
    s = "".join(f"  {r}: {{is: law_relation, display: 試しの関係{IROHA[i]}}}\n" for i, r in enumerate(REL))
    rules = [f"vpart_{p}" for p in VP] + [f"role_{i}" for i in range(len(ROLE))] + [
        "mod_part", "mod_whole", "mod_part_up_own", "mod_part_up_step", "mod_whole_up_own", "mod_whole_up_step",
        "kind_is", "kind_self", "part_fact", "kmp", "kmw", "part_dir_part", "part_dir_whole"]
    return s + "".join(f"  {r}: {{is: law_rule, display: 試しの規則{IROHA[i]}}}\n" for i, r in enumerate(rules))


def syn_facts():
    L = []
    A = lambda r, x: L.append(f"  - {{is: v_assume, from: {r}, to: {x}}}\n")
    D = lambda r, x: L.append(f"  - {{is: v_derive, from: {r}, to: {x}}}\n")
    Q = lambda r, x: L.append(f"  - {{is: v_require, from: {r}, to: {x}}}\n")
    for p in VP:
        r = f"vpart_{p}"
        A(r, "{is: part_of_verb, from: var1, to: var2}")
        A(r, "{is: part_from, from: var1, to: var3}")
        A(r, f"{{is: position, from: var3, to: {PAIRS[p[0]]}}}")
        A(r, "{is: part_to, from: var1, to: var4}")
        A(r, f"{{is: position, from: var4, to: {PAIRS[p[1]]}}}")
        D(r, f"{{is: r_vpart_{p}, from: var2}}")
    for i, (role, pos, new, p) in enumerate(ROLE):
        r = f"role_{i}"
        A(r, "{is: of, from: var1, to: var2}")
        A(r, f"{{is: position, from: var1, to: {pos}}}")
        A(r, "{is: r_end_new_kind, from: var2, to: var3}" if new else "{is: r_end_new_kind, from: var2, to: var3, neg: true}")
        A(r, f"{{is: r_vpart_{p}, from: var2}}")
        D(r, f"{{is: r_t_{role}, from: var1}}")
    for role in ("part", "whole"):
        r = f"mod_{role}"
        A(r, "{is: mod, from: var1, to: var2}")
        A(r, "{is: with, from: var2, to: var3}")
        A(r, "{is: neg, from: var2, to: true, neg: true}")
        A(r, f"{{is: r_t_{role}, from: var2}}")
        D(r, f"{{is: r_mod_{role}, from: var1, to: var3}}")
        A(f"mod_{role}_up_own", f"{{is: r_mod_{role}, from: var1, to: var2}}")
        D(f"mod_{role}_up_own", f"{{is: r_mod_{role}_up, from: var1, to: var2}}")
        A(f"mod_{role}_up_step", "{is: r_parent, from: var1, to: var3}")
        A(f"mod_{role}_up_step", f"{{is: r_mod_{role}_up, from: var3, to: var2}}")
        D(f"mod_{role}_up_step", f"{{is: r_mod_{role}_up, from: var1, to: var2}}")
    A("kind_is", "{is: is, from: var1, to: var2}")
    D("kind_is", "{is: r_kind, from: var1, to: var2}")
    A("kind_self", "{is: exists, from: var1}")
    D("kind_self", "{is: r_kind, from: var1, to: var1}")
    A("part_fact", "{is: fact_verb, from: var1, to: var2}")
    A("part_fact", "{is: r_vpart_ft, from: var2}")
    A("part_fact", "{is: fact_from, from: var1, to: var3}")
    A("part_fact", "{is: fact_to, from: var1, to: var4}")
    D("part_fact", "{is: r_part_fact, from: var3, to: var4}")
    for k, role in (("kmp", "part"), ("kmw", "whole")):
        A(k, "{is: r_kind, from: var1, to: var2}")
        A(k, f"{{is: r_mod_{role}_up, from: var2, to: var3}}")
        D(k, f"{{is: r_{k}, from: var1, to: var3}}")
    A("part_dir_part", "{is: r_part_fact, from: var1, to: var2}")
    A("part_dir_part", "{is: r_kmp, from: var2, to: var3}")
    A("part_dir_part", "{is: r_kind, from: var1, to: var4}")
    Q("part_dir_part", "{is: r_below, from: var4, to: var3, neg: true}")
    A("part_dir_whole", "{is: r_part_fact, from: var1, to: var2}")
    A("part_dir_whole", "{is: r_kmw, from: var1, to: var3}")
    A("part_dir_whole", "{is: r_kind, from: var2, to: var4}")
    Q("part_dir_whole", "{is: r_below, from: var4, to: var3, neg: true}")
    return "".join(L)


PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        tc.build()
        crash = ""
    except Exception as e:
        crash = repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
print(json.dumps(errs, ensure_ascii=False))
'''


def patch(p, old, new):
    s = p.read_text()
    assert s.count(old) == 1, old
    p.write_text(s.replace(old, new))


def run(case, add):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(ROOT / "cscl", d / "cscl")
        shutil.copytree(ROOT / "exp/src", d / "exp/src")
        shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")
        if add:
            patch(d / TC, TC_ANCHOR, TC_ADD + TC_ANCHOR)
            patch(d / SYN, SYN_IND_ANCHOR, SYN_IND_ANCHOR + syn_ind())
            patch(d / SYN, SYN_FACTS_ANCHOR, SYN_FACTS_ANCHOR + syn_facts())
        nodes, inds, facts = CASES[case]
        if nodes:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + nodes)
            patch(d / CLAIMS, IND_ANCHOR, IND_ANCHOR + inds)
            patch(d / CLAIMS, FACT_ANCHOR, FACT_ANCHOR + facts)
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return ["probe failed: " + r.stderr[-300:]]


def py_key(e):
    m = re.search(r"の事実 (\S+) は (\S+) の部分だが、\S+ の種類は (\S+) の部分と限定", e)
    if m:
        return ("part", m.group(1), m.group(2), m.group(3))
    m = re.search(r"の事実 (\S+) は (\S+) の部分だが、\S+ の種類は (\S+) を部分に持つと限定", e)
    return ("whole", m.group(1), m.group(2), m.group(3)) if m else None


def rule_key(e):
    m = re.search(r"var1=([^,\s]+), var2=([^,\s]+), var3=([^,\s]+)", e)
    if not m:
        return None
    return ("part" if "法則 part_dir_part" in e else "whole", m.group(1), m.group(2), m.group(3))


def main():
    summary, texts = {}, {}
    for c in CASES:
        errs = run(c, True)
        ctrl = run(c, False)
        py = [e for e in errs if "法則 part_fact_direction" in e]
        ru = [e for e in errs if "法則 part_dir_part" in e or "法則 part_dir_whole" in e]
        other = [e for e in errs if e not in py and e not in ru and e not in ctrl]
        summary[f"py_{c}"] = len(py)
        summary[f"rule_{c}"] = len(ru)
        summary[f"agree_{c}"] = int({py_key(e) for e in py} == {rule_key(e) for e in ru})
        summary[f"other_{c}"] = len(other)
        summary[f"ctrl_{c}"] = len(ctrl)
        texts[f"errors {c}"] = (py + ru + other)[:6]
        texts[f"control {c}"] = ctrl[:6]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
