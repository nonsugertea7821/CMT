"""E11: 概念式をそのまま与え、途中経過も概念式の書き方で書かせる。書いた行は、1行ずつ体系で検査する。

条件（どちらも、語の概念式を spec/subj.yaml に書いたまま（語そのもの以外の表示名は外す）、設問の直前に置く）:
  direct  番号だけを即答させる（E10 の expr と同じ）
  write   先に、事例を個体・事実・帰属の行で書かせ、そのあとで番号を答えさせる

記録: 正答の margin、書いた行、行ごとの検査の結果（tools/check_line.py）。
中断しても、済んだ設問から再開する。

使い方:
  python e11_expression_scratchpad.py --model Qwen/Qwen2.5-1.5B-Instruct
"""
import argparse
import json
import sys

ROOT_TOOLS = __import__("pathlib").Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(ROOT_TOOLS))
from e1_context_injection import ROOT, Runner, question_text  # noqa: E402
from e9_scratchpad import chat, logits_12, reason  # noqa: E402
import check_line  # noqa: E402
import render_expr  # noqa: E402

HEAD = "次の概念式に従うこと。\n"
ASK = ("\n\n番号を答える前に、この事例を、上の概念式と同じ書き方で書いてください。1行に1つ、次のどれかの形で書きます。\n"
       "名前: {is: 種類}\n{is: 動詞, from: 名前, to: 名前}\n{is: is, from: 名前, to: 種類}（属さないときは neg: true を付ける）\n"
       "番号はまだ書かないでください。")
FOLLOW = "では、番号だけで答えてください。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--max-new-tokens", type=int, default=200)
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    items = [it for it in data["items"] if it["group"] in ("G2c", "G2k")]
    R, C = render_expr.Renderer(), check_line.LineChecker()
    r = Runner(args.model, args.dtype)

    out = ROOT / "results" / f"e11_{args.model.split('/')[-1]}.json"
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for it in items:
        if it["id"] in res:
            continue
        expr = "\n".join(R.text(d, mask=True) for d in it["defs"])
        row = {"group": it["group"], "concept": it["defs"][0], "direct": [], "write": [], "written": [], "checked": []}
        for swap in (False, True):
            body, correct_no = question_text(it, swap)
            q = f"{HEAD}{expr}\n\n{body}"
            l1, l2 = logits_12(r, chat(r, [{"role": "user", "content": q}]))
            row["direct"].append((l1 - l2) if correct_no == 1 else (l2 - l1))
            msgs = [{"role": "user", "content": q + ASK}]
            text = reason(r, chat(r, msgs), args.max_new_tokens)
            msgs += [{"role": "assistant", "content": text}, {"role": "user", "content": FOLLOW}]
            l1, l2 = logits_12(r, chat(r, msgs))
            row["write"].append((l1 - l2) if correct_no == 1 else (l2 - l1))
            row["written"].append(text)
            row["checked"].append([{"line": l, "form": f, "errors": e} for l, f, e in C.check(check_line.extract(text))])
        res[it["id"]] = row
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(len(c) for c in row["checked"])
        ok = sum(not x["errors"] for c in row["checked"] for x in c)
        print(it["id"], "direct=%+.1f write=%+.1f lines=%d ok=%d" % (sum(row["direct"]) / 2, sum(row["write"]) / 2, n, ok), flush=True)

    acc = lambda k, g: (lambda v: sum(v) / len(v))([sum(x[k]) / 2 > 0 for x in res.values() if x["group"] == g])
    for g in ("G2c", "G2k"):
        print(g, "direct=%.2f write=%.2f" % (acc("direct", g), acc("write", g)))
    lines = [x for v in res.values() for c in v["checked"] for x in c]
    print("書いた行 %d、検査に通った行 %d" % (len(lines), sum(not x["errors"] for x in lines)))


if __name__ == "__main__":
    main()
