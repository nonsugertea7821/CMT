"""E59: 適用例を見せると、使い方をまたぐ一貫は上がるか（h_consistency_by_examples）。

仮説（exp.yaml）: {v_depend, from: cross_usage_consistency, to: application_example}。
目的との関係: d_metric の物差し（E58: 四つの使い方がそろって新しい定義に従う概念の割合 joint）で、
一貫を上げる手を一つ確かめる。E58 では、定義を文脈に置くと joint は 1.5B で 0.458、4B で 0.708 になり、
どちらも律速は apply（当てはめ）だった。適用例は apply に直接効く手なので、まずこれを測る。

題材と使い方: E58 と同じ（G2c の 24 概念、definition_choice_ja.json の言い換え。apply・para・explain・recite の 4 つ。
margin > 0 を「新しい定義に従った」とする）。学習はしない。前向き計算だけ。
E58 の測り方（設問、2 回の順序の平均、recite の負の対数尤度の差）は、この中に写して同じにした。

条件（2 つ。同じ実行の中で両方を測る）:
  near     E58 の near と同じ。「次の定義に従うこと。」と定義文を、使い方の設問の直前に置く。
  near_ex  near の前に、ほかの 2 概念の適用例を置く。
           概念 i（G2c の並び順）の例は、概念 i+1 と i+2（24 で割った余り）の G2c の設問。
           例 1 つの形: 「次の定義に従うこと。」＋その概念の定義文＋設問（apply と同じ本文、選択肢の順は元のまま）＋「答え: 正答」。
           例の後に「では、次の問いに答えてください。」を置き、続けて near と同じ本文を置く。
           例は apply の形だけ（para・explain・recite の例は見せない）。

量（条件ごと）: acc_u（使い方ごと）、joint、indep（acc の積）。E58 と同じ置換の区間も残す（判定には使わない）。
対の比較（概念ごと）: joint の当たり（四つとも margin > 0）を near と near_ex で比べ、
  b = near で外れ・near_ex で当たりの概念の数、c = near で当たり・near_ex で外れの概念の数。
  p = 符号検定の片側の p 値（b 以上が出る確率、二項分布 n = b + c、確率 1/2）。

判定（事前登録。モデルごと。1.5B と 4B の両方を測る）:
  支持: b > c かつ p ≤ 0.05。
  反証: b ≤ c。
  その他（b > c だが p > 0.05）: 判定しない。
  二つのモデルで支持と反証に分かれたら mixed。片方が判定しないなら、もう片方の判定を採る。

開示（結果を見る前に分かっていること）:
  - E58 の結果（near の acc と joint）を見てから、この手順を書いた。
  - 例の選び方（隣の 2 概念）と書き方は 1 通りだけ。例は対象の概念と違う概念のもの。
  - near は E58 と同じ測り方なので、E58 の near と同じ値が出るはず（1.5B は float32、4B は bfloat16。E58 と同じ）。
    同じ値が出たかは結果のファイルで照らし、違えば開示する。
  - 24 概念で、対の比較の検出力は低い（b + c が小さいと支持に届かない）。

使い方:
  python e59_examples_consistency.py --model Qwen/Qwen2.5-1.5B-Instruct
  python e59_examples_consistency.py --model Qwen/Qwen3-4B --dtype bfloat16
  出力: results/e59_<model>.json
"""
import argparse
import json
import math
import random

import torch

from e1_context_injection import INSTRUCTION, ROOT, Runner, question_text

INSTR_PARA = "「{L}」の定義として正しいほうを選び、番号だけで答えてください。"
EXPLAIN = "次の問いの答えは「{A}」です。そう判断する理由として正しいほうを選び、番号だけで答えてください。"
RECITE_Q = "「{L}」の定義を一文で答えてください。"
USAGES = ("apply", "para", "explain", "recite")
CONDS = ("near", "near_ex")


def near_prefix(defs, label):
    return "次の定義に従うこと。\n" + defs[label] + "\n\n"


def example_block(items, i, defs):
    parts = []
    for k in (1, 2):
        ex = items[(i + k) % len(items)]
        body, _ = question_text(ex, False)
        parts.append(near_prefix(defs, ex["defs"][0]) + body + f"\n答え: {ex['correct']}")
    return "例:\n" + "\n\n".join(parts) + "\n\nでは、次の問いに答えてください。\n"


