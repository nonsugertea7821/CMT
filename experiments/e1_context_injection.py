"""E1: 概念の定義を文章として文脈に注入したとき、モデルはどこまで定義に従うか。

条件:
  none      定義なし（モデルの元の意味だけ）
  near      設問に関係する定義だけを、設問の直前に置く
  glossary  全定義を用語集としてシステムプロンプトに置く
  far-N     用語集のあとに、無関係な文章を約Nトークン挟む

測り方:
  二択の設問を出し、次の1トークンで「1」と「2」のロジットを比べる。
  選択肢の順序を入れ替えた2回の平均で、位置の偏りを打ち消す。
  margin = 正答のロジット − 誤答のロジット（2回の平均）。margin > 0 を正答とする。

使い方:
  python e1_context_injection.py --model Qwen/Qwen2.5-0.5B-Instruct
"""
import argparse
import copy
import json
import random
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).parent

FILLER_SENTENCES = [
    "今朝は空がよく晴れて、遠くの山までくっきりと見えた。",
    "駅前の通りには、古くから続くパン屋と小さな花屋が並んでいる。",
    "川沿いの道を歩くと、水鳥が群れになって休んでいるのが見える。",
    "祖母は毎年、庭でとれた梅を塩に漬けて梅干しを作る。",
    "この地方は冬に雪が多く、屋根の雪下ろしが欠かせない。",
    "港では早朝から漁船が戻り、魚を下ろす声が響いていた。",
    "味噌汁は、だしを取ってから具を入れ、最後に味噌を溶く。",
    "山の上の展望台からは、湾に浮かぶ島々を一度に見渡せる。",
    "夏祭りの夜には、通りに屋台が並び、太鼓の音が遠くまで届く。",
    "図書室の窓際の席は、午後になると日が差して暖かい。",
    "畑では春に種をまき、秋には大きなかぼちゃが実る。",
    "古い城の石垣には、長い年月のあいだに苔が厚く付いている。",
    "雨上がりの森は土の匂いが濃く、葉の先から水が落ちてくる。",
    "子どもたちは放課後、公園の広場で日が暮れるまで走り回る。",
    "峠を越えると急に視界が開け、一面の茶畑が広がっていた。",
    "湯を沸かして急須に注ぎ、少し待ってから茶碗に分ける。",
]

INSTRUCTION = {
    "fill": "次の文の空欄に入る語として正しいほうを選び、番号だけで答えてください。",
    "yesno": "次の問いに、正しいほうを選び、番号だけで答えてください。",
}


def make_filler(tok, n_tokens: int, seed: int = 0) -> str:
    rng = random.Random(seed)
    out, count = [], 0
    while count < n_tokens:
        s = rng.choice(FILLER_SENTENCES)
        out.append(s)
        count += len(tok(s, add_special_tokens=False).input_ids)
    return "".join(out)


def question_text(item, swap: bool) -> tuple[str, int]:
    """設問の本文と、正答の番号（1か2）を返す。"""
    opts = [item["correct"], item["wrong"]]
    if swap:
        opts.reverse()
    correct_no = 2 if swap else 1
    body = f"{INSTRUCTION[item['type']]}\n{item['q']}\n1. {opts[0]}\n2. {opts[1]}"
    return body, correct_no


