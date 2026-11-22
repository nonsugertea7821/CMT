"""E36: 説明で学習した概念ベクトルは、適用に転移するか（h_explain_transfers_to_apply）。

系列: E20 は、適用（qa）で学習したベクトルが説明に転移しないことを観察した
（h_apply_does_not_transfer_to_explain は支持。qa の explain の acc 0.458、none 0.417）。
その含意として、逆の向きを登録した（0e7ee9f）: 体系では usage_explain は usage_apply を extends する
（説明は適用を部分に持つ）。部分（適用）から全体（説明）へは届かなかったが、全体から部分へは届く、とする解き方。

ベクトル（概念ごとに1本、層 8、文中の概念の語のトークン位置に加える。E3・E20 と同じ）:
  none    何も加えない
  ex      このスクリプトで学習する。教師は「説明」の形の設問だけ（下）。適用の二択は教師に使わない
  qa      results/e3_<model>_L8_qa.pt（E3 の記録。適用で学習。参考。ファイルがなければ省く）

ex の学習（E3 の train_vector と同じ最適化: ゼロから、Adam、lr 0.1、30 歩、例ごとの平均損失を平均）:
  例は train_qa_ja.json の学習用の設問（評価の G2c とは別の設問）。設問ごとに、選択肢の順を入れ替えた2つ:
    次の問いの答えは「{correct}」です。そう判断する理由として正しいほうを選び、番号だけで答えてください。
    {q}
    1. 「{L}」は{project}を指すから
    2. 「{L}」は{ordinary}を指すから
  続き（教師）は、project の理由の番号。理由の言い換えは definition_choice_ja.json（E20 と同じ）。

評価: concepts_ja.json の G2c（24 問、E20 と同じ）。
  apply           E3 と同じ二択（判定に使う）
  explain         E20 と同じ、答えを示して理由を選ばせる設問（操作の確かめ）
  explain_noans   E20 と同じ、答えを示さない理由の設問（参考）
  acc は margin > 0 の割合（選択肢の順を入れ替えた2回の平均）。

判定（事前登録。24 問）:
  前提（操作の確かめ）: explain の acc が ex で none より 0.25 以上高い。
  前提（天井）: apply の acc が none で 0.75 未満。
  前提のどちらかが崩れたら、判定しない（仮説は未検証のまま、観察だけ書く）。
  転移する（支持）: apply の acc が ex で 0.75 以上、かつ none より 0.25 以上高い。
  転移しない（反証）: それ以外。
  qa と explain_noans は判定に使わない。

訂正（実行の途中で書き足す。開示）:
  学習の一歩をまとめて1回で計算すると、メモリの上限（15 GB）を超えてプロセスが止められた。
  ほかの重い処理を同時に走らせていないときにも、果物で1回、社員で2回止められた（前の果物は再開で通った）。
  そこで --micro k を足した。一歩の損失（例ごとの平均損失の、例についての平均）を、k 例ずつに分けて計算し、
  勾配を足し合わせてから1歩進める。式は同じで、違いは浮動小数の丸めだけ。
  --micro なし（事前登録のまま）で学習した概念は、そのまま使う。--micro で学習した概念は train の micro に記録する。
  判定と評価は変えない。
  あわせて、再開のときに環境変数 MALLOC_ARENA_MAX=2 を付けた（メモリの割り当ての設定。計算は変えない）。

途中保存: 概念ごとに results/e36_<model>_L8.partial.pt に書き、再実行で続きから学習する。

使い方:
  python e36_explain_to_apply.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e36_<model>_L8.json と results/e36_<model>_L8_ex.pt
"""
import argparse
import json
import time

import torch

from e1_context_injection import ROOT, Runner
from e3_concept_vectors import Injector, eval_item, label_mask
from e20_explain_transfer import EXPLAIN, EXPLAIN_NOANS, choice, summarize


def explain_pairs(r, label, qa, pair):
    out = []
    for ex in qa:
        for swap in (False, True):
            opts = [f"「{label}」は{pair['project']}を指すから", f"「{label}」は{pair['ordinary']}を指すから"]
            no = 1
            if swap:
                opts.reverse()
                no = 2
            body = f"{EXPLAIN.format(A=ex['correct'])}\n{ex['q']}\n1. {opts[0]}\n2. {opts[1]}"
            out.append((r.render(None, body), str(no)))
    return out


