"""E34: h_state_unique_display を確かめる: 隠れ状態は、ちょうど一つの表示語を指すか。

仮説（exp.yaml）: v_refer(h, v_refer(hidden_state, syntax.display, at: {count: 1}))。issue #477。
  出どころ: 利用者の言い直し「モデルの内部状態は幾何空間の一部を指し示すため、何を考えているか一意に表示語に出来る」。

問い: 語を見せずに概念を思い浮かべさせたとき、その状態からモデル自身の読み出しで出てくる表示語は、
  候補の中のちょうど一つに集まり、それが正しい語か。
操作（モデル Qwen/Qwen2.5-1.5B-Instruct、重みは固定、学習しない）:
  状態を作る文（語は＿＿で隠す）:
    D: data/concepts_ja.json の defs の 55 語。定義文の「語：」より後を説明として使い、説明の中の語は＿＿に置き換える。
       設問「次の説明に当たる語を一つ答えてください。\\n説明：<説明>」。候補は 55 語。
    S_new: data/sense_pairs_ja.json の 24 語の new の 3 文。文の中の語を＿＿に置き換える。
       設問「次の文の＿＿に入る語を一つ答えてください。\\n文：<文>」。候補は 24 語。
    S_old: 同じく old の 3 文。候補は 24 語。
  読み出し: 設問をチャットの形にし、応答の頭に「「」を置いて、候補 w ごとに log P(w」 | 文脈) を足し合わせる
    （w のトークンと閉じかっこの対数確率の和）。候補の上で正規化して q(w) とする。
    q はモデルの最終層の読み出しで、状態から語への写像はモデル自身のもの（外から読み出しを学習しない）。
  状態ごと: hit（q の最大が正しい語）、n_eff = exp(H(q))（指している語の実効の数）、q_max。
    一意: hit かつ n_eff < 2。
  状態の数: D 55、S_new 72、S_old 72、計 199。
  集計（s）: 組（D, S_new, S_old）ごとと全体で、n, share_hit, share_unique（一意の割合）, mean_n_eff。
行（e34_state_unique_display.json）: 状態ごとに set, word, top, q_max, q_true, n_eff, hit, unique。
  途中の結果は e34_state_unique_display.partial.json に状態ごとに書き、再開のときは済んだ状態を飛ばす
  （コンテナが再起動するため。計算は決まっていて、やり直しても同じ値になる）。

判定（事前に決める。全体の share_unique で）:
  モデルが読めないか状態が 100 未満なら外れ（状態を変えない）。
  支持: share_unique >= 0.8。
  反証: share_unique <= 0.5。
  mixed: それ以外。
開示:
  - exp.yaml の hidden_state は、語のトークン位置の層の出力。ここでは語を隠すので、語の位置はなく、
    設問の最後の位置の状態をモデルの読み出しで語にしている。仮説の「状態が一意に語を指す」を、語を見せない状態で問うための置き換え。
  - 読み出しは候補の集合の上で閉じている。候補にない語へ向かう分は q に入らない。
  - n_eff < 2 の閾値と 0.8 / 0.5 は、走らせる前に決めた。数は計算していない。
  - D の G1 は一般の類義語で、モデルの既定の意味のままで当たりうる。G3・G4 は当プロジェクトの定義で、
    名前から中身が分からないものがある。組ごとの値も出すが、判定は全体で行う。
  - S_old は語のふつうの意味の文、S_new は当プロジェクトの意味の文。表示語はどちらも同じ語。
使い方:
  python e34_state_unique_display.py
"""
import json
import math
import time

import torch

from e1_context_injection import ROOT, Runner

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
OUT = ROOT / "results" / "e34_state_unique_display.json"
PART = ROOT / "results" / "e34_state_unique_display.partial.json"
Q_DEF = "次の説明に当たる語を一つ答えてください。\n説明：{}"
Q_SEN = "次の文の＿＿に入る語を一つ答えてください。\n文：{}"
OPEN, CLOSE = "「", "」"


def states():
    c = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    words = list(c["defs"])
    out = []
    for w, t in c["defs"].items():
        body = t.split("：", 1)[1].replace(w, "＿＿")
        out.append(("D", w, Q_DEF.format(body), words))
    s = json.loads((ROOT / "data" / "sense_pairs_ja.json").read_text(encoding="utf-8"))
    s = s["pairs"]
    sw = list(s)
    for kind in ("new", "old"):
        for w in sw:
            for i, sent in enumerate(s[w][kind]):
                out.append((f"S_{kind}", f"{w}#{i}", Q_SEN.format(sent.replace(w, "＿＿")), sw))
    return out


@torch.no_grad()
def readout(r, prompt, cands):
    ctx = r.render(None, prompt) + OPEN
    c_ids = r.tok(ctx, add_special_tokens=False).input_ids
    seqs, spans = [], []
    for w in cands:
        full = r.tok(ctx + w + CLOSE, add_special_tokens=False).input_ids
        assert full[:len(c_ids)] == c_ids, "文脈のトークンが一致しない"
        seqs.append(full)
        spans.append((len(c_ids), len(full)))
    L = max(len(x) for x in seqs)
    pad = r.tok.pad_token_id if r.tok.pad_token_id is not None else 0
    ids = torch.tensor([x + [pad] * (L - len(x)) for x in seqs])
    att = torch.tensor([[1] * len(x) + [0] * (L - len(x)) for x in seqs])
    lp = torch.log_softmax(r.model(input_ids=ids, attention_mask=att).logits.float(), -1)
    scores = []
    for b, (a, e) in enumerate(spans):
        scores.append(sum(lp[b, t - 1, ids[b, t]].item() for t in range(a, e)))
    m = max(scores)
    z = [math.exp(x - m) for x in scores]
    tot = sum(z)
    return [x / tot for x in z]


def summary(rows):
    def agg(rs):
        n = len(rs)
        if not n:
            return {"n": 0}
        return {"n": n, "share_hit": sum(x["hit"] for x in rs) / n,
                "share_unique": sum(x["unique"] for x in rs) / n,
                "mean_n_eff": sum(x["n_eff"] for x in rs) / n}
    s = {k: agg([x for x in rows if x["set"] == k]) for k in ("D", "S_new", "S_old")}
    s["all"] = agg(rows)
    return s


def main():
    done = json.loads(PART.read_text(encoding="utf-8")) if PART.exists() else {}
    r = Runner(MODEL)
    for st, key, prompt, cands in states():
        k = f"{st}/{key}"
        if k in done:
            continue
        t = time.time()
        q = readout(r, prompt, cands)
        w = key.split("#")[0]
        top = cands[max(range(len(q)), key=q.__getitem__)]
        h = -sum(x * math.log(x) for x in q if x > 0)
        n_eff = math.exp(h)
        hit = top == w
        done[k] = {"set": st, "word": key, "top": top, "q_max": max(q), "q_true": q[cands.index(w)],
                   "n_eff": n_eff, "hit": hit, "unique": hit and n_eff < 2}
        PART.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{k} top={top} q_max={max(q):.2f} n_eff={n_eff:.2f} {time.time() - t:.0f}s", flush=True)
    rows = list(done.values())
    OUT.write_text(json.dumps({"rows": done, "s": summary(rows)}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    PART.unlink()
    print(json.dumps(summary(rows), ensure_ascii=False))


if __name__ == "__main__":
    main()
