"""h_basic_vocab_fits の途中記録: 英語の領域を置いたときの書き直しごとの誤りの傾向。

利用者の求め（書き直しの誤りの傾向も記録する）による。判定には使わない。
入力: results/vocab_basic_en_rw<n>.yaml と、書いた時点に残した型検査器の出力 results/vocab_basic_en_rw<n>_tc.txt
  （このスクリプトは型検査器を走らせない）。
  rw1: 日本語の領域と同じ式を、識別子 <en> で書いたもの。
  rw2: rw1 で one_name か「動詞の式が同じ」に当たった語を外したもの（事前登録の追記 2 による）。
  rw3: rw2 に残った語は、外した語を式に使うので、英語の領域の中では書けない。すべて外したもの。
操作: 誤りを種類に分けて数える（vocab_basic_rewrite_errors.py と同じ分け方）。ほかの領域の語とぶつかった誤りは、
  相手の領域ごとにも数える。
使い方:
  python exp/experiments/vocab_basic_en_errors.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve()


def tally(text):
    items = re.split(r"\n - ", "\n" + text.split("\n", 1)[1])[1:] if text.startswith("検査に失敗") else []
    rows = {}
    cross = 0
    for it in items:
        it = it.strip()
        m = re.match(r"法則 (\w+)", it)
        if m:
            k = f"law {m.group(1)}"
        elif it.startswith("動詞の式が同じ"):
            k = "node: 動詞の式が同じ"
        else:
            k = "node: " + re.sub(r"\b(?:go|come|keep|see)\b", "<removed>", it.split(": ", 1)[1].split("（")[0])
        rows[k] = rows.get(k, 0) + 1
        cross += "ja_basic." in it and "en_basic." in it
    return len(items), cross, dict(sorted(rows.items(), key=lambda kv: -kv[1]))


def main():
    R = HERE.parent / "results"
    rows = {}
    for p in sorted(R.glob("vocab_basic_en_rw*_tc.txt")):
        name = re.search(r"(rw\d+)", p.name).group(1)
        n, cross, kinds = tally(p.read_text(encoding="utf-8"))
        y = (R / f"vocab_basic_en_{name}.yaml").read_text(encoding="utf-8")
        rows[name] = {"n_errors": n, "n_cross_ja": cross, "n_nodes": len(re.findall(r"^  (?!en_basic:)\w+: ", y, re.M)) ,
                      "kinds": kinds}
    s = {"errors_by_step": [r["n_errors"] for r in rows.values()], "nodes_by_step": [r["n_nodes"] for r in rows.values()]}
    (R / "vocab_basic_en_errors.json").write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
