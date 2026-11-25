"""E63: apply を上げる手で、使い方をまたぐ一貫 joint も上がるか（h_consistency_bound_by_apply）。

仮説（exp.yaml）: {v_rely, from: cross_usage_consistency, to: usage_apply}。
系列:
  E58（#847）: near で joint は 1.5B 0.458、4B 0.708。para・explain・recite はほぼ天井で、joint は apply の正答率で頭打ち。
    これだけでは「joint は apply に頼る」はほぼ定義どおりで、確かめにならない。apply を動かす手で joint が付いてくるかを見る。
  E59・E60・E62: 例を前に置く手は、apply を上げず、概念をまたぐ margin の散らばりを縮めた。
  E5: 語を元の語が見えない名前に改名する（rename_opaque、社員 → 用語08）と、4B で G2c の apply が near より上がった
    （h_opaque_renaming_raises、支持）。1.5B では near と同程度だった。
ここでは、E58 の四つの使い方を、near と rename_opaque の両方で測る。

題材: E58 と同じ（G2c の 24 概念、definition_choice_ja.json の言い換え）。学習はしない。前向き計算だけ。
条件:
  near    E58 の near と同じ（E58 の測り直し。前向き計算は決定的なので、E58 と同じ値が出るはず。違えば開示する）。
  opaque  E5 の rename_opaque と同じ名前（G2c と G2k の概念を辞書順に並べた番号で「用語NN」）に、
          定義文・設問・選択肢・言い換え・理由・recite の文の中の語を、すべて置き換える。
          置き換えは E5 の sub と同じ（「翌」＋新しい名前は元に戻す）。
使い方と margin: E58 と同じ（apply・para・explain・recite。margin > 0 で従ったとする）。

量（モデルと条件ごと）: acc_u、joint、indep。
判定（事前登録。モデルごと）:
  da = acc_apply(opaque) − acc_apply(near)、dj = joint(opaque) − joint(near)。
  前提: da ≥ 0.125（apply が 3 概念以上上がった）。満たさなければ、そのモデルでは判定しない（手が効いていない）。
  h_consistency_bound_by_apply:
    支持: dj ≥ da / 2（apply の上がりの半分以上が joint に付いてくる）。
    反証: dj ≤ 0（apply が上がっても joint は上がらない。ほかの使い方が崩れて打ち消す）。
    その他: 判定しない。
  二つのモデルで支持と反証に分かれたら mixed。片方が判定しないなら、もう片方の判定を採る。

開示（結果を見る前に分かっていること）:
  - E5 で 4B の rename_opaque が apply を上げたこと、1.5B では上がらなかったことを知っている。1.5B は前提を満たさない見込みが高い。
  - E58 の near の値（上の値）を知っている。
  - 改名は、ほかの使い方（para・explain・recite）からも元の語の先入観を外すので、それらも上がりうる。
    そのときの dj の上がりは apply だけの効きではない。判定は「apply を上げる手で joint が付いてくるか」だけを言う。
  - 改名した名前の書き方は 1 通りだけ。1.5B は float32、4B は bfloat16。

使い方:
  python e63_apply_lever_joint.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e63_apply_lever_joint.py --model Qwen/Qwen3-4B --dtype bfloat16
  出力: results/e63_<model>.json（途中保存: results/e63_<model>.partial.json。概念ごと）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e58_cross_usage_consistency import USAGES, measure, summarize

CONDS = ("near", "opaque")


def sub(text, old, new):
    return text.replace(old, new).replace("翌" + new, "翌" + old)


def renamed(it, defs, pair, new):
    c = it["defs"][0]
    it2 = dict(it, q=sub(it["q"], c, new), correct=sub(it["correct"], c, new),
               wrong=sub(it["wrong"], c, new), defs=[new])
    defs2 = {new: sub(defs[c], c, new)}
    pair2 = {k: sub(v, c, new) if isinstance(v, str) else v for k, v in pair.items()}
    return it2, defs2, pair2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2c"]
    concepts = sorted({it["defs"][0] for it in data["items"] if it["group"] in ("G2c", "G2k")})
    choice = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    short = args.model.split("/")[-1]
    out = ROOT / "results" / f"e63_{short}.json"
    part = ROOT / "results" / f"e63_{short}.partial.json"
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "model": args.model, "dtype": args.dtype, "rows": {c: {} for c in CONDS}, "summary": {}, "resumed": 0}
    if part.exists():
        res["resumed"] += 1
    r = Runner(args.model, args.dtype)
    for cond in CONDS:
        rows = res["rows"][cond]
        for it in items:
            L = it["defs"][0]
            if L in rows:
                continue
            if cond == "near":
                rows[L] = measure(r, "near", it, defs, choice[L])
            else:
                new = f"用語{concepts.index(L) + 1:02d}"
                it2, defs2, pair2 = renamed(it, defs, choice[L], new)
                rows[L] = measure(r, "near", it2, defs2, pair2)
            part.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(cond, L, {u: round(v, 3) for u, v in rows[L].items()}, flush=True)
    for cond in CONDS:
        res["summary"][cond] = summarize(res["rows"][cond])
    s = res["summary"]
    da = s["opaque"]["acc"]["apply"] - s["near"]["acc"]["apply"]
    dj = s["opaque"]["joint"] - s["near"]["joint"]
    if da < 0.1249:
        v = "not_judged"
    elif dj >= da / 2 - 1e-9:
        v = "supported"
    elif dj <= 1e-9:
        v = "refuted"
    else:
        v = "not_judged"
    res["paired"] = {"da": da, "dj": dj}
    res["judgment"] = {"consistency_bound_by_apply": v}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()
    for cond in CONDS:
        t = s[cond]
        print(cond, {u: round(a, 3) for u, a in t["acc"].items()}, "joint", round(t["joint"], 3))
    print(res["paired"], res["judgment"])


if __name__ == "__main__":
    main()
