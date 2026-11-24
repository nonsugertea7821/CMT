"""E47: 設問に名前を出さない形で、モデルは extends を読むか・字面で読むか（h_model_misses_extends #723、h_model_reads_by_word）。

系列:
  E41（T ごとの二択）・E42（比べ、番号）では extends の acc が 0.417・0.708 で、h_model_misses_extends は判定しなかった。
  E43（比べ、番号）では decoy 0.125 で h_model_reads_by_word が支持された。
  E46（#736）は、設問に名前を出さない形（nomention）で、extends 0.958（両順 0.792）、decoy 0.875、control 1.0 だった。
  ただし E46 の判定の対象は順への依存で、これらの値は事前登録の外。E43 と同じ項目（seed 1）でもある。
  ここでは、新しい項目（seed 2）で、nomention の形の値に、事前に線を引く。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。
項目: E43 と同じ生成関数（e43_reads_by_word_compare.make_items）で seed 2。24 項目。条件は extends・decoy・control。
  依存する側の定義を D（E43 の P）、しない側を O（E43 の Q）と呼ぶ。

設問（E46 の nomention と同じ）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。」のあとに定義の集まり。
  名前の割り当て 2 通り（そのまま / D と O の名前を入れ替え）× 定義の並び 2 通り（D が先 / O が先）= 4 回。
  s(名前) = 応答の頭に名前を置いたときの、名前のトークンの対数確率の和。d = s(D の名前) − s(O の名前)。
  並びごとに、名前の割り当て 2 通りの d を平均する: pair = [D が先の平均, O が先の平均]。
  acc = pair の平均 > 0 の割合。order_robust = pair の 2 つがどちらも > 0 の割合。

判定（事前登録。24 項目）:
  h_model_misses_extends（モデルは extends を読まない）:
    反証: extends の acc ≥ 0.75、かつ order_robust ≥ 0.5。
    支持: extends の acc ≤ 0.583。
    それ以外: 判定しない。
  h_model_reads_by_word（モデルは依存を語の字面で読む。E43 で支持）:
    前提: extends の acc ≥ 0.625（E43 と同じ線）。崩れたら判定しない。
    反する根拠: decoy の acc ≥ 0.5（E43 の反証の線と同じ）。
    沿う根拠: decoy の acc ≤ 0.25、かつ control の acc − decoy の acc ≥ 0.25（E43 の支持の線と同じ）。
    それ以外: 判定しない。
    反する根拠が出ると、E43 の支持と合わせて mixed になる。

開示:
  - E46 の結果（seed 1 で nomention の extends 0.958、decoy 0.875）を見てから、この手順を書いた。h_model_reads_by_word の線は E43 の線のまま。h_model_misses_extends の線（0.75 と順の両方 0.5 / 0.583）はここで決めた。E46 の値を見た後なので、線の置き方が値に引かれた可能性は消せない。
  - 形の違い（番号で比べる / 名前を出さずに答える）で結果が変わるなら、2 つの仮説は「その形では」という限りつきになる。
  - 関数は E46（#736、まだ main にない）からこのスクリプトへ写した。

使い方:
  python e47_extends_unnamed.py --model Qwen/Qwen3-4B
  出力: results/e47_<model>.json（途中保存: results/e47_<model>.partial.json）
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner
from e43_reads_by_word_compare import CONDS, make_items, snippet

HEAD = "次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。"


@torch.no_grad()
def score(r, prompt, name):
    p_ids = r.tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids
    ids = r.tok(prompt + name, return_tensors="pt", add_special_tokens=False).input_ids
    n = p_ids.shape[1]
    assert torch.equal(ids[:, :n], p_ids), "接頭部が一致しない"
    lp = torch.log_softmax(r.model(ids).logits[0].float(), dim=-1)
    return sum(lp[i - 1, ids[0, i]].item() for i in range(n, ids.shape[1]))


def d_one(r, it, cond, swap_names, d_first):
    it = dict(it, P=it["Q"], Q=it["P"]) if swap_names else dict(it)
    it["p_first"] = d_first
    prompt = r.render(None, f"{HEAD.format(A=it['A'])}\n{snippet(it, cond)}")
    return score(r, prompt, it["P"]) - score(r, prompt, it["Q"])


def summ(rows):
    vs = [v["pair"] for v in rows.values()]
    n = len(vs)
    return {"acc": sum(sum(e) > 0 for e in vs) / n,
            "order_robust": sum(all(x > 0 for x in e) for e in vs) / n,
            "mean_margin": sum(sum(e) / 2 for e in vs) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e47_{short}.partial.json"
    items = make_items(seed=2)
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "raw": {}, "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for cond in CONDS:
        if cond in out["raw"]:
            continue
        out["raw"][cond] = {str(it["id"]): [d_one(r, it, cond, s, f) for f in (True, False) for s in (False, True)]
                            for it in items}
        print(cond, "done", flush=True)
        part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for cond in CONDS:
        out["items"][cond] = {k: {"pair": [(d[0] + d[1]) / 2, (d[2] + d[3]) / 2], "d4": d}
                              for k, d in out["raw"][cond].items()}
        out["summary"][cond] = summ(out["items"][cond])
    s = out["summary"]
    ext = s["extends"]
    me = "not_judged"
    if ext["acc"] >= 0.75 and ext["order_robust"] >= 0.5:
        me = "refuted"
    elif ext["acc"] <= 0.5834:
        me = "supported"
    pre = ext["acc"] >= 0.625
    dec, con = s["decoy"]["acc"], s["control"]["acc"]
    rw = "not_judged"
    if pre and dec >= 0.5:
        rw = "against"
    elif pre and dec <= 0.25 and con - dec >= 0.25:
        rw = "for"
    out["judgment"] = {"model_misses_extends": me, "reads_by_word_pre": pre, "model_reads_by_word": rw}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e47_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
