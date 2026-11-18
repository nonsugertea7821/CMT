"""仮説 h_annotation_gold（依存する(日本語の文章から読み戻した式, 注釈)）のための材料を取り出す:
claims.yaml のコメントのうち、仮説の中身を人が日本語で言い換えたものを、その仮説の式と対にする。
コメントを消す（h_comment_ban）前に取り出すことで、変換器の正解の材料を残す。結果を見る前に、この手順を登録した。

この実験は取り出しだけで、h_annotation_gold の判定はしない（判定は、変換器と読み戻しの実験でする）。
なので観察を置かず、仮説の状態も変えない。

取り出し方（機械的。手で選ばない）:
  ブロック: claims.yaml を、行頭の空白のあとに「# =====」で始まる行で区切った範囲。
  言い換え: コメント行の中の「中身は「…」」の … の部分（かぎ括弧の入れ子を数えて閉じる）。
  対の相手: 同じブロックにある仮説（individuals の h_ で始まる識別子で、is が exp.hyp_ で始まるもの）のうち、
    言い換えの行に行番号が最も近いもの。同じブロックに仮説がなければ、対にせず unpaired に数える。
  式: exp_check.build() の仮説の s, p, o。機械の訳: display.fact(T, p, s, o)（issue の題と同じ訳）。
  文脈: そのブロックのコメント行をすべて（記述。後の分け方に使う）。
数える量（要約）: comments（コメント行の数）, blocks, quotes（言い換えの数）, paired, unpaired
行（annotation_pairs.json）:
  "summary 要約": 上の数
  "pairs": [{hyp, line, human, machine, formula, context}]
下調べ（開示）: 手順を書く前に、「中身は」を含む行を grep で見た（11 行。そのうち「中身は「」の形は 7 行ほど）。

使い方:
  python exp/experiments/annotation_pairs.py
"""
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/display"), str(ROOT / "exp/src")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import exp_check  # noqa: E402
import display  # noqa: E402

OUT = ROOT / "exp/experiments/results"
SRC = ROOT / "cscl/design/claims.yaml"
HYP = re.compile(r"^\s+(h_[a-z0-9_]+): \{is: exp\.hyp_")
HEAD = re.compile(r"^\s*# =====")
COMMENT = re.compile(r"^\s*#")


def quotes(text):
    out, i = [], 0
    while (i := text.find("中身は「", i)) >= 0:
        j, depth = i + len("中身は「"), 1
        k = j
        while k < len(text) and depth:
            depth += {"「": 1, "」": -1}.get(text[k], 0)
            k += 1
        out.append(text[j:k - 1] if depth == 0 else text[j:])
        i = k
    return out


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, S, M, C = exp_check.build()
    L = SRC.read_text(encoding="utf-8").split("\n")
    blocks, cur = [], []
    for n, l in enumerate(L, 1):
        if HEAD.match(l) and cur:
            blocks.append(cur)
            cur = []
        cur.append((n, l))
    blocks.append(cur)
    pairs, n_quotes, unpaired = [], 0, 0
    for b in blocks:
        hyps = [(n, m.group(1)) for n, l in b if (m := HYP.match(l))]
        ctx = [l.strip() for n, l in b if COMMENT.match(l)]
        for n, l in b:
            if not COMMENT.match(l):
                continue
            for q in quotes(l):
                n_quotes += 1
                if not hyps:
                    unpaired += 1
                    continue
                _, h = min(hyps, key=lambda x: abs(x[0] - n))
                cid = next((c for c in C["hypotheses"] if tc.short(c) == h), None)
                x = C["hypotheses"].get(cid) if cid else None
                machine = formula = None
                if x:
                    ss, oo = ([v] if isinstance(v, str) else v for v in (x["s"], x["o"]))
                    machine = "、".join(display.fact(T, x["p"], a, b2) for a in ss for b2 in oo)
                    formula = {"p": x["p"], "s": x["s"], "o": x["o"]}
                pairs.append({"hyp": h, "line": n, "human": q, "machine": machine, "formula": formula, "context": ctx})
    summ = {"comments": sum(1 for l in L if COMMENT.match(l)), "blocks": len(blocks), "quotes": n_quotes,
            "paired": len(pairs), "unpaired": unpaired}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "annotation_pairs.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ}, "pairs": pairs}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for p in pairs:
        print(p["hyp"], "|", p["human"], "|", p["machine"])


if __name__ == "__main__":
    main()