@torch.no_grad()
def two_choice(r, user_of):
    ms = []
    for swap in (False, True):
        body, correct_no = user_of(swap)
        l1, l2 = r.logits_12(r.render(None, body))
        ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
    return sum(ms) / 2


@torch.no_grad()
def nll(r, prompt, answer):
    p = r.tok(prompt, add_special_tokens=False).input_ids
    a = r.tok(answer, add_special_tokens=False).input_ids
    ids = torch.tensor([p + a])
    labels = ids.clone()
    labels[:, : len(p)] = -100
    return r.model(ids, labels=labels).loss.item()


def measure(r, pre, it, pair):
    L = it["defs"][0]

    def apply_user(swap):
        body, c = question_text(it, swap)
        return pre + body, c

    def para_user(swap):
        opts = [pair["project"], pair["ordinary"]]
        if swap:
            opts.reverse()
        return pre + f"{INSTR_PARA.format(L=L)}\n1. {opts[0]}\n2. {opts[1]}", (2 if swap else 1)

    def explain_user(swap):
        opts = [f"「{L}」は{pair['project']}を指すから", f"「{L}」は{pair['ordinary']}を指すから"]
        if swap:
            opts.reverse()
        return pre + f"{EXPLAIN.format(A=it['correct'])}\n{it['q']}\n1. {opts[0]}\n2. {opts[1]}", (2 if swap else 1)

    prompt = r.render(None, pre + RECITE_Q.format(L=L))
    recite = nll(r, prompt, f"「{L}」は{pair['ordinary']}を指す。") - nll(r, prompt, f"「{L}」は{pair['project']}を指す。")
    return {
        "apply": two_choice(r, apply_user),
        "para": two_choice(r, para_user),
        "explain": two_choice(r, explain_user),
        "recite": recite,
    }


def joint_hits(rows, keys):
    return [all(rows[k][u] > 0 for u in USAGES) for k in keys]


def summarize(rows, keys):
    n = len(keys)
    hit = {u: [rows[k][u] > 0 for k in keys] for u in USAGES}
    acc = {u: sum(hit[u]) / n for u in USAGES}
    joint = sum(joint_hits(rows, keys)) / n
    indep = 1.0
    for u in USAGES:
        indep *= acc[u]
    rng = random.Random(0)
    sims = []
    for _ in range(10000):
        cols = {u: rng.sample(hit[u], n) for u in USAGES}
        sims.append(sum(all(cols[u][i] for u in USAGES) for i in range(n)) / n)
    sims.sort()
    lo, hi = sims[int(0.025 * 10000)], sims[int(0.975 * 10000) - 1]
    return {"n": n, "acc": acc, "joint": joint, "indep": indep, "lo": lo, "hi": hi}


def sign_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] == "G2c"]
    choice = json.loads((ROOT / "data" / "definition_choice_ja.json").read_text(encoding="utf-8"))["items"]
    r = Runner(args.model, args.dtype)

    keys = [it["defs"][0] for it in items]
    res = {"model": args.model, "dtype": args.dtype, "rows": {}, "summary": {}}
    for cond in CONDS:
        rows = {}
        for i, it in enumerate(items):
            L = it["defs"][0]
            pre = near_prefix(defs, L)
            if cond == "near_ex":
                pre = example_block(items, i, defs) + pre
            rows[L] = measure(r, pre, it, choice[L])
            print(cond, L, {u: round(v, 3) for u, v in rows[L].items()}, flush=True)
        res["rows"][cond] = rows
        res["summary"][cond] = summarize(rows, keys)

    h0 = joint_hits(res["rows"]["near"], keys)
    h1 = joint_hits(res["rows"]["near_ex"], keys)
    b = sum((not x) and y for x, y in zip(h0, h1))
    c = sum(x and (not y) for x, y in zip(h0, h1))
    p = sign_p(b, c)
    v = "supported" if (b > c and p <= 0.05) else "refuted" if b <= c else "not_judged"
    res["paired"] = {"b": b, "c": c, "p": p}
    res["judgment"] = {"consistency_by_examples": v, "joint_gain":
                       res["summary"]["near_ex"]["joint"] - res["summary"]["near"]["joint"]}
    out = ROOT / "results" / f"e59_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for cond in CONDS:
        t = res["summary"][cond]
        print(cond, {u: round(a, 3) for u, a in t["acc"].items()}, "joint", round(t["joint"], 3),
              "indep", round(t["indep"], 3), "lo/hi", t["lo"], t["hi"])
    print(res["paired"], res["judgment"])


if __name__ == "__main__":
    main()