class Runner:
    def __init__(self, model_name: str):
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float32, use_safetensors=True
        )
        self.model.eval()
        ids = [self.tok(s, add_special_tokens=False).input_ids for s in ("1", "2")]
        assert all(len(i) == 1 for i in ids), "「1」「2」が1トークンでない"
        self.id1, self.id2 = ids[0][0], ids[1][0]

    def render(self, system: str | None, user: str) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user})
        return self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    @torch.no_grad()
    def prefix_cache(self, prefix_text: str):
        ids = self.tok(prefix_text, return_tensors="pt", add_special_tokens=False).input_ids
        out = self.model(ids, use_cache=True)
        return ids, out.past_key_values

    @torch.no_grad()
    def logits_12(self, full_text: str, cache=None) -> tuple[float, float]:
        ids = self.tok(full_text, return_tensors="pt", add_special_tokens=False).input_ids
        if cache is not None:
            p_ids, pkv = cache
            n = p_ids.shape[1]
            assert torch.equal(ids[:, :n], p_ids), "接頭部が一致しない"
            out = self.model(ids[:, n:], past_key_values=copy.deepcopy(pkv), use_cache=True)
        else:
            out = self.model(ids)
        last = out.logits[0, -1]
        return last[self.id1].item(), last[self.id2].item()

    def margin(self, item, system_fn, user_fn, cache=None) -> dict:
        ms = []
        for swap in (False, True):
            body, correct_no = question_text(item, swap)
            text = self.render(system_fn(item), user_fn(item, body))
            l1, l2 = self.logits_12(text, cache)
            ms.append((l1 - l2) if correct_no == 1 else (l2 - l1))
        return {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--far", type=int, nargs="*", default=[500, 2000])
    args = ap.parse_args()

    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs, items = data["defs"], data["items"]
    r = Runner(args.model)

    glossary = "以下は当プロジェクトの用語集である。回答はこの用語集の定義に従うこと。\n" + "\n".join(
        defs.values()
    )
    n_gloss = len(r.tok(glossary, add_special_tokens=False).input_ids)

    conds = {}
    # none: 定義なし
    conds["none"] = dict(system=lambda it: None, user=lambda it, body: body, prefix=None)
    # near: 関係する定義だけを設問の直前に
    conds["near"] = dict(
        system=lambda it: None,
        user=lambda it, body: "次の定義に従うこと。\n"
        + "\n".join(defs[d] for d in it["defs"])
        + "\n\n"
        + body,
        prefix=None,
    )
    # glossary: 全定義をシステムプロンプトに
    conds["glossary"] = dict(system=lambda it: glossary, user=lambda it, body: body, prefix=glossary)
    # far-N: 用語集のあとに無関係な文章
    for n in args.far:
        sys_text = glossary + "\n\n以下は参考の文章である。\n" + make_filler(r.tok, n)
        conds[f"far-{n}"] = dict(
            system=lambda it, s=sys_text: s, user=lambda it, body: body, prefix=sys_text
        )

    results = {"model": args.model, "glossary_tokens": n_gloss, "items": {}, "summary": {}}
    for name, c in conds.items():
        t0 = time.time()
        cache = None
        if c["prefix"] is not None:
            # システムプロンプトまでを一度だけ計算して使い回す
            probe = r.render(c["prefix"], "\x00")
            cache = r.prefix_cache(probe[: probe.index("\x00")])
        for it in items:
            res = r.margin(it, c["system"], c["user"], cache)
            results["items"].setdefault(it["id"], {"group": it["group"]})[name] = res
        print(f"[{name}] {time.time() - t0:.0f}s", flush=True)

    groups = sorted({it["group"] for it in items})
    for name in conds:
        row = {}
        for g in groups + ["ALL"]:
            rs = [v[name] for v in results["items"].values() if g == "ALL" or v["group"] == g]
            row[g] = {
                "n": len(rs),
                "acc": sum(x["margin"] > 0 for x in rs) / len(rs),
                "acc_both": sum(x["both"] for x in rs) / len(rs),
                "mean_margin": sum(x["margin"] for x in rs) / len(rs),
            }
        results["summary"][name] = row

    out = ROOT / "results" / f"e1_{args.model.split('/')[-1]}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nmodel={args.model}  glossary={n_gloss} tokens")
    print("acc = 2順序の平均marginが正 / both = 2順序とも正答 / m = 平均margin")
    for g in groups + ["ALL"]:
        print(f"\n{g} (n={results['summary']['none'][g]['n']})")
        for name in conds:
            s = results["summary"][name][g]
            print(f"  {name:10s} acc={s['acc']:.2f}  both={s['acc_both']:.2f}  m={s['mean_margin']:+.2f}")


if __name__ == "__main__":
    main()
