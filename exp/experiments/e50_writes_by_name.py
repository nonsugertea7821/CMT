"""E50: 依存する定義を書き挙げるとき、モデルは名前のない中身の中の依存を落とすか（h_model_writes_by_name）。

系列:
  #478 の事前登録で、手順を書いたモデルが、関係の差を「名詞の名前を含む行」で振り分け、
  名前のない中身（{of: ..., with: ...}）の行を漏らした。
  読む側の仮説 h_model_reads_by_name は、E49（#718、Qwen3-4B、名前を 1 つ答える形）で反証になった。
    extends 0.833、inline 1.0。1 つ選ぶ読みでは、名前のない中身の中の依存を落とさなかった。
  #478 で漏れが出たのは、当てはまるものを書き挙げる場面だった。そこで、書き挙げる形で測る（#740 で登録）。
  式は {v_rely, from: v_speak_definition, to: syntax.identifier}。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。生成は貪欲（do_sample なし）、最大 48 トークン、思考なし。

項目（24 項目、seed 5）:
  根 2 つ（A・B、どちらも {extends: entity}）と、依存する定義 4 つ:
    EA: {extends: A}                                            A に、名前の位置で依存
    IA: {extends: entity, mod: {of: [v_depend, from], with: A}}  A に、名前のない中身の中で依存
    EB: {extends: B}、IB: 同じ形で B に依存
  名前は意味のない 3 音節のローマ字。依存する 4 行の並びは項目ごとに混ぜる。根の 2 行は先頭に置く。

設問:
  「次の定義の集まりで、{R} の定義を変えたとします。意味が変わる定義の名前を、すべて挙げてください。
   名前だけを、読点で区切って答えてください。」のあとに定義の集まり。
  R = A と R = B の 2 問 × 依存する 4 行の並び 2 通り（そのまま / 逆順）= 1 項目 4 問。計 96 問。
  R = A のとき、正しいのは EA・IA、誤りは EB・IB（R = B は逆）。

測る量（問いごとに 0 か 1。応答の中に、その名前が単語として現れたら 1）:
  extends = 名前の位置で R に依存する定義を挙げた。inline = 名前のない中身の中で R に依存する定義を挙げた。
  wrong_extends・wrong_inline = R に依存しない側の、それぞれの定義を挙げた。
  それぞれ 96 問の平均を、挙げた割合とする。

判定（事前登録。96 問）:
  前提: extends ≥ 0.75（名前の位置の依存を挙げられること）、かつ wrong_extends ≤ 0.5（何でも挙げてはいないこと）。
        崩れたら判定しない。
  h_model_writes_by_name（書き挙げるとき、名前の位置に頼り、名前のない中身の中の依存を落とす）:
    支持: extends − inline ≥ 0.25。
    反証: それ以外（前提が立ったうえで、差が 0.25 未満）。
  参考（判定しない）: wrong_inline、項目ごとの応答の文字列。

開示:
  - E40〜E49 の結果を見てから、この手順を書いた。E49 で inline が高かったことを知っている。
  - 測るのは「名前を書き挙げる」ことで、定義文そのものを書くことではない。v_speak_definition の一部（依存する定義を挙げる段）だけを見る。
  - #478 で漏らしたのは、このモデルではない。読む側・書く側の一般について見る。

使い方:
  python e50_writes_by_name.py --model Qwen/Qwen3-4B
  出力: results/e50_<model>.json（途中保存: results/e50_<model>.partial.json。問いごとに保存）
"""
import argparse
import json
import random
import re

import torch

from e1_context_injection import ROOT, Runner

N_ITEMS = 24
SYL = ["ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so", "ta", "te", "to", "na", "ni", "nu", "ne",
       "no", "ha", "hi", "fu", "he", "ho", "ma", "mi", "mu", "me", "mo", "ra", "ri", "ru", "re", "ro"]
HEAD = ("次の定義の集まりで、{R} の定義を変えたとします。意味が変わる定義の名前を、すべて挙げてください。"
        "名前だけを、読点で区切って答えてください。")
KINDS = ("EA", "IA", "EB", "IB")


def make_items(seed=5):
    rng = random.Random(seed)
    used = set()

    def name():
        while True:
            w = "".join(rng.choice(SYL) for _ in range(3))
            if w not in used and not any(w in u or u in w for u in used):
                used.add(w)
                return w

    items = []
    for i in range(N_ITEMS):
        names = {k: name() for k in ("A", "B") + KINDS}
        order = list(KINDS)
        rng.shuffle(order)
        items.append({"id": i, "names": names, "order": order})
    return items


def line(n, k):
    root = n["A"] if k.endswith("A") else n["B"]
    if k.startswith("E"):
        return f"{n[k]}: {{extends: {root}}}"
    return f"{n[k]}: {{extends: entity, mod: {{of: [v_depend, from], with: {root}}}}}"


def snippet(it, reverse):
    n = it["names"]
    order = it["order"][::-1] if reverse else it["order"]
    return "\n".join([f"{n['A']}: {{extends: entity}}", f"{n['B']}: {{extends: entity}}"] + [line(n, k) for k in order])


def listed(text, name):
    return re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", text) is not None


@torch.no_grad()
def ask(r, it, root, reverse):
    prompt = r.render(None, f"{HEAD.format(R=it['names'][root])}\n{snippet(it, reverse)}")
    ids = r.tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids
    out = r.model.generate(ids, max_new_tokens=48, do_sample=False)
    text = r.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)
    n = it["names"]
    other = "B" if root == "A" else "A"
    return {"text": text,
            "extends": float(listed(text, n["E" + root])),
            "inline": float(listed(text, n["I" + root])),
            "wrong_extends": float(listed(text, n["E" + other])),
            "wrong_inline": float(listed(text, n["I" + other]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e50_{short}.partial.json"
    items = make_items()
    out = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {
        "args": vars(args), "items": {}, "summary": {}}
    r = Runner(args.model, dtype=args.dtype)
    for it in items:
        for root in ("A", "B"):
            for rev in (False, True):
                key = f"{it['id']}_{root}_{'rev' if rev else 'fwd'}"
                if key in out["items"]:
                    continue
                out["items"][key] = ask(r, it, root, rev)
                part.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(it["id"], "done", flush=True)
    rows = list(out["items"].values())
    s = {k: sum(v[k] for v in rows) / len(rows) for k in ("extends", "inline", "wrong_extends", "wrong_inline")}
    s["n"] = len(rows)
    out["summary"] = s
    pre = s["extends"] >= 0.7499 and s["wrong_extends"] <= 0.5001
    v = "not_judged"
    if pre:
        v = "supported" if s["extends"] - s["inline"] >= 0.2499 else "refuted"
    out["judgment"] = {"premise": pre, "model_writes_by_name": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e50_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
