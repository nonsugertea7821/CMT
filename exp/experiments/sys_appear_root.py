"""h_appear_root を確かめる: 出現（pre で無く post で有る）の分類は、pre だけから読めるか。

仮説（claims.yaml）: v_depend(signature_class, syntax.pre)。
  出現の形（pre に {is: exists, from: p, neg: true}、post に {is: exists, from: p}）は、v_design（ontology）、
  v_compute（std）、v_speak（exp）ほかに別々に書かれている。これを一つの根（出現）にまとめられるなら、
  その分類はシグネチャの式から定まり、しかも pre を見れば決まるはず、と読む。

手順（体系のファイルは変えない。tc.build() の T.N を読むだけ）:
  対象: T.is_verb が真のノード。枠（pre・post）は、自分が持てば自分の、持たなければ extends をたどって最初に持つ祖先のもの
    （tc の base_of と同じたどり方）。holds だけのものと、枠のないものは対象の外。
  位置 p ごとに:
    pre_neg(v)   = {p : pre に exists(p) の否定がある}
    post_pos(v)  = {p : post に exists(p) があり、pre に exists(p)（否定なし）がない}
    appear(v)    = pre_neg ∩ post_pos
  分類:
    A_pre   = {v : pre_neg(v) が空でない}         pre だけで読む出現
    A_pair  = {v : appear(v) が空でない}           pre と post の対で読む出現
    A_post  = {v : post_pos(v) が空でない}         post だけで読む「現れる」
  記述（判定に使わない）:
    residual(v)  枠の原子から、appear の位置の exists の 2 つを除いた残り。A_pair のうち残りが空のものを数える
                 （n_bare: 出現の形のほかに式の差がなく、区別が表示にだけある動詞）。
    pos          A_pair の各動詞の appear の位置（to・new など）。
    vanish       pre に exists(p)、post に exists(p) の否定がある動詞（消える）の数。
    sometime     sometime を持つノードの数。
    variant      写しの ontology.yaml に v_appear（extends occurrent、from continuant、to any、出現の形を to に）を
                 足したときの tc の誤りの数と、「動詞の式が同じ」を含む誤り。
  行（sys_appear_root.json）: "verb <名>": {frame_own, A_pre, A_pair, A_post, n_residual, pos}、
    "variant v_appear": {errors, same_formula, err_text}、"summary 要約": {...}
判定（事前に決める）:
  A_pre == A_pair（pre の否定の exists があれば、必ず同じ位置の exists が post にあり、その逆も）、かつ
  A_post ⊆ A_pre（post で現れるものは、pre で無いと書かれている）、かつ
  v_design・v_compute・v_speak が A_pair に入る、なら支持。どれかが崩れれば反証。

開示（結果を見る前に分かっていること）:
  - grep で見た限り、出現の形は v_design・v_compute・v_speak（to の位置）と、new の位置のもの（std・exp・runtime）にある。
    消える形（std の 1 つ）もある。この 3 つが A_pair に入ることは見込まれる。
  - post に exists を足すが pre に否定を書かない動詞があるかは、数えていない。
  - v_compute の式は出現の形そのもの。v_appear を足す変種は「動詞の式が同じ」で落ちる見込みが高い。
  - 型検査を 2 回走らせる（本体と変種）。
使い方:
  python exp/experiments/sys_appear_root.py
"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_appear_root.json"
ONT = "cscl/library/ontology/ontology.yaml"
ANCHOR = "  v_design: {display: 設計する,"
ADD = ("  v_appear: {display: 現れる, extends: occurrent, from: continuant, to: any, "
       "pre: [{is: exists, from: to, neg: true}], post: [{is: exists, from: to}]}\n")
WANT = ("v_design", "v_compute", "v_speak")

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    tc.build()
errs = [str(e) for e in tc.errors]
print(json.dumps({"errors": len(errs), "same": [e for e in errs if "動詞の式が同じ" in e], "err_text": errs[:10]}, ensure_ascii=False))
'''


def frame(T, v):
    hops = 0
    while v in T.N and hops < 50:
        n = T.N[v]
        if "pre" in n or "post" in n:
            return v, n.get("pre", []), n.get("post", [])
        if "holds" in n:
            return None
        v, hops = T.up(v), hops + 1
    return None


def ex(f, neg):
    return isinstance(f, dict) and f.get("is") == "exists" and bool(f.get("neg")) == neg and "to" not in f


def variant():
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        f = Path(d) / ONT
        s = f.read_text(encoding="utf-8")
        assert s.count(ANCHOR) == 1
        s = s.replace(ANCHOR, ADD + ANCHOR)
        f.write_text(s, encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    base_errors = len(tc.errors)
    S = tc.short
    rows, A_pre, A_pair, A_post = {}, set(), set(), set()
    n_bare = n_vanish = 0
    for v in sorted(T.N):
        if not T.is_verb(v):
            continue
        fr = frame(T, v)
        if fr is None:
            continue
        own, pre, post = fr
        pre_neg = {f["from"] for f in pre if ex(f, True)}
        pre_pos = {f["from"] for f in pre if ex(f, False)}
        post_pos = {f["from"] for f in post if ex(f, False)} - pre_pos
        post_neg = {f["from"] for f in post if ex(f, True)}
        ap = pre_neg & post_pos
        res = [f for f in pre if not (ex(f, True) and f["from"] in ap)] + \
              [f for f in post if not (ex(f, False) and f["from"] in ap)]
        k = S(v)
        if pre_neg:
            A_pre.add(k)
        if ap:
            A_pair.add(k)
            n_bare += not res
        if post_pos:
            A_post.add(k)
        n_vanish += bool(pre_pos & post_neg)
        rows[f"verb {k}"] = {"frame_own": int(own == v), "A_pre": int(bool(pre_neg)), "A_pair": int(bool(ap)),
                             "A_post": int(bool(post_pos)), "n_residual": len(res), "pos": ",".join(sorted(ap))}
    var = variant()
    rows["variant v_appear"] = {"errors": var["errors"] - base_errors, "same_formula": len(var["same"]),
                                "err_text": var["err_text"]}
    c1, c2, c3 = A_pre == A_pair, A_post <= A_pre, all(w in A_pair for w in WANT)
    rows["summary 要約"] = {"n_framed": len(rows) - 1, "n_A_pre": len(A_pre), "n_A_pair": len(A_pair),
                          "n_A_post": len(A_post), "pre_eq_pair": int(c1), "post_in_pre": int(c2), "want_in": int(c3),
                          "n_bare": n_bare, "n_vanish": n_vanish, "base_errors": base_errors,
                          "variant_errors": var["errors"], "variant_same_formula": len(var["same"]),
                          "pre_only": sorted(A_pre - A_pair), "post_only": sorted(A_post - A_pre),
                          "n_sometime": sum(1 for n in T.N.values() if "sometime" in n),
                          "verdict_support": int(c1 and c2 and c3)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if c1 and c2 and c3 else "反証")


if __name__ == "__main__":
    main()
