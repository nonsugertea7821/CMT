"""E27: 数の大小の照合の誤りが、規則型の再定義への追従を下げているか（#8）。

E9 で、1.5B は途中経過を書かせても規則型の再定義に従えなかった。途中の文には「22歳は25歳以上」
「160センチは150センチ未満」のような大小の取り違えがあった。追従の失敗が、数の大小の照合の失敗から
来るのかを、照合だけを取り出して測る。

設問: data/concepts_ja.json の規則型のうち、数のしきい値で境界が決まる 9 概念（新規・午前・大口注文・
遅延・未成年・無料・夜間・大人・都市部）の G2c（衝突）と G2k（衝突しない）、計 18 問 × 2 順序。
暦の規則（営業日・週・平日）は数の大小の照合ではないので除く。

条件（どれも番号を即答させる。ベクトルは使わない）:
  real   E9 の direct と同じ: 定義文 + 設問
  nonce  real の定義文と設問で、概念の語を、元の意味を持たない語（data の nonce）に置き換える
  bare   定義も概念の語もなく、同じ数の大小だけを問う（data/number_comparison_ja.json、手で作ったもの。
         正答は元の設問の正答と同じ向きにそろえてある）

指標: accuracy（2順序の平均 margin > 0）、order_robust_accuracy。

判定（18 問を合わせて）:
  lowers         bare の accuracy ≤ 0.75、かつ real で誤った問のうち半分以上で bare も誤る
  not_lowers     bare の accuracy ≥ 0.85、かつ real の accuracy ≤ bare − 0.20
                 （照合だけなら解けるのに、追従は落ちている）
  inconclusive   それ以外
  nonce は記録するが、判定には使わない（落ちるのが元の意味のせいか、規則を当てはめることのせいかを見る）。

使い方:
  python e27_number_comparison.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner, question_text

NUMERIC = set("新規 午前 大口注文 遅延 未成年 無料 夜間 大人 都市部".split())


@torch.no_grad()
def margin(r, text_of, item):
    ms = []
    for swap in (False, True):
        body, correct_no = question_text(item, swap)
        ids = r.tok(r.render(None, text_of(body)), return_tensors="pt", add_special_tokens=False).input_ids
        last = r.model(ids).logits[0, -1]
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    nc = json.loads((ROOT / "data" / "number_comparison_ja.json").read_text(encoding="utf-8"))
    nonce = nc["nonce"]
    r = Runner(args.model)
    items = [it for it in data["items"] if it["group"] in ("G2c", "G2k") and it["defs"][0] in NUMERIC]
    assert len(items) == 18 and all(it["id"] in nc["bare"] for it in items)

    conds = ["real", "nonce", "bare"]
    rows = []
    for it in items:
        c = it["defs"][0]
        d = data["defs"][c]
        n_it = dict(it, q=it["q"].replace(c, nonce))
        bare = dict(nc["bare"][it["id"]], type="yesno")
        row = {"id": it["id"], "group": it["group"], "concept": c,
               "real": margin(r, lambda b: f"次の定義に従うこと。\n{d}\n\n{b}", it),
               "nonce": margin(r, lambda b: f"次の定義に従うこと。\n{d.replace(c, nonce)}\n\n{b}", n_it),
               "bare": margin(r, lambda b: b, bare)}
        rows.append(row)
        print(it["id"], c, {k: round(row[k]["margin"], 2) for k in conds}, flush=True)

    def summ(rs):
        return {k: {"n": len(rs), "acc": sum(x[k]["margin"] > 0 for x in rs) / len(rs),
                    "acc_both": sum(x[k]["both"] for x in rs) / len(rs),
                    "mean_margin": sum(x[k]["margin"] for x in rs) / len(rs)} for k in conds}

    summary = {"all": summ(rows)}
    for g in ("G2c", "G2k"):
        summary[g] = summ([x for x in rows if x["group"] == g])
    s = summary["all"]
    real_wrong = [x for x in rows if x["real"]["margin"] <= 0]
    both_wrong = [x for x in real_wrong if x["bare"]["margin"] <= 0]
    if s["bare"]["acc"] <= 0.75 and real_wrong and len(both_wrong) >= 0.5 * len(real_wrong):
        verdict = "lowers"
    elif s["bare"]["acc"] >= 0.85 and s["real"]["acc"] <= s["bare"]["acc"] - 0.20:
        verdict = "not_lowers"
    else:
        verdict = "inconclusive"
    out = ROOT / "results" / f"e27_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps({"args": vars(args), "nonce": nonce, "items": rows, "summary": summary,
                               "n_real_wrong": len(real_wrong), "n_real_and_bare_wrong": len(both_wrong),
                               "verdict": verdict}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in summary.items():
        print(k, {c: (round(x["acc"], 3), round(x["acc_both"], 3)) for c, x in v.items()})
    print("real_wrong:", len(real_wrong), "of which bare wrong:", len(both_wrong), "verdict:", verdict)


if __name__ == "__main__":
    main()
