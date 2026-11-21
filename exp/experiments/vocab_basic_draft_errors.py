"""h_basic_vocab_fits の途中記録: 日本語の領域の最初の下書きが型検査器で受けた誤りの傾向。

利用者の求め（下書きの誤りの傾向も記録する）による。判定には使わない（事前登録の判定は vocab_basic_place.py のまま）。
入力: results/vocab_basic_ja_draft.yaml（下書き。std と同じく extends だけで置いた形）と、
  それを置いたときの型検査器の出力 results/vocab_basic_ja_draft_tc.txt。
操作: 出力の各誤りを種類に分けて数える。種類は、法則の名前（「法則 X」）か、ノードへの指摘の文（「: 」の後ろ）。
  法則の誤りは、ja_basic のノードを引数に含むものと含まないものに分ける。
行: 種類ごとの件数と、ja_basic のノードの数。
使い方:
  python exp/experiments/vocab_basic_draft_errors.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve()


def main():
    R = HERE.parent / "results"
    text = (R / "vocab_basic_ja_draft_tc.txt").read_text(encoding="utf-8")
    items = re.split(r"\n - ", "\n" + text.split("\n", 1)[1])[1:]
    rows = {}
    for it in items:
        it = it.strip()
        m = re.match(r"法則 (\w+)", it)
        if m:
            k = f"law {m.group(1)} ({'ja_basic' if 'ja_basic.' in it else 'other'})"
        else:
            k = "node: " + it.split(": ", 1)[1].split("（")[0] if ": " in it else it
            k = re.sub(r"ja_basic\.\w+", "<ja>", k)
        rows[k] = rows.get(k, 0) + 1
    y = (R / "vocab_basic_ja_draft.yaml").read_text(encoding="utf-8")
    n_nodes = len(re.findall(r"^  j_\w+:", y, re.M))
    s = {"n_errors": len(items), "n_nodes": n_nodes, "head": text.split("\n", 1)[0]}
    out = R / "vocab_basic_draft_errors.json"
    out.write_text(json.dumps({"rows": dict(sorted(rows.items(), key=lambda kv: -kv[1])), "s": s},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
