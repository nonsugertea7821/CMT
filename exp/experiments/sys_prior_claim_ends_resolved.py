"""h_prior_claim_ends_resolved を確かめる: 先行研究の主張の読みの式も、宣言の範囲に依るように検査を掛けられるか。

仮説（claims.yaml）: 依る(先行研究の主張の読みの式, 宣言の範囲)。登録（ac77d8f）の読み: #223（sys_reading_ends_resolved）で、
  宣言されていない名前を端に置いても通った読みの式が 20 あり、うち 13 が先行研究の主張（prior_claim）だった。
  いまは exp の検査が端を確かめるのは仮説と決定の中身だけ（exp_check.py の triple）。主張にも同じ確かめを掛けられ、
  掛けても今の体系は通り、端を壊した主張は弾かれる、と読む。

手順（体系のファイルも検査器も変えない。検査を写した関数で測る）:
  1. tc.build() で体系を読み、各領域の個体のうち、種類が prior_claim の下位で、読みの式（p・s・o）を持つものを集める。
  2. 確かめ check(x): exp_check.py の triple と同じ規則（端が未定義でないこと、p が is_a でないこと、p が動詞であること、
     端が動詞の from・to の種類と重なること）。triple の本文を写したもの。
  3. 対照: 同じ check を、仮説（種類が hypothesis の下位で p を持つ個体）に掛ける。triple と同じものを写せていれば、
     ec が通る今の体系では誤り 0 になる。
  4. 変異: 主張ごとに1つ、s が文字列ならそれを、並びならその最初を、どちらでもなければ o を、zz_undefined_end に置き換えて check する。
  行（sys_prior_claim_ends_resolved.json）:
    "claim <id>": {errors（HEAD での誤りの数）, mutant_rejected（0 か 1）}
    "summary 要約": {n_claims, n_head_errors, n_mutants_rejected, n_hyps, n_hyp_errors}
判定: n_hyp_errors が 0 でなければ外れ（写しが triple と違う）。0 のもとで、n_head_errors が 0 かつ
  n_mutants_rejected = n_claims なら支持。n_head_errors が 1 以上なら反証（今の主張の式は、宣言の範囲と動詞の端に合わない）。

開示（結果を見る前に分かっていること）:
  - 変異が弾かれるのは、端の未定義の確かめで決まり、ほぼ確実（予想が立つ部分）。予想が立たないのは、今の主張 22 の式が、
    動詞の端の種類と重なるか（仮説・決定の中身と違い、これまで一度も確かめられていない）。
  - 主張の数は 22（#223 の時点では 13）。式は exp.yaml の facts の v_refer（始点 pwc_）。
  - この実験は検査器に確かめを足さない。支持なら、exp_check.py に主張の確かめを足すかは別の判断として残す。

使い方:
  python exp/experiments/sys_prior_claim_ends_resolved.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results/sys_prior_claim_ends_resolved.json"
BAD = "zz_undefined_end"


def check(T, x):
    out = []
    ss = x["s"] if isinstance(x["s"], list) else [x["s"]]
    oo = x["o"] if isinstance(x["o"], list) else [x["o"]]
    for t in ss + oo:
        if t not in T.N and t not in T.I:
            return [f"ノード {t} が未定義"]
    if x["p"] == "is_a":
        return ["is_a を使えるのは決定だけ"]
    if not T.is_verb(x["p"]):
        return [f"{x['p']} は動詞でない"]
    for side, ts in (("from", ss), ("to", oo)):
        bound = T.end(x["p"], side)
        for t in ts:
            if not T.overlaps(t, bound):
                out.append(f"{t} は動詞 {x['p']} の {side}（{bound}）に来られない")
    return out


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, Dm = tc.build()
    claims, hyps = {}, {}
    for name, (_, D) in Dm.items():
        for iid, x in (D.get("individuals") or {}).items():
            if not isinstance(x, dict) or "p" not in x:
                continue
            k = x.get("is")
            if T.is_a(k, "prior_claim") or T.is_a(k, "exp.prior_claim"):
                claims[iid] = x
            elif T.is_a(k, "hypothesis") or T.is_a(k, "exp.hypothesis"):
                hyps[iid] = x
    rows, texts = {}, {}
    for cid, x in sorted(claims.items()):
        e = check(T, x)
        m = dict(x)
        if isinstance(m["s"], str):
            m["s"] = BAD
        elif isinstance(m["s"], list) and m["s"]:
            m["s"] = [BAD] + m["s"][1:]
        else:
            m["o"] = BAD
        rows[f"claim {cid}"] = {"errors": len(e), "mutant_rejected": int(bool(check(T, m)))}
        if e:
            texts[cid] = e
    hyp_err = {h: check(T, x) for h, x in hyps.items()}
    R = [v for k, v in rows.items() if k.startswith("claim ")]
    rows["summary 要約"] = {"n_claims": len(R), "n_head_errors": sum(1 for r in R if r["errors"]),
                          "n_mutants_rejected": sum(r["mutant_rejected"] for r in R),
                          "n_hyps": len(hyps), "n_hyp_errors": sum(1 for e in hyp_err.values() if e)}
    s = rows["summary 要約"]
    verdict = ("外れ" if s["n_hyp_errors"] else "支持" if not s["n_head_errors"] and s["n_mutants_rejected"] == s["n_claims"]
               else "反証" if s["n_head_errors"] else "外れ")
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows, "head_errors": texts,
                               "hyp_errors": {h: e for h, e in hyp_err.items() if e}}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    for c, e in texts.items():
        print(c, e)
    for h, e in list(hyp_err.items()):
        if e:
            print("hyp", h, e)
    print("判定:", verdict)


if __name__ == "__main__":
    main()
