"""E45: 比べの判定は選択肢に頼るか（h_verdict_by_option #731）。

系列:
  E42〜E44（#725・#721・#729。Qwen3-4B、比べの形「意味が変わるのはどちらですか。番号で答えてください。」）では、
  両方の順で正しい項目の割合（both_acc）が extends を除いて 0 か 0.04 だった。
  E43 の行は margin と both しか残しておらず、「両方の順で同じ方を選んだか」（一貫）は読み返せない。
  答えが番号の位置に引かれているなら、番号の選択肢をやめ、名前で答えさせれば一貫が上がるはず。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。
項目: E43 と同じ（e43_reads_by_word_compare.make_items, seed 1）。条件も E43 と同じ 3 つ（extends・decoy・control）。

2 つの答えの形（どちらも、P と Q の出る順を入れ替えた 2 回）:
  number: E43 と同じ設問。d = logit(P の番号) − logit(Q の番号)。
  name:   「次の定義の集まりで、{A} の定義を変えたとします。{X} と {Y} のうち、意味が変わるのはどちらですか。名前だけで答えてください。」
          のあとに定義の集まり。番号の選択肢は置かない。
          s(名前) = 応答の頭に名前を置いたときの、名前のトークンの対数確率の和。d = s(P) − s(Q)。
          名前の長さや字面の事前の好みを除くため、定義の集まりを置かない同じ設問（null）の d を、同じ順ごとに引く。
          d_adj = d − d_null。
  行の記録: {"pair": {"margin": 2 回の平均, "both": 2 回とも > 0}, "consistent": 2 回の符号が同じ, "d": [2 回の値]}。
  一貫 cons = consistent の割合（3 条件 × 24 項目 = 72 行）。

判定（事前登録）:
  cons_num = number の一貫（素の d）。cons_name = name の一貫（d_adj）。
  h_verdict_by_option（判定は番号の選択肢に頼る）:
    支持: cons_num ≤ 0.5、かつ cons_name − cons_num ≥ 0.25。
    反証: cons_num ≥ 0.75（番号でも順に引かれていない）、または cons_name − cons_num ≤ 0.083（名前にしても一貫が上がらない）。
    それ以外: 判定しない。
  参考（判定しない）: 条件ごとの acc・both_acc（両方の形）、name の素の d の一貫、number の null を引いた一貫、
    name の形での decoy の acc（h_model_reads_by_word を順に頑健な形で見直す参考）。

開示:
  - E42〜E44 の結果を見てから、この手順を書いた。
  - number の形は E43 と同じ計算をもう一度行う（E43 の結果ファイルは触らない。一貫を残すため）。
  - name の形でも、設問の中で名前の出る順は残る。反証の 2 つ目は、偏りが番号でなく出る順から来るときにも当たる。
    そのときの仮説の読み（選択肢＝番号の並び）は、この手順の定めで、出る順は選択肢に含めない。
  - null を引くのは name だけにする。number の偏り（番号の位置）こそ、確かめたいものだから。

使い方:
  python e45_verdict_by_option.py --model Qwen/Qwen3-4B
  出力: results/e45_<model>.json（途中保存: results/e45_<model>.partial.json）
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e43_reads_by_word_compare import CONDS, HEAD, make_items, snippet

HEAD_NAME = "次の定義の集まりで、{A} の定義を変えたとします。{X} と {Y} のうち、意味が変わるのはどちらですか。名前だけで答えてください。"


@torch.no_grad()
def d_number(r, it, cond, p_first):
    o = [it["P"], it["Q"]] if p_first else [it["Q"], it["P"]]
    body = f"{HEAD.format(A=it['A'])}\n{snippet(it, cond)}\n1. {o[0]}\n2. {o[1]}"
    l1, l2 = r.logits_12(r.render(None, body))
    return (l1 - l2) if p_first else (l2 - l1)


@torch.no_grad()
def score(r, prompt, name):
    p_ids = r.tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids
    ids = r.tok(prompt + name, return_tensors="pt", add_special_tokens=False).input_ids
    n = p_ids.shape[1]
    assert torch.equal(ids[:, :n], p_ids), "接頭部が一致しない"
    lp = torch.log_softmax(r.model(ids).logits[0].float(), dim=-1)
    return sum(lp[i - 1, ids[0, i]].item() for i in range(n, ids.shape[1]))


def d_name(r, it, cond, p_first):
    x, y = (it["P"], it["Q"]) if p_first else (it["Q"], it["P"])
    head = HEAD_NAME.format(A=it["A"], X=x, Y=y)
    body = head if cond is None else f"{head}\n{snippet(it, cond)}"
    prompt = r.render(None, body)
    return score(r, prompt, it["P"]) - score(r, prompt, it["Q"])


def row(ds):
    return {"pair": {"margin": sum(ds) / 2, "both": all(d > 0 for d in ds)},
            "consistent": (ds[0] > 0) == (ds[1] > 0), "d": ds}


def summ(rows):
    vs = list(rows.values())
    return {"acc": sum(v["pair"]["margin"] > 0 for v in vs) / len(vs),
            "both_acc": sum(v["pair"]["both"] for v in vs) / len(vs),
            "cons": sum(v["consistent"] for v in vs) / len(vs),
            "mean_margin": sum(v["pair"]["margin"] for v in vs) / len(vs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e45_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "raw": {}, "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)

    def save():
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    if "null_name" not in out["raw"]:
        out["raw"]["null_name"] = {str(it["id"]): [d_name(r, it, None, f) for f in (True, False)] for it in items}
        out["raw"]["null_number"] = {}
        for it in items:
            body = lambda f: f"{HEAD.format(A=it['A'])}\n1. {it['P'] if f else it['Q']}\n2. {it['Q'] if f else it['P']}"
            ds = []
            for f in (True, False):
                l1, l2 = r.logits_12(r.render(None, body(f)))
                ds.append((l1 - l2) if f else (l2 - l1))
            out["raw"]["null_number"][str(it["id"])] = ds
        print("null done", flush=True)
        save()
    for form, fn in (("number", d_number), ("name", d_name)):
        for cond in CONDS:
            key = f"{form}_{cond}"
            if key in out["raw"]:
                continue
            out["raw"][key] = {str(it["id"]): [fn(r, it, cond, f) for f in (True, False)] for it in items}
            print(key, "done", flush=True)
            save()
    for form in ("number", "name"):
        null = out["raw"][f"null_{form}"]
        for cond in CONDS:
            raw = out["raw"][f"{form}_{cond}"]
            out["items"][f"{form}_{cond}"] = {k: row(v) for k, v in raw.items()}
            out["items"][f"{form}_adj_{cond}"] = {k: row([a - b for a, b in zip(v, null[k])]) for k, v in raw.items()}
    for k, rows in out["items"].items():
        out["summary"][k] = summ(rows)

    def cons(prefix):
        rows = [v for c in CONDS for v in out["items"][f"{prefix}_{c}"].values()]
        return sum(v["consistent"] for v in rows) / len(rows)

    cn, cm = cons("number"), cons("name_adj")
    v = "not_judged"
    if cn <= 0.5 and cm - cn >= 0.25:
        v = "supported"
    elif cn >= 0.75 or cm - cn <= 0.0834:
        v = "refuted"
    out["judgment"] = {"cons_num": cn, "cons_name": cm, "cons_name_raw": cons("name"),
                       "cons_num_adj": cons("number_adj"), "verdict_by_option": v}
    print(json.dumps(out["summary"], indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e45_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
