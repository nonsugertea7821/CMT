"""E46: 比べの判定は、設問に名前の出る順に頼るか（h_verdict_by_mention_order #735）。

系列:
  E45（#733）では、番号の選択肢をやめて名前で答えさせても、順を入れ替えた 2 回の一貫は上がらなかった。
  定義を置かない設問でも、設問の中で先に出た名前が強く選ばれた（名前の対数確率の差 +5.2 / -5.8）。
  E45 は名前の事前の好みを「定義なしの設問」の差で引いたが、引きすぎのおそれがあった。
  ここでは、名前の好みを名前の入れ替えで打ち消し、設問に名前を出す形と出さない形を比べる。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。
項目: E43 と同じ（e43_reads_by_word_compare.make_items, seed 1）。条件も E43 と同じ 3 つ（extends・decoy・control）。
  依存する側の定義を D、しない側を O と呼ぶ（E43 の P・Q）。

2 つの形:
  mention:   「次の定義の集まりで、{A} の定義を変えたとします。{X} と {Y} のうち、意味が変わるのはどちらですか。名前だけで答えてください。」
             （E45 の名前の形と同じ）。順 = 設問に D の名前が先に出るか。定義の並びは項目のまま。
  nomention: 「次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。」
             設問に名前を出さない。順 = 定義の集まりで D の定義が O より先に並ぶか。
  どちらも、名前の割り当て 2 通り（項目の名前のまま / D と O の名前を入れ替え）× 順 2 通り = 4 回。
  s(名前) = 応答の頭に名前を置いたときの、名前のトークンの対数確率の和。d = s(D の名前) − s(O の名前)。
  順ごとに、名前の割り当て 2 通りの d を平均する（名前の事前の好みが打ち消される）: e = [順 1 の平均, 順 2 の平均]。
  行の記録: {"pair": e, "consistent": e の 2 つの符号が同じ, "d4": 4 回の d}。
  items には条件ごとの行（{form}_{cond}）と、3 条件をまとめた行（{form}_all。72 行）を置く。

判定（事前登録。72 行の一貫）:
  h_verdict_by_mention_order:
    支持: nomention の一貫 − mention の一貫 ≥ 0.25。
    反証: nomention の一貫 − mention の一貫 ≤ 0.083。
    それ以外: 判定しない。
  参考（判定しない）: 条件ごとの一貫・acc・both_acc。

開示:
  - E42〜E45 の結果を見てから、この手順を書いた。
  - nomention にも、定義の並びという順は残る。この手順は「設問に名前が出る順」と「定義の並びの順」の比べで、
    順に頼ること一般を消せるかは問わない。
  - mention の形は E45 の名前の形と同じ設問だが、名前の好みの消し方が違う（E45: 定義なしの差を引く。E46: 名前を入れ替えて平均）。

使い方:
  python e46_verdict_by_mention_order.py --model Qwen/Qwen3-4B
  出力: results/e46_<model>.json（途中保存: results/e46_<model>.partial.json）
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e43_reads_by_word_compare import CONDS, make_items, snippet

HEAD_MENTION = "次の定義の集まりで、{A} の定義を変えたとします。{X} と {Y} のうち、意味が変わるのはどちらですか。名前だけで答えてください。"
HEAD_NOMENTION = "次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。"
FORMS = ("mention", "nomention")


@torch.no_grad()
def score(r, prompt, name):
    p_ids = r.tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids
    ids = r.tok(prompt + name, return_tensors="pt", add_special_tokens=False).input_ids
    n = p_ids.shape[1]
    assert torch.equal(ids[:, :n], p_ids), "接頭部が一致しない"
    lp = torch.log_softmax(r.model(ids).logits[0].float(), dim=-1)
    return sum(lp[i - 1, ids[0, i]].item() for i in range(n, ids.shape[1]))


def d_one(r, it, cond, form, swap_names, d_first):
    it = dict(it, P=it["Q"], Q=it["P"]) if swap_names else dict(it)
    if form == "mention":
        x, y = (it["P"], it["Q"]) if d_first else (it["Q"], it["P"])
        head = HEAD_MENTION.format(A=it["A"], X=x, Y=y)
    else:
        it["p_first"] = d_first
        head = HEAD_NOMENTION.format(A=it["A"])
    prompt = r.render(None, f"{head}\n{snippet(it, cond)}")
    return score(r, prompt, it["P"]) - score(r, prompt, it["Q"])


def row(d4):
    e = [(d4[0] + d4[1]) / 2, (d4[2] + d4[3]) / 2]
    return {"pair": e, "consistent": (e[0] > 0) == (e[1] > 0), "d4": d4}


def summ(rows):
    vs = list(rows.values())
    n = len(vs)
    return {"cons": sum(v["consistent"] for v in vs) / n,
            "acc": sum(sum(v["pair"]) > 0 for v in vs) / n,
            "both_acc": sum(all(x > 0 for x in v["pair"]) for v in vs) / n,
            "mean_margin": sum(sum(v["pair"]) / 2 for v in vs) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e46_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "raw": {}, "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for form in FORMS:
        for cond in CONDS:
            key = f"{form}_{cond}"
            if key in out["raw"]:
                continue
            out["raw"][key] = {str(it["id"]): [d_one(r, it, cond, form, s, f)
                                               for f in (True, False) for s in (False, True)] for it in items}
            print(key, "done", flush=True)
            part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for form in FORMS:
        allrows = {}
        for cond in CONDS:
            rows = {k: row(v) for k, v in out["raw"][f"{form}_{cond}"].items()}
            out["items"][f"{form}_{cond}"] = rows
            allrows.update({f"{cond}:{k}": v for k, v in rows.items()})
        out["items"][f"{form}_all"] = allrows
    for k, rows in out["items"].items():
        out["summary"][k] = summ(rows)
    cm, cn = out["summary"]["mention_all"]["cons"], out["summary"]["nomention_all"]["cons"]
    v = "not_judged"
    if cn - cm >= 0.25:
        v = "supported"
    elif cn - cm <= 0.0834:
        v = "refuted"
    out["judgment"] = {"cons_mention": cm, "cons_nomention": cn, "verdict_by_mention_order": v}
    print(json.dumps(out["summary"], indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e46_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
