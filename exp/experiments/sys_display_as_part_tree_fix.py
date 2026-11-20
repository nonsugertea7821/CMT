"""h_display_as_part_tree の訂正（sys_display_as_part_tree.py の後、結果を見てから、実行の前に登録した）。

訂正の理由: 元の手順は other_<v> を「版 F の誤りの文に無いもの」と決めた。版 M・X・G の other はどれも 2 で、
  中身は法則 single（1つのノードが足せる限定は1つだけ）の誤りだった。版 F にも同じ法則の誤りが 2 つあるが、
  限定の中身に display が入ると誤りの文が変わるため、文の一致では F と別のものに数えた。
  元の結果: lost = gained = 0、py_F = 2、py_M = 0、py_X = 2、py_G = 1、n_both = 0、crash = 0。
訂正した操作: other_<v> を、誤りの文の先頭の「法則 名前」（法則でない誤りは文そのもの）を鍵にして、
  版 v の鍵の数が版 F の同じ鍵の数を超えた分の合計とする（法則 part_display_explicit は除く）。
  ほかは元と同じ（写しの変え方・版・数える量・判定）。
行（sys_display_as_part_tree_fix.json）: 元と同じ。

使い方:
  python exp/experiments/sys_display_as_part_tree_fix.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_display_as_part_tree as base

OUT = base.ROOT / "exp/experiments/results/sys_display_as_part_tree_fix.json"


def key(e):
    m = re.match(r"法則 (\S+?)（", e)
    return m.group(1) if m else e


def main():
    o0, o1 = base.run(False), base.run(True)
    probes = [o0, o1]
    summary, texts = {}, {}
    summary["lost"] = len([e for e in o0["errors"] if e not in o1["errors"]])
    summary["gained"] = len([e for e in o1["errors"] if e not in o0["errors"]])
    texts["O0 vs O1"] = ([e for e in o0["errors"] if e not in o1["errors"]] + [e for e in o1["errors"] if e not in o0["errors"]])[:10]
    res = {}
    for v, nodes in base.SYNTH.items():
        res[v] = base.run(True, nodes)
        probes.append(res[v])
        law = [e for e in res[v]["errors"] if base.LAW in e]
        summary[f"py_{v}"] = len(law)
        texts[f"law {v}"] = law[:4]
    cf = collections.Counter(key(e) for e in res["F"]["errors"] if base.LAW not in e)
    for v in ("M", "X", "G"):
        cv = collections.Counter(key(e) for e in res[v]["errors"] if base.LAW not in e)
        summary[f"other_{v}"] = sum(max(0, n - cf.get(k, 0)) for k, n in cv.items())
        texts[f"other {v}"] = [k for k, n in cv.items() if n > cf.get(k, 0)][:6]
    summary["n_both"] = len(o1["both"])
    texts["both"] = o1["both"][:20]
    summary["crash"] = int(any(e.startswith("probe failed") for p in probes for e in p["errors"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": {"summary 要約": summary, "texts": texts}}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
