"""仮説 h_phrase_in_checker（検査器が限定の句を限定から作る: v_depend(syntax.display, syntax.mod)）を確かめる。
結果を見る前に、この説明と手順を登録した。

背景: #468 で部分の限定 99 の句がすべて限定の式から訳せ、#469 で、句を式から作れば表示語の法則
  （syntax.yaml の規則 disp_vague・disp_dir_part・disp_dir_whole）は何も捕まえず、除いても検査が変わらないと分かった。
  ここでは、それを体系と検査器に入れる。
変更（この登録の後の commit で行う）:
  - 検査器に関数 mod_phrases(T) を足す。#468 の写しと同じ訳し方で、部分の限定（動詞でないノードの限定で、
    動詞の holds の part と位置から部分か全体かが決まるもの）ごとに句を作る:
      相手 = with（なければ new_kind、それもなければ T.end(動詞, 反対の位置)）、句 = 表示(相手) + 言い方
      （語幹は動詞か上位の「…になる」の表示語から、なければ「部分」。neg なら否定の言い方）。
  - syntax_facts は、句を限定の文の表示語として書く（{is: display, from: 限定, to: 句}）。
  - 表示語から says_part_side・says_whole_side・says_vague を作る箇所と part_words を検査器から除き、
    文法から規則 disp_*（個体と v_assume・v_require）と関係 says_* の個体を除く。
数える量（変更の後の作業ツリーで。体系のファイルは書き換えない。走らせるのは tc、ec、写しでの build）:
  tc_ok        tc の出力に「検査に成功」があれば 1
  ec_ok        ec の終了コードが 0 なら 1
  n_disp_rules syntax.yaml の中で disp_vague・disp_dir_part・disp_dir_whole を含む行の数
  n_says       syntax_facts の文のうち、関係が says_ で始まるものの数
  n_target     部分の限定の数（上の決まり方で、この手順の中で数える）
  n_phrase     そのうち、syntax_facts に表示語の文がある数
  n_mut        書き足したノードの数
  mut_new      一時の写しで、部分の限定（neg でない）を持つノードの表示語の文に逆の向きの言い方
               （部分なら「を部分に持つ」、全体なら「の部分である」）を書き足して build したとき、書き足さない写しにない誤りの数
  crash        プローブが落ちたら 1
判定（事前に決める）:
  crash = 0 で:
    tc_ok = 1、ec_ok = 1、n_disp_rules = 0、n_says = 0、n_phrase = n_target、mut_new = 0 なら支持
      （句は限定から作られ、表示語の法則がなくても検査は通り、手で書いた表示語は検査に効かない）。
    tc_ok = 0 か n_phrase < n_target か mut_new ≥ 1 なら反証。
    それ以外は、手順の誤りとして開示し、状態を変えない。
  crash = 1 なら、手順の誤りとして開示し、状態を変えない。
範囲: 名前を付けた限定（mod の個体）の句、部分の限定でない限定の句は作らない。句の日本語の自然さは問わない（ロードマップ b）。
行（sys_phrase_in_checker.json）:
  "summary 要約": 上の量
  "texts": 句の例（先頭 10）、句のない部分の限定（先頭 10）、mut_new の文（先頭 10）

使い方:
  python exp/experiments/sys_phrase_in_checker.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_phrase_in_checker.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SYN = "cscl/library/syntax/syntax.yaml"
RULES = ("disp_vague", "disp_dir_part", "disp_dir_whole")
MUT_OLD = """            if n.get("display"):
                add("display", nid, n["display"])
"""
MUT_NEW = """            if n.get("display"):
                _w = __import__("os").environ.get("MUT") and getattr(self, "_mut", {}).get(nid)
                add("display", nid, n["display"] + (_w or ""))
