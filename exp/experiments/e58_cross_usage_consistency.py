"""E58: 再定義を文脈に置いたとき、四つの使い方は同じ項目でそろって従うか（h_consistency_beyond_accuracy）。

目的との関係: d_goal は再定義の成功を上げること、d_metric はそれを使い方をまたぐ一貫性（cross_usage_consistency）で
測ること。これまで（E6・E8・E20・E36）は使い方ごとの正答率を測り、使い方の間の転移を見た。同じ概念で四つの使い方が
そろって新しい定義に従う割合（一貫）は、一つの量として測っていない。ここで初めて測り、それが使い方ごとの正答率から
決まるか（独立に掛け合わせた値で足りるか）を確かめる。

題材: concepts_ja.json の G2c（再定義が元の意味と衝突する 24 概念。1 概念 1 設問）と definition_choice_ja.json の
言い換え（project / ordinary。定義文とは文言を変えてある）。学習はしない。前向き計算だけ。

条件:
  none   定義を置かない（モデルの元の意味）
  near   E1 と同じく、使い方の設問の直前に「次の定義に従うこと。」と、その概念の定義文を置く

使い方（概念ごとに 4 つ。どれも「新しい定義に従う」を正にした margin。margin > 0 を従ったとする）:
  apply    E1 の二択（question_text。選択肢の順を入れ替えた 2 回の平均）
  para     E6 の定義の言い換えの二択（INSTR。project と ordinary。2 回の平均）
  explain  E20 の、答え（correct）を示して理由を選ばせる二択（EXPLAIN。2 回の平均）
  recite   「「{L}」の定義を一文で答えてください。」への応答として、
             「「{L}」は{project}を指す。」と「「{L}」は{ordinary}を指す。」の、1 トークンあたりの負の対数尤度の差
             margin = nll(ordinary) − nll(project)

量（条件ごと、24 概念）:
  acc_u      使い方 u の margin > 0 の割合
  joint      四つとも margin > 0 の概念の割合（一貫）
  indep      acc_u の積（使い方が概念をまたいで独立なら joint の期待値）
  置換の区間: 使い方ごとに概念への割り当てを独立に並べ替え（acc_u は保たれる）、joint を 10000 回（seed 0）求め、
             その 2.5% と 97.5% の点を lo, hi とする。

判定（事前登録。near で判定し、none は物差しの基準として観察だけ書く）:
  前提: near で、0 < acc_u < 1 となる使い方が 2 つ以上ある（そうでなければ joint は acc で決まってしまうので、判定しない）。
  h_consistency_beyond_accuracy（一貫は使い方ごとの正答率から決まらない）:
    支持: near の joint が [lo, hi] の外（joint < lo または joint > hi）。
    反証: near の joint が [lo, hi] の内。
  開示: 24 概念では検出力が低い。反証は「24 概念では独立と区別できない」の意味で読む。

開示（結果を見る前に分かっていること）:
  - E1 の near の G2c apply、E6 の para（none とベクトル）、E20 の explain（none とベクトル）の値は、以前の記録にある。
    ここでは near の para・explain・recite を同じ道で測り直す（near の para・explain・recite は、まだ測っていない）。
  - recite は、E6 の define_nll（定義文そのもの）と違い、言い換えの文を一文の応答として比べる。書き方は 1 通りだけ。
  - モデルは Qwen2.5-1.5B-Instruct（E1・E6・E20 と同じ）。Qwen3-4B は E57 の後に同じ手順で測る（判定はモデルごと）。

使い方:
  python e58_cross_usage_consistency.py --model Qwen/Qwen2.5-1.5B-Instruct
  出力: results/e58_<model>.json
"""
import argparse
import json
import random

import torch

from e1_context_injection import ROOT, Runner, question_text

INSTR_PARA = "「{L}」の定義として正しいほうを選び、番号だけで答えてください。"
EXPLAIN = "次の問いの答えは「{A}」です。そう判断する理由として正しいほうを選び、番号だけで答えてください。"
RECITE_Q = "「{L}」の定義を一文で答えてください。"
USAGES = ("apply", "para", "explain", "recite")


def prefix_of(cond, defs, label):
    return "" if cond == "none" else "次の定義に従うこと。\n" + defs[label] + "\n\n"


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


def measure(r, cond, it, defs, pair):
    L = it["defs"][0]
    pre = prefix_of(cond, defs, L)

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


def summarize(rows):
    n = len(rows)
    hit = {u: [rows[k][u] > 0 for k in sorted(rows)] for u in USAGES}
    acc = {u: sum(hit[u]) / n for u in USAGES}
    joint = sum(all(hit[u][i] for u in USAGES) for i in range(n)) / n
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

    res = {"model": args.model, "rows": {}, "summary": {}}
    for cond in ("none", "near"):
        rows = {}
        for it in items:
            L = it["defs"][0]
            rows[L] = measure(r, cond, it, defs, choice[L])
            print(cond, L, {u: round(v, 3) for u, v in rows[L].items()}, flush=True)
        res["rows"][cond] = rows
        res["summary"][cond] = summarize(rows)

    s = res["summary"]["near"]
    nontrivial = sum(0 < s["acc"][u] < 1 for u in USAGES)
    if nontrivial < 2:
        v = "not_judged"
    elif s["joint"] < s["lo"] - 1e-9 or s["joint"] > s["hi"] + 1e-9:
        v = "supported"
    else:
        v = "refuted"
    res["judgment"] = {"nontrivial": nontrivial, "consistency_beyond_accuracy": v,
                       "joint_minus_indep": s["joint"] - s["indep"]}
    out = ROOT / "results" / f"e58_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for cond in ("none", "near"):
        t = res["summary"][cond]
        print(cond, {u: round(a, 3) for u, a in t["acc"].items()}, "joint", round(t["joint"], 3),
              "indep", round(t["indep"], 3), "lo/hi", t["lo"], t["hi"])
    print(res["judgment"])


if __name__ == "__main__":
    main()
