"""仮説 h_part_display_own_phrase（表示語は holds と上位から組み立つ。法則 part_display_explicit が自分の限定の句だけを読めば、
式から訳した表示語で誤りは出ない: v_depend(syntax.display, [syntax.holds, syntax.extends])）を確かめる。結果を見る前に、この説明と手順を登録した。

背景: h_part_display_from_formula の反証（#450）。式から訳した表示語 99 に置き換えると、part_display_explicit が 3 つ咎めた。
  3 つとも、逆向きの言い方は上位の表示語から来ていた（例: exp.prosodic_phrase の訳「発話の部分である」＋上位「語を部分に持つ情報」）。
操作（一時の写しで行う。体系のファイルも検査器も書き換えない）:
  検査器の写しの check_parts で、表示名を読む前に、自分の句に限る:
    上位の表示語 u があり、表示名が u で終わり、表示名が u そのものでなければ、表示名から末尾の u を除いたものを読む。
    そうでなければ、表示名をそのまま読む（今の法則と同じ）。
  訳し方は #450 の訂正（sys_part_display_formula_fix.py）と同じ。
走らせるもの（どれも tc.build() を 1 回）:
  O0 体系のまま、検査器は今のまま
  O1 体系のまま、検査器は自分の句に限る写し
  合成の版（claims の写しにノードを足す。検査器は自分の句に限る写し。種類は quality の下、zz_b は「試しB」）:
    V 「試しBから部分になる試しA」、限定 {of: [v_compose, from], with: zz_b}
    R 「試しBを部分に持つ試しA」、同じ限定
    W 「試しBの部分である試しA」、限定 {of: [v_compose, to], with: zz_b}
    S 「試しBを時間的な部分に持つ試しA」、限定 {of: [v_stage, from], with: zz_b}
    N 「試しBを部分に持つ試しA」、限定 {of: [v_compose, from], with: zz_b, neg: true}
    K 「試しBの部分である試しA」、限定 {of: [v_compose, from], with: zz_b}
    P 上位の表示語で終わる逆向き: zz_c「試しC」（quality の下）、zz_a は zz_c の下で「試しBを部分に持つ試しC」、限定 {of: [v_compose, from], with: zz_b}
    Q 逆向きの言い方が上位の表示語の中だけ: zz_c「試しDを部分に持つ試しC」（quality の下、限定なし）、
      zz_a は zz_c の下で「試しBの部分である試しDを部分に持つ試しC」、限定 {of: [v_compose, from], with: zz_b}
  D 部分の限定を持つ動詞でないノードを式から訳した表示語に置き換えた体系で、検査器は自分の句に限る写し
数える量:
  lost / gained  O0 にあって O1 にない誤りの数 / O1 にあって O0 にない誤りの数
  py_<v>         版 v（V R W S N K P Q）の、法則 part_display_explicit の誤りの数
  ok_synth       py_V、py_R、py_W、py_S、py_P がどれも 1 以上で、py_N、py_K、py_Q がどれも 0 なら 1
  n_target / n_replaced / py_D / new_D   #450 と同じ（new_D は O1 にない D の誤りの数）
  crash          どれかのプローブが落ちたら 1
判定（事前に決める）:
  crash = 0、n_replaced = n_target で:
    lost = 0、gained = 0、ok_synth = 1、py_D = 0、new_D = 0 なら支持。
    そうでなければ反証（自分の句に限っても、訳した表示語を咎めるか、今の体系や合成の版での検査が変わる）。
  crash = 1 か n_replaced < n_target なら、手順の誤りとして開示し、状態を変えない。
範囲: 対の h_display_as_part_tree の状態は、この手順では変えない。
  一つのノードに部分と全体の限定が両方あるときの句の分け方は、この手順では見ない（平らな文字列では分けられない）。
行（sys_part_display_own_phrase.json）:
  "summary 要約": 上の量
  "texts": 版ごとの法則の誤りの文（先頭 4）、D の新しい誤りの文（先頭 10）、O0 と O1 の差の文（先頭 10）

使い方:
  python exp/experiments/sys_part_display_own_phrase.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_part_display_own_phrase.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
CLAIMS = "cscl/design/claims.yaml"
OWN_OLD = """    for nid, n in T.N.items():
        disp = n.get("display") or ""
        if T.is_verb(nid):
"""
OWN_NEW = """    for nid, n in T.N.items():
        disp = n.get("display") or ""
        _u = (T.N.get(T.up(nid)) or {}).get("display") or ""
        if _u and disp.endswith(_u) and disp != _u:
            disp = disp[: -len(_u)]
        if T.is_verb(nid):