"""

PROBE = r'''
import contextlib, io, json, os, sys, yaml
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    out = {"errors": [], "target": [], "phrase": {}, "n_says": 0, "mut": {}}
    try:
        def role(T, m):
            if not isinstance(m, dict) or not isinstance(m.get("of"), list) or len(m["of"]) != 2:
                return None
            v, pos = T.q(m["of"][0]), m["of"][1]
            if v not in T.N:
                return None
            wpos = "new" if T.end(v, "new_kind") else ("to" if pos == "from" else "from")
            P = {(h["from"], h["to"]) for h in T.end(v, "holds") or [] if isinstance(h, dict) and h.get("is") == "part"}
            return "part" if (pos, wpos) in P else "whole" if (wpos, pos) in P else None
        T = tc.build()[0]
        facts = T.syntax_facts()
        disp = {xs[0]: xs[1] for rel, xs in facts if rel == "display" and len(xs) == 2}
        out["n_says"] = sum(rel.startswith("says_") for rel, _ in facts)
        for nid, n in T.N.items():
            if T.is_verb(nid):
                continue
            for i, m in enumerate(n.get("mod") or []):
                r = role(T, m)
                if r is None:
                    continue
                key = f"{nid} {i}"
                out["target"].append(key)
                t = yaml.safe_dump(m, sort_keys=True, allow_unicode=True).strip()
                if t in disp:
                    out["phrase"][key] = disp[t]
                if not m.get("neg"):
                    out["mut"][nid] = "を部分に持つ" if r == "part" else "の部分である"
    except Exception as e:
        out["errors"].append("probe crash: " + repr(e))
out["errors"] = [str(e) for e in tc.errors] + out["errors"]
print(json.dumps(out, ensure_ascii=False))
'''

MUT_PROBE = r'''
import contextlib, io, json, os, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
mut = json.loads(open(os.environ["MUT_FILE"], encoding="utf-8").read())
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    crash = ""
    for _c in list(tc.__dict__.values()):
        if isinstance(_c, type) and hasattr(_c, "syntax_facts"):
            _c._mut = mut
    try:
        tc.build()
    except Exception as e:
        crash = "probe crash: " + repr(e)
print(json.dumps({"errors": [str(e) for e in tc.errors] + ([crash] if crash else [])}, ensure_ascii=False))
'''


def sh(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})


def last_json(r):
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"errors": ["probe failed: " + r.stderr[-300:]]}


def copy_tree(d):
    shutil.copy(ROOT / "cscl.yaml", d / "cscl.yaml")
    shutil.copytree(ROOT / "cscl", d / "cscl")
    shutil.copytree(ROOT / "exp/src", d / "exp/src")
    shutil.copytree(ROOT / "exp/experiments/results", d / "exp/experiments/results")


def main():
    summary, texts = {}, {}
    r = sh([sys.executable, TC], ROOT)
    summary["tc_ok"] = int("検査に成功" in r.stdout + r.stderr)
    summary["ec_ok"] = int(sh([sys.executable, "exp/src/exp_check.py"], ROOT).returncode == 0)
    summary["n_disp_rules"] = sum(any(x in l for x in RULES) for l in (ROOT / SYN).read_text(encoding="utf-8").splitlines())
    p = last_json(sh([sys.executable, "-c", PROBE], ROOT))
    target, phrase = p.get("target") or [], p.get("phrase") or {}
    summary["n_says"] = p.get("n_says", -1)
    summary["n_target"] = len(target)
    summary["n_phrase"] = sum(k in phrase for k in target)
    mut = p.get("mut") or {}
    summary["n_mut"] = len(mut)
    runs = {}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        copy_tree(d)
        s = (d / TC).read_text(encoding="utf-8")
        assert s.count(MUT_OLD) == 1
        (d / TC).write_text(s.replace(MUT_OLD, MUT_NEW), encoding="utf-8")
        mf = d / "mut.json"
        mf.write_text(json.dumps(mut, ensure_ascii=False), encoding="utf-8")
        for name, env in (("base", {"MUT_FILE": str(mf)}), ("mut", {"MUT_FILE": str(mf), "MUT": "1"})):
            runs[name] = last_json(sh([sys.executable, "-c", MUT_PROBE], d, env))
    new = [e for e in runs["mut"]["errors"] if e not in runs["base"]["errors"]]
    summary["mut_new"] = len(new)
    errs = p.get("errors", []) + runs["base"]["errors"] + runs["mut"]["errors"]
    summary["crash"] = int(any(e.startswith(("probe failed", "probe crash")) for e in errs))
    texts["phrases"] = [f"{k}: {phrase[k]}" for k in target if k in phrase][:10]
    texts["no phrase"] = [k for k in target if k not in phrase][:10]
    texts["mut new"] = new[:10]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
