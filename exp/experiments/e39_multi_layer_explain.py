"""E39: 複数の層に分けた概念ベクトルは、説明に転移するか（h_multi_layer_transfers_to_explain #270）。

系列: E20 は、単層（層 8）のベクトルが、学習した使い方（適用）から説明に転移しないことを観察した
（h_apply_does_not_transfer_to_explain は支持）。その含意として、別々の解き方の対を登録した（0e7ee9f）:
  - h_explain_transfers_to_apply（説明を教えれば適用に届く）: E36 で反証。
  - h_multi_layer_transfers_to_explain（届かないのは単層だから。複数層なら説明に届く）: この実験。

ベクトル（モデルは学習しない。記録済みのベクトルを読むだけ）:
  none   何も加えない
  ml     results/e8_L2-13_d0.001.pt（E8 の記録。層 2〜13 の 12 層に1本ずつ。教師は定義文の暗唱と適用例 = defqa）
  sl     results/e3_<model>_L8_defqa.pt（E3 の記録。層 8 の1本。同じ教師 defqa。比べる参考）
  E8 の .pt はリポジトリに入れていない（.pt は記録しない）。手元の sha256 は
  20456ffd24bbcf677f83993036eaa9dbc3427d9884700f73b5a7968287804a8a（E8 の json と同じ時刻に書かれたもの）。
  実行時に sha256 を出力に書き、違えば止める。

加え方: E8 と同じ。語（概念の名前）のトークン位置で、各層の出力にその層のベクトルを加える。
  sl も同じ仕組みで、層 8 だけに加える。

評価: concepts_ja.json の G2c（24 問。E20・E36 と同じ）。
  apply           E8 と同じ二択（question_text）。操作の確かめ
  explain         E20 と同じ、答えを示して理由を選ばせる設問（判定に使う）
  explain_noans   E20 と同じ、答えを示さない理由の設問（参考）
  acc は margin > 0 の割合（選択肢の順を入れ替えた2回の margin の平均で数える）。

判定（事前登録。24 問）:
  前提（操作の確かめ）: apply の acc が ml で none より 0.25 以上高い。
  前提（天井）: explain の acc が none で 0.75 未満。
  前提のどちらかが崩れたら、判定しない（仮説は未検証のまま、観察だけ書く）。
  転移する（支持）: explain の acc が ml で 0.75 以上、かつ none より 0.25 以上高い。
  転移しない（反証）: それ以外。
  sl と explain_noans は判定に使わない。

開示（結果を見る前に分かっていること）:
  - E8 の記録の G2c の apply を、事前登録の前に読んだ: none 0.375、vec（= ml）0.833。前提（操作の確かめ）は
    この記録どおりなら成り立つ見込み。ここでは同じ数をこのスクリプトの評価の道でもう一度測る。
  - E20 の none の explain は 0.417、defqa（= sl と同じベクトル）の explain は E20 の記録にある（ここでは読み直していない）。
  - E8 は、定義の言い換え（教えていない使い方）で、複数層が単層と変わらないことを観察した
    （o_e8_paraphrase_like_single_layer。h_multi_layer_raises_consistency は mixed）。説明の設問は、まだ測っていない。
  - E36 の含意として h_apply_depends_explain を登録した。この実験はそれを確かめない（教師は説明でない）。

使い方:
  python e39_multi_layer_explain.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e39_<model>_L2-13.json
"""
import argparse
import hashlib
import json

import torch

from e1_context_injection import ROOT, Runner, question_text
from e3_concept_vectors import label_mask
from e8_multilayer import MultiInjector
from e20_explain_transfer import EXPLAIN, EXPLAIN_NOANS, summarize

ML_SHA = "20456ffd24bbcf677f83993036eaa9dbc3427d9884700f73b5a7968287804a8a"


@torch.no_grad()
def margin(r, inj, layers, body_of, label, v):
    ms = []
    for swap in (False, True):
        body, correct_no = body_of(swap)
        text = r.render(None, body)
        ids, mask = label_mask(r.tok, text, label)
        inj.set(torch.tensor(mask, dtype=torch.float32).view(1, -1, 1), v)
        last = r.model(torch.tensor([ids])).logits[0, -1]
        inj.set(None, None)
        l1, l2 = last[r.id1].item(), last[r.id2].item()
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def reason_body(head, item, label, pair):
    def body_of(swap):
        opts = [f"「{label}」は{pair['project']}を指すから", f"「{label}」は{pair['ordinary']}を指すから"]
        if swap:
            opts.reverse()
        return f"{head}\n{item['q']}\n1. {opts[0]}\n2. {opts[1]}", (2 if swap else 1)

    return body_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res_dir = ROOT / "results"
    ml_path = res_dir / "e8_L2-13_d0.001.pt"
    sha = hashlib.sha256(ml_path.read_bytes()).hexdigest()
    if sha != ML_SHA:
        raise SystemExit(f"E8 のベクトルの sha256 が違う: {sha}")
    layers = list(range(2, 14))
    ml = torch.load(ml_path)
    sl1 = torch.load(res_dir / f"e3_{short}_L8_defqa.pt")
    d_model = next(iter(ml.values())).shape[1]

    def as_ml(v):
        out = torch.zeros(len(layers), d_model)
        out[layers.index(8)] = v
        return out

    sl = {c: as_ml(v) for c, v in sl1.items()}

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    pairs = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    items = [x for x in data["items"] if x["group"] == "G2c"]

    r = Runner(args.model)
    inj = MultiInjector(r.model, layers)
    conds = {"none": None, "ml": ml, "sl": sl}
    out = {"args": vars(args), "layers": layers, "ml_sha256": sha, "items": {}, "summary": {}}
    for cname, vectors in conds.items():
        rows = {}
        for it in items:
            label = it["defs"][0]
            v = None if vectors is None else vectors[label]
            rows[it["id"]] = {
                "apply": margin(r, inj, layers, lambda s, it=it: question_text(it, s), label, v),
                "explain": margin(r, inj, layers, reason_body(EXPLAIN.format(A=it["correct"]), it, label, pairs[label]), label, v),
                "explain_noans": margin(r, inj, layers, reason_body(EXPLAIN_NOANS, it, label, pairs[label]), label, v),
            }
        out["items"][cname] = rows
        out["summary"][cname] = {k: summarize(rows, k) for k in ("apply", "explain", "explain_noans")}
        print(cname, json.dumps(out["summary"][cname], ensure_ascii=False), flush=True)
    s = out["summary"]
    pre_apply = s["ml"]["apply"]["acc"] - s["none"]["apply"]["acc"] >= 0.25
    pre_ceiling = s["none"]["explain"]["acc"] < 0.75
    transfer = s["ml"]["explain"]["acc"] >= 0.75 and s["ml"]["explain"]["acc"] - s["none"]["explain"]["acc"] >= 0.25
    out["judgment"] = {
        "pre_apply": pre_apply,
        "pre_ceiling": pre_ceiling,
        "verdict": ("not_judged" if not (pre_apply and pre_ceiling) else ("transfer" if transfer else "no_transfer")),
    }
    print(json.dumps(out["judgment"]), flush=True)
    (res_dir / f"e39_{short}_L2-13.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