def train_explain(r, inj, label, pairs, steps, lr, micro=None):
    d_model = r.model.config.hidden_size
    v = torch.zeros(d_model).requires_grad_(True)
    opt = torch.optim.Adam([v], lr=lr)
    rows = []
    for prompt, cont in pairs:
        n_prompt = len(r.tok(prompt, add_special_tokens=False).input_ids)
        ids, mask = label_mask(r.tok, prompt + cont, label)
        rows.append((ids, n_prompt, mask))
    n, width = len(rows), max(len(ids) for ids, _, _ in rows)
    pad = r.tok.pad_token_id if r.tok.pad_token_id is not None else r.tok.eos_token_id
    ids_b = torch.full((n, width), pad)
    att_b = torch.zeros((n, width), dtype=torch.long)
    lab_b = torch.full((n, width), -100)
    msk_b = torch.zeros((n, width, 1))
    for i, (ids, n_prompt, mask) in enumerate(rows):
        k = len(ids)
        ids_b[i, :k] = torch.tensor(ids)
        att_b[i, :k] = 1
        lab_b[i, n_prompt:k] = torch.tensor(ids[n_prompt:])
        msk_b[i, :k, 0] = torch.tensor(mask, dtype=torch.float32)
    losses = []
    chunks = [slice(0, n)] if not micro else [slice(i, min(i + micro, n)) for i in range(0, n, micro)]
    for _ in range(steps):
        opt.zero_grad()
        total = 0.0
        for s in chunks:
            inj.delta = msk_b[s] * v.view(1, 1, -1)
            logits = r.model(ids_b[s], attention_mask=att_b[s]).logits
            k = logits.shape[0]
            per_tok = torch.nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, logits.shape[-1]), lab_b[s, 1:].reshape(-1), reduction="none"
            ).view(k, -1)
            valid = (lab_b[s, 1:] != -100).float()
            loss = ((per_tok * valid).sum(1) / valid.sum(1)).sum() / n
            loss.backward()
            total += loss.item()
            del logits, per_tok, loss
        opt.step()
        losses.append(total)
    inj.delta = None
    return v.detach(), losses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layer", type=int, default=8)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--micro", type=int, default=None)
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    pairs = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    qa = json.loads((ROOT / "data" / "train_qa_ja.json").read_text(encoding="utf-8"))["train"]
    items = [x for x in data["items"] if x["group"] == "G2c"]
    concepts = sorted({x["defs"][0] for x in items})

    r = Runner(args.model)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, args.layer)

    run = f"e36_{short}_L{args.layer}"
    part = ROOT / "results" / f"{run}.partial.pt"
    ex, log = torch.load(part) if part.exists() else ({}, {})
    for c in concepts:
        if c in ex:
            continue
        t0 = time.time()
        v, losses = train_explain(r, inj, c, explain_pairs(r, c, qa[c], pairs[c]), args.steps, args.lr, args.micro)
        ex[c] = v
        log[c] = {"loss_first": losses[0], "loss_last": losses[-1], "norm": v.norm().item(), "n_train": 2 * len(qa[c]),
                  "micro": args.micro}
        print(f"[train] {c}: loss {losses[0]:.2f} -> {losses[-1]:.2f} |v|={v.norm():.1f} {time.time() - t0:.0f}s", flush=True)
        torch.save((ex, log), part)
    torch.save(ex, ROOT / "results" / f"{run}_ex.pt")

    conds = {"none": None, "ex": ex}
    qa_path = ROOT / "results" / f"e3_{short}_L{args.layer}_qa.pt"
    if qa_path.exists():
        conds["qa"] = torch.load(qa_path)
    out = {"args": vars(args), "train": log, "items": {}, "summary": {}}
    for cname, vectors in conds.items():
        rows = {}
        for it in items:
            label = it["defs"][0]
            v = None if vectors is None else vectors[label]
            rows[it["id"]] = {
                "apply": eval_item(r, inj, it, data["defs"], vectors or {}, False, vectors is not None),
                "explain": choice(r, inj, EXPLAIN.format(A=it["correct"]), it, label, pairs[label], v),
                "explain_noans": choice(r, inj, EXPLAIN_NOANS, it, label, pairs[label], v),
            }
        out["items"][cname] = rows
        out["summary"][cname] = {k: summarize(rows, k) for k in ("apply", "explain", "explain_noans")}
        print(cname, json.dumps(out["summary"][cname], ensure_ascii=False), flush=True)
    s = out["summary"]
    pre_explain = s["ex"]["explain"]["acc"] - s["none"]["explain"]["acc"] >= 0.25
    pre_ceiling = s["none"]["apply"]["acc"] < 0.75
    transfer = s["ex"]["apply"]["acc"] >= 0.75 and s["ex"]["apply"]["acc"] - s["none"]["apply"]["acc"] >= 0.25
    out["judgment"] = {
        "pre_explain": pre_explain,
        "pre_ceiling": pre_ceiling,
        "verdict": ("not_judged" if not (pre_explain and pre_ceiling) else ("transfer" if transfer else "no_transfer")),
    }
    print(json.dumps(out["judgment"]), flush=True)
    (ROOT / "results" / f"{run}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
