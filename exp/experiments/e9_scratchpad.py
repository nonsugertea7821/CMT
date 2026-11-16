"""E9: 途中経過を書き出させると、文章の定義に従えるようになるか。

仮説: モデルにとっての計算は連想の連鎖で、一度の処理（層を一度通るだけ）で連鎖できる段数に
上限がある。数値や暦の規則で決まる再定義（規則型）は段数が多いので、番号だけを即答させると
失敗する。途中を書き出させれば解けるはずで、改善は規則型に集中するはずである。

条件（どちらも定義文を設問の直前に置く。ベクトルは使わない）:
  direct  番号だけを即答させる（E1 の near と同じ）
  cot     先に「定義の条件と、事例がそれを満たすか」を一文で書かせ、そのあとで番号を答えさせる

使い方:
  python e9_scratchpad.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json

import torch

from e1_context_injection import ROOT, Runner, question_text

# 規則型: 数値のしきい値や暦の計算で境界が決まる再定義。それ以外は付け替え型
RULE = set("営業日 新規 週 午前 大口注文 遅延 未成年 平日 無料 夜間 大人 都市部".split())
ASK = "\n\n番号を答える前に、定義の条件と、この事例がその条件を満たすかどうかを、一文で書いてください。番号はまだ書かないでください。"
FOLLOW = "では、番号だけで答えてください。"


@torch.no_grad()
def logits_12(r, text):
    ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
    last = r.model(ids).logits[0, -1]
    return last[r.id1].item(), last[r.id2].item()


@torch.no_grad()
def reason(r, text, max_new_tokens):
    ids = r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids
    out = r.model.generate(ids, max_new_tokens=max_new_tokens, do_sample=False)
    return r.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()


def chat(r, msgs):
    return r.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--max-new-tokens", type=int, default=70)
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = data["defs"]
    items = [it for it in data["items"] if it["group"] in ("G2c", "G2k")]
    r = Runner(args.model, args.dtype)

    out = ROOT / "results" / f"e9_{args.model.split('/')[-1]}.json"
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for it in items:
        if it["id"] in res:
            continue  # 中断からの再開
        c = it["defs"][0]
        row = {"group": it["group"], "concept": c, "type": "規則" if c in RULE else "付け替え", "direct": [], "cot": [], "reasons": []}
        for swap in (False, True):
            body, correct_no = question_text(it, swap)
            q = f"次の定義に従うこと。\n{defs[c]}\n\n{body}"
            l1, l2 = logits_12(r, chat(r, [{"role": "user", "content": q}]))
            row["direct"].append((l1 - l2) if correct_no == 1 else (l2 - l1))
            msgs = [{"role": "user", "content": q + ASK}]
            why = reason(r, chat(r, msgs), args.max_new_tokens)
            msgs += [{"role": "assistant", "content": why}, {"role": "user", "content": FOLLOW}]
            l1, l2 = logits_12(r, chat(r, msgs))
            row["cot"].append((l1 - l2) if correct_no == 1 else (l2 - l1))
            row["reasons"].append(why)
        res[it["id"]] = row
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(it["id"], row["type"], "direct=%+.1f cot=%+.1f" % (sum(row["direct"]) / 2, sum(row["cot"]) / 2), flush=True)

    print("\n表記: 衝突する設問の正答率 / 衝突しない設問の正答率 / 両方に正答した概念数")
    ok = lambda row, k: sum(row[k]) / 2 > 0
    for typ in ("規則", "付け替え"):
        for k in ("direct", "cot"):
            c = [ok(v, k) for v in res.values() if v["type"] == typ and v["group"] == "G2c"]
            kk = [ok(v, k) for v in res.values() if v["type"] == typ and v["group"] == "G2k"]
            concepts = {v["concept"] for v in res.values() if v["type"] == typ}
            both = sum(all(ok(v, k) for v in res.values() if v["concept"] == cc) for cc in concepts)
            print(f"{typ:4s} {k:6s} {sum(c) / len(c):.2f} / {sum(kk) / len(kk):.2f} / {both}/{len(concepts)}")


if __name__ == "__main__":
    main()
