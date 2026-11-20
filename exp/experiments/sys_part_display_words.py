"""仮説 h_part_display_by_word_facts（part_display_explicit は、表示語の言い方を文にすれば規則で書ける:
v_depend(syntax.law_relation, [syntax.display, syntax.holds])）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: h_law_given_by_facts（#436）を、残りの law_given ごとに確かめる五つ目で、最後のもの
  （named_mod、definition_stratified、world_declared、part_fact_direction の次）。対の仮説 h_part_display_from_formula
  （表示語を holds の式から訳せば、この法則は要らなくなる）とは別に確かめる。こちらは法則を残したまま規則に移せるかを見る。
  part_display_explicit（check_parts の後半）は、動詞でないノードの自分の限定 m ごとに、役割（部分か全体か）が決まるなら:
    表示名に曖昧な言い方（「から部分になる」「へ部分になる」など）があれば咎める（neg の限定でも咎める）。
    neg でない限定で、役割が部分なのに「を…に持つ」、全体なのに「の…である」の言い方があれば咎める。
  言い方は part_words(T) が、部分の動詞（T.v_parts）の表示語から作る。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  検査器の写しの syntax_facts に文を足す（Python の検査はそのまま残し、比べる）:
    前の実験（sys_part_direction）と同じ holds の部分の文: part_of_verb、part_from、part_to、position
    言い方の文（表示語の部分文字列を読むのは、ここで Python が行う。規則が読むのはこの文だけ）:
      ノード n の表示名に part_words の明示の from の言い方があれば says_part_side(n)、to の言い方があれば says_whole_side(n)、
      曖昧な言い方があれば says_vague(n)
  syntax.yaml の写しに、関係と規則を足す（関係はすべて law_relation。表示語は「試しの関係」「試しの規則」に、いろはの一字を付ける）:
    r_vpart_XY・r_t_part・r_t_whole: 前の実験と同じ（限定 t の役割）
    r_t_role(t): r_t_part(t) か r_t_whole(t)
    r_isverb(n): r_end_from(n, x) かつ r_end_to(n, y)（T.is_verb と同じ）
    disp_vague:      mod(var1, var2)、r_t_role(var2)、r_isverb(var1) でない なら、says_vague(var1) でないことを求める
    disp_dir_part:   mod(var1, var2)、r_t_part(var2)、neg(var2) でない、r_isverb(var1) でない なら、says_whole_side(var1) でないことを求める
    disp_dir_whole:  mod(var1, var2)、r_t_whole(var2)、neg(var2) でない、r_isverb(var1) でない なら、says_part_side(var1) でないことを求める
版（claims の写しにノードを足す。種類はどれも quality の下）:
  B 何も足さない
  V 曖昧: zz_a「試しBから部分になる試しA」、限定 {of: [v_compose, from], with: zz_b}
  R 部分の向きに逆: zz_a「試しBを部分に持つ試しA」、限定 {of: [v_compose, from], with: zz_b}
  W 全体の向きに逆: zz_a「試しBの部分である試しA」、限定 {of: [v_compose, to], with: zz_b}
  S 時間的な部分で逆: zz_a「試しBを時間的な部分に持つ試しA」、限定 {of: [v_stage, from], with: zz_b}
  N 否定の限定: zz_a「試しBを部分に持つ試しA」、限定 {of: [v_compose, from], with: zz_b, neg: true}
  K 向きが合う: zz_a「試しBの部分である試しA」、限定 {of: [v_compose, from], with: zz_b}
  （zz_b は「試しB」、quality の下）
  版ごとに、文と規則を足した写しと、足さない対照（版の書き換えだけ）で、tc.build() を 1 回ずつ走らせる。
数える量（版 v ごと）:
  py_<v>     法則 part_display_explicit（Python）の誤りの数
  rule_<v>   規則 disp_vague・disp_dir_part・disp_dir_whole の誤りの数
  agree_<v>  Python の誤りの (曖昧か向きか, ノード) の集まりと、規則の誤りの (曖昧か向きか, var1) の集まりが等しければ 1
  other_<v>  足した写しの誤りのうち、上の法則の誤りでも、同じ版の対照の誤りでもないものの数
  ctrl_<v>   対照の誤りの数
判定（事前に決める）:
  すべての版で agree = 1 かつ other = 0 で、py_V ≥ 1、py_R ≥ 1、py_W ≥ 1、py_S ≥ 1、py_N = 0、py_K = 0 なら支持。
  other がどれも 0 で、agree = 0 の版が一つでもあれば反証。
  other ≥ 1 の版があれば、手順の誤りとして開示し、状態を変えない。
範囲: part_display_explicit の一つだけ。h_part_display_from_formula と h_law_given_by_facts の状態は、この手順では変えない。
  支持でも、表示語の部分文字列を読むことは Python に残る（言い方の文を作るところ）。規則に移るのは、役割と言い方の照合だけ。
行（sys_part_display_words.json）:
  "summary 要約": 上の量
  "texts": 版ごとの誤りの文（先頭 6）と、対照の誤りの文（先頭 6）

使い方:
  python exp/experiments/sys_part_display_words.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_part_display_words.json"
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
        _pw, _pv = part_words(self)
        for nid, n in self.N.items():
            disp = n.get("display") or ""
            if any(w in disp for w in _pw["from"]):
                add("says_part_side", nid)
            if any(w in disp for w in _pw["to"]):
                add("says_whole_side", nid)
            if any(w in disp for w in _pv):
                add("says_vague", nid)
'''
NODE_ANCHOR = "  is_from_lang_decision: {display: 言語の設計の決定へ属する（始点）, extends: quality, of: [is, from], with: lang_decision}\n"
ZB = "  zz_b: {display: 試しB, extends: quality}\n"
node = lambda disp, m: f"  zz_a: {{display: {disp}, extends: quality, mod: {m}}}\n" + ZB
CASES = {
    "B": "",
    "V": node("試しBから部分になる試しA", "{of: [v_compose, from], with: zz_b}"),
    "R": node("試しBを部分に持つ試しA", "{of: [v_compose, from], with: zz_b}"),
    "W": node("試しBの部分である試しA", "{of: [v_compose, to], with: zz_b}"),
    "S": node("試しBを時間的な部分に持つ試しA", "{of: [v_stage, from], with: zz_b}"),
    "N": node("試しBを部分に持つ試しA", "{of: [v_compose, from], with: zz_b, neg: true}"),
    "K": node("試しBの部分である試しA", "{of: [v_compose, from], with: zz_b}"),
}
SYN_IND_ANCHOR = "  part_display_explicit: {is: law_given, display: 部分の限定を持つ種類の表示名は、どちらが部分かを明示し、限定の向きと合う}\n"
SYN_FACTS_ANCHOR = "  - {is: v_govern, from: part_display_explicit, to: concept_expression}\n"
IROHA = "いろはにほへとちりぬるをわかよたれそつねならむうゐのおくやまけふこえてあさきゆめみしゑひもせす"
PAIRS = {"f": "from", "t": "to", "n": "new"}
VP = ["ft", "tf", "fn", "tn", "nf", "nt"]
ROLE = [
    ("part", "from", False, "ft"), ("part", "to", False, "tf"), ("part", "from", True, "fn"), ("part", "to", True, "tn"),
    ("whole", "from", False, "tf"), ("whole", "to", False, "ft"), ("whole", "from", True, "nf"), ("whole", "to", True, "nt"),
]
REL = ["part_of_verb", "part_from", "part_to", "says_part_side", "says_whole_side", "says_vague",
       "r_t_part", "r_t_whole", "r_t_role", "r_isverb"] + [f"r_vpart_{p}" for p in VP]
RULES = [f"vpart_{p}" for p in VP] + [f"role_{i}" for i in range(len(ROLE))] + [
    "role_any_part", "role_any_whole", "isverb", "disp_vague", "disp_dir_part", "disp_dir_whole"]


def syn_ind():
    s = "".join(f"  {r}: {{is: law_relation, display: 試しの関係{IROHA[i]}}}\n" for i, r in enumerate(REL))
    return s + "".join(f"  {r}: {{is: law_rule, display: 試しの規則{IROHA[i]}}}\n" for i, r in enumerate(RULES))


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
        A(f"role_any_{role}", f"{{is: r_t_{role}, from: var1}}")
        D(f"role_any_{role}", "{is: r_t_role, from: var1}")
    A("isverb", "{is: r_end_from, from: var1, to: var2}")
    A("isverb", "{is: r_end_to, from: var1, to: var3}")
    D("isverb", "{is: r_isverb, from: var1}")
    for r, t, neg, said in (("disp_vague", "r_t_role", False, "says_vague"),
                            ("disp_dir_part", "r_t_part", True, "says_whole_side"),
                            ("disp_dir_whole", "r_t_whole", True, "says_part_side")):
        A(r, "{is: mod, from: var1, to: var2}")
        A(r, f"{{is: {t}, from: var2}}")
        if neg:
            A(r, "{is: neg, from: var2, to: true, neg: true}")
        A(r, "{is: r_isverb, from: var1, neg: true}")
        Q(r, f"{{is: {said}, from: var1, neg: true}}")
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
        if CASES[case]:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + CASES[case])
        r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return ["probe failed: " + r.stderr[-300:]]


def py_key(e):
    m = re.search(r"法則 part_display_explicit に反する: (\S+) の表示名「[^」]*」(は、どちらが部分かが曖昧|が、限定の向き)", e)
    return ("vague" if "曖昧" in m.group(2) else "dir", m.group(1)) if m else None


def rule_key(e):
    m = re.search(r"var1=([^,\s]+)", e)
    if not m:
        return None
    return ("vague" if "法則 disp_vague" in e else "dir", m.group(1))


RULE_LAWS = ("法則 disp_vague", "法則 disp_dir_part", "法則 disp_dir_whole")


def main():
    summary, texts = {}, {}
    for c in CASES:
        errs = run(c, True)
        ctrl = run(c, False)
        py = [e for e in errs if "法則 part_display_explicit" in e]
        ru = [e for e in errs if any(w in e for w in RULE_LAWS)]
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
