"""sys_refer_stratified の訂正: 個体と事実を、各領域の yaml から直接読む。結果を見る前に、この手順を登録した。

訂正の理由（開示）: sys_refer_stratified は tc.build() の O から個体と事実を読んだ。O は文法とライブラリの法則の
  事実（590）と個体（218）しか持たず、claims（lang）と exp・subj の個体と事実が入っていなかった。
  そのため R が 0 になった（O の中身を数えて確かめた。exp.v_support の上位は syntax.v_agree、
  exp.v_ground の上位は ontology.v_depend で、どちらも述べる動詞ではないことも、そのとき見た）。
手順:
  読む yaml: cscl/library 以下・cscl/design/claims.yaml・exp/src の、facts を持つすべての yaml（cscl.yaml を除く）。
  各ファイルの領域 dom はファイルの domain。
  個体 dom.名前 の種類は T.resolve(is, dom)。事実の動詞・始点・終点の名前も T.resolve(名前, dom) で解く。
    動詞や種類が解けなければ、その事実・個体は数えない（数を記述に置く）。
    始点・終点は、個体の表 Iq（dom.名前 → 種類）に dom.名前 があればそれ、なければ T.resolve で解く。
  定義（述べる動詞・文・領域・R・R_same・R_cross・R_inline・S_same）は sys_refer_stratified と同じ。
    文 sentence(x): x が Iq にあり、その種類とその祖先に syntax.sentence がある。
判定: sys_refer_stratified と同じ（R_same = 0 かつ R_cross > 0 で支持、R_same > 0 で反証、R = 0 で mixed）。
数える量: errors, n_facts, n_ind, unresolved_verb, R, R_same, R_cross, R_inline, S_same
行（sys_refer_stratified_fix.json）: "summary 要約", "verb <v>": same, cross、"texts": R_same と S_same の例
使い方:
  python exp/experiments/sys_refer_stratified_fix.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_refer_stratified_fix.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, _, _ = tc.build()
    files = sorted(list((ROOT / "cscl/library").rglob("*.yaml")) + [ROOT / "cscl/design/claims.yaml"]
                   + list((ROOT / "exp/src").glob("*.yaml")))
    docs = []
    for p in files:
        D = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(D, dict) and D.get("facts") and D.get("domain"):
            docs.append((D["domain"], D))
    Iq = {}
    for dom, D in docs:
        for n, x in (D.get("individuals") or {}).items():
            k = T.resolve(x.get("is"), dom) if isinstance(x, dict) and isinstance(x.get("is"), str) else None
            if k:
                Iq[f"{dom}.{n}"] = k
    up = lambda x: [x] + T.ancestors(x) if isinstance(x, str) and x in T.N else []
    name = lambda w, dom: (f"{dom}.{w}" if f"{dom}.{w}" in Iq else T.resolve(w, dom)) if isinstance(w, str) else w
    refer = lambda v: "syntax.v_refer" in up(v)
    sentence = lambda x: isinstance(x, str) and x in Iq and "syntax.sentence" in up(Iq[x])
    domof = lambda x: x.split(".")[0]
    c = collections.Counter()
    per = collections.defaultdict(lambda: {"same": 0, "cross": 0})
    ex_r, ex_s = [], []
    for dom, D in docs:
        for f in D.get("facts") or []:
            if not isinstance(f, dict) or not isinstance(f.get("is"), str):
                continue
            c["n_facts"] += 1
            v = T.resolve(f["is"], dom)
            if not v:
                c["unresolved_verb"] += 1
                continue
            a, b = name(f.get("from"), dom), name(f.get("to"), dom)
            if sentence(a) and sentence(b) and domof(a) == domof(b):
                c["S_same"] += 1
                if len(ex_s) < 20:
                    ex_s.append(f"{v} {a} → {b}")
            if not refer(v):
                continue
            if isinstance(f.get("to"), dict):
                c["R_inline"] += 1
                continue
            if not (isinstance(a, str) and sentence(b)):
                continue
            c["R"] += 1
            if domof(a) == domof(b):
                c["R_same"] += 1
                per[v]["same"] += 1
                if len(ex_r) < 20:
                    ex_r.append(f"{v} {a} → {b}")
            else:
                c["R_cross"] += 1
                per[v]["cross"] += 1
    summ = {"errors": len(tc.errors), "n_facts": c["n_facts"], "n_ind": len(Iq), "unresolved_verb": c["unresolved_verb"]}
    summ |= {k: c[k] for k in ("R", "R_same", "R_cross", "R_inline", "S_same")}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = {"summary 要約": summ} | {f"verb {v}": x for v, x in sorted(per.items())}
    OUT.write_text(json.dumps({"rev": rev, "rows": rows, "texts": {"R_same": ex_r, "S_same": ex_s}}, ensure_ascii=False,
                              indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for v, x in sorted(per.items()):
        print(v, x)
    for e in ex_r + ["--"] + ex_s:
        print(e)


if __name__ == "__main__":
    main()