"""
NODE_ANCHOR = "  is_from_lang_decision: {display: 言語の設計の決定へ属する（始点）, extends: quality, of: [is, from], with: lang_decision}\n"
ZB = "  zz_b: {display: 試しB, extends: quality}\n"
node = lambda disp, m, up="quality": f"  zz_a: {{display: {disp}, extends: {up}, mod: {m}}}\n" + ZB
PART = "{of: [v_compose, from], with: zz_b}"
SYNTH = {
    "V": node("試しBから部分になる試しA", PART),
    "R": node("試しBを部分に持つ試しA", PART),
    "W": node("試しBの部分である試しA", "{of: [v_compose, to], with: zz_b}"),
    "S": node("試しBを時間的な部分に持つ試しA", "{of: [v_stage, from], with: zz_b}"),
    "N": node("試しBを部分に持つ試しA", "{of: [v_compose, from], with: zz_b, neg: true}"),
    "K": node("試しBの部分である試しA", PART),
    "P": node("試しBを部分に持つ試しC", PART, "zz_c") + "  zz_c: {display: 試しC, extends: quality}\n",
    "Q": node("試しBの部分である試しDを部分に持つ試しC", PART, "zz_c") + "  zz_c: {display: 試しDを部分に持つ試しC, extends: quality}\n",
}
EXPECT_ONE = ("V", "R", "W", "S", "P")
LAW = "法則 part_display_explicit"

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    try:
        T = tc.build()[0]
        crash = ""
    except Exception as e:
        T, crash = None, repr(e)
errs = [str(e) for e in tc.errors] + ([crash] if crash else [])
out = {"errors": errs, "derived": {}, "displays": {}}
if T is not None:
    out["displays"] = {k: n.get("display") for k, n in T.N.items() if n.get("display")}
    parts = lambda v: {(h["from"], h["to"]) for h in T.end(v, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"} if v in T.N else set()
    def role(m):
        if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2:
            return None
        v, pos = T.q(m["of"][0]), m["of"][1]
        wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
        P = parts(v)
        return "part" if (pos, wpos) in P else "whole" if (wpos, pos) in P else None
    disp = lambda x: "" if x is None else ((T.N.get(x) or {}).get("display") or x) if isinstance(x, str) else str(x)
    for nid, n in T.N.items():
        if T.is_verb(nid):
            continue
        words = []
        for m in n.get("mod") or []:
            r = role(m)
            if r is None:
                continue
            v = T.q(m["of"][0])
            stem = (T.N[v].get("display") or "").removesuffix("になる")
            w = (f"の{stem}でない" if m.get("neg") else f"の{stem}である") if r == "part" else (f"を{stem}に持たない" if m.get("neg") else f"を{stem}に持つ")
            words.append(disp(T.q(m["with"]) if isinstance(m.get("with"), str) else m.get("with")) + w)
        if words:
            out["derived"][nid] = "".join(words) + disp(T.up(nid))
print(json.dumps(out, ensure_ascii=False))
'''


def probe(d):
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]], "derived": {}, "displays": {}}


def patch(p, old, new):
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, old
    p.write_text(s.replace(old, new), encoding="utf-8")


def copy(d):
    shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
    shutil.copytree(ROOT / "cscl", d / "cscl")
    shutil.copytree(ROOT / "exp/src", d / "exp/src")
    shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")


def run(own, nodes=""):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        copy(d)
        if own:
            patch(d / TC, OWN_OLD, OWN_NEW)
        if nodes:
            patch(d / CLAIMS, NODE_ANCHOR, NODE_ANCHOR + nodes)
        return probe(d)


def run_derived():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        copy(d)
        before = probe(d)
        derived = before["derived"]
        files = list((d / "cscl").rglob("*.yaml")) + list((d / "exp/src").rglob("*.yaml"))
        replaced = 0
        for nid, new in derived.items():
            short = nid.split(".")[-1]
            line = f"  {short}: {{display: {before['displays'].get(nid)}, "
            hits = [p for p in files if line in p.read_text(encoding="utf-8")]
            if len(hits) == 1 and hits[0].read_text(encoding="utf-8").count(line) == 1:
                p = hits[0]
                p.write_text(p.read_text(encoding="utf-8").replace(line, f"  {short}: {{display: {new}, "), encoding="utf-8")
                replaced += 1
        patch(d / TC, OWN_OLD, OWN_NEW)
        return before, len(derived), replaced, probe(d)


def main():
    o0, o1 = run(False), run(True)
    summary, texts = {}, {}
    probes = [o0, o1]
    summary["lost"] = len([e for e in o0["errors"] if e not in o1["errors"]])
    summary["gained"] = len([e for e in o1["errors"] if e not in o0["errors"]])
    texts["O0 vs O1"] = ([e for e in o0["errors"] if e not in o1["errors"]] + [e for e in o1["errors"] if e not in o0["errors"]])[:10]
    for v, nodes in SYNTH.items():
        r = run(True, nodes)
        probes.append(r)
        law = [e for e in r["errors"] if LAW in e]
        summary[f"py_{v}"] = len(law)
        texts[f"law {v}"] = law[:4]
    summary["ok_synth"] = int(all(summary[f"py_{v}"] >= 1 for v in EXPECT_ONE) and all(summary[f"py_{v}"] == 0 for v in SYNTH if v not in EXPECT_ONE))
    before, n_target, n_replaced, dd = run_derived()
    probes += [before, dd]
    new = [e for e in dd["errors"] if e not in o1["errors"]]
    summary["n_target"] = n_target
    summary["n_replaced"] = n_replaced
    summary["py_D"] = sum(LAW in e for e in dd["errors"])
    summary["new_D"] = len(new)
    summary["crash"] = int(any(e.startswith("probe failed") for p in probes for e in p["errors"]))
    texts["new D"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
