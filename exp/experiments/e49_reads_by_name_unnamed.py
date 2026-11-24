"""E49: 名前で答える形で、モデルは名前のない中身の中の依存を落とすか（h_model_reads_by_name #483）。

系列:
  E40（この枝。Qwen2.5-1.5B、T ごとの二択）は前提（extends の acc ≥ 0.75）が崩れ、判定しなかった。
  その後、形が判定を左右することがわかった:
    E47（#737、Qwen3-4B、名前で答える形）で extends 0.958。h_model_misses_extends は反証。
    E48（#725、同じ項目で番号で選ぶ形）で decoy 0.083、名前で答える形では 0.875。h_verdict_by_question_format は支持。
  ここでは、前提が立ちやすい名前で答える形で、E40 と同じ 3 つの書き方（extends・inline・named）を比べる。

モデル: Qwen/Qwen3-4B（bf16）。学習はしない。前向き計算だけ。
項目: e40_reads_by_name.make_items(seed=3)（新しい項目。24 項目）。定義の集まりは e40_reads_by_name.snippet。
  A に依存する側が X、B に依存する（A に依存しない）側が Y。

設問（E47 と同じ）:
  「次の定義の集まりで、{A} の定義を変えたとします。意味が変わる定義の名前を、1 つだけ答えてください。」のあとに定義の集まり。
  名前の割り当て 2 通り（そのまま / X と Y の名前を入れ替え）× 定義の並び 2 通り（X が先 / Y が先）= 4 回。
  s(名前) = 応答の頭に名前を置いたときの、名前のトークンの対数確率の和。d = s(X の名前) − s(Y の名前)。
  並びごとに、名前の割り当て 2 通りの d を平均する: pair = [X が先の平均, Y が先の平均]。
  acc = pair の平均 > 0 の割合。order_robust = pair の 2 つがどちらも > 0 の割合。

判定（事前登録。24 項目。線は E40 と同じ）:
  前提: extends の acc ≥ 0.75。崩れたら判定しない。
  h_model_reads_by_name（名前の位置で読み、名前のない中身の中の依存を落とす）:
    支持: extends の acc − inline の acc ≥ 0.25。
    反証: それ以外（前提が立ったうえで、差が 0.25 未満）。
  named は参考（判定に使わない）。

開示:
  - E40〜E48 の結果を見てから、この手順を書いた。名前で答える形を選んだのは、E47 で extends が高かったから（見てから選んだ）。
  - E47 の decoy・control の P（{extends: entity, mod: M}）は、この named と同じ書き方で、名前で答える形で 0.875・0.917 だった。
    inline（名前のない中身）はまだ名前で答える形で測っていない。
  - E40 とはモデルも形も違う。E40 の訂正ではなく、同じ仮説への 2 つ目の測り。結果ファイルが E40 のものより後に来るので、自動マージの条件に合わない。手で見る。

使い方:
  python e49_reads_by_name_unnamed.py --model Qwen/Qwen3-4B
  出力: results/e49_<model>.json（途中保存: results/e49_<model>.partial.json）
"""
import argparse
import json

from e1_context_injection import ROOT, Runner
from e40_reads_by_name import make_items, snippet
from e47_extends_unnamed import HEAD, score, summ

CONDS = ("extends", "inline", "named")


def d_one(r, it, cond, swap_names, x_first):
    it = dict(it, X=it["Y"], Y=it["X"]) if swap_names else dict(it)
    it["x_first"] = x_first
    prompt = r.render(None, f"{HEAD.format(A=it['A'])}\n{snippet(it, cond)}")
    return score(r, prompt, it["X"]) - score(r, prompt, it["Y"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()
    short = args.model.split("/")[-1]
    res = ROOT / "results"
    part = res / f"e49_{short}.partial.json"
    items = make_items(seed=3)
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
    pre = s["extends"]["acc"] >= 0.7499
    v = "not_judged"
    if pre:
        v = "supported" if s["extends"]["acc"] - s["inline"]["acc"] >= 0.2499 else "refuted"
    out["judgment"] = {"premise": pre, "model_reads_by_name": v}
    print(json.dumps(s, indent=1), flush=True)
    print(json.dumps(out["judgment"]), flush=True)
    (res / f"e49_{short}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    part.unlink()


if __name__ == "__main__":
    main()
