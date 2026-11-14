"""候補2の試験。

候補2:
  次元は3つ。持続（名詞）、生起（動詞）、修飾（修飾語）。
  原始的な最上位を持つのは持続と生起だけ。修飾の次元の住人は、すべて持続か生起の語根から作られる。
  修飾は、持続にも生起にも当てられる。当てた結果は、当てた相手と同じ次元にとどまる。

測るもの:
  1. いまの語彙の中で、ある次元のものが、別の次元のものを作るのに何回使われているか（3×3 の表）。
  2. 修飾語的な値 40種類が、持続か生起の語根から作れるか（spec/trial/modifier_roots.yaml、手作業の判定）。
"""
import collections
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
O = yaml.safe_load((ROOT / "spec" / "ontology.yaml").read_text(encoding="utf-8"))
E, R, A = O["entities"], O["relations"], O["classifications"]
roots = yaml.safe_load((ROOT / "spec" / "trial" / "modifier_roots.yaml").read_text(encoding="utf-8"))
# 列挙値の品詞（軸ごと、手作業）。N=名詞的、V=動詞的、M=修飾語的
POS = dict(dependence="M", realization="M", grounding="M", temporal_extent="M", aboutness="V", unit="N", language="M",
           speech_act="V", speaker="N", persistence="M", expression_part="N", options="N", task="V",
           prior_meaning_presence="M", agreement_with_prior="M", boundary_kind="M", relevance_to_question="M",
           function="V", weight_state="M", weight_access="M", origin="M", experimental_role="M", quantity="N",
           counted_side="M", option_order="M", role_function="V", scope_of_use="M", intermediate_output="M",
           action="V", delivered="N", word_substitution="M", position_to_word="M", training_use="M",
           layer_count="M", visibility_of_original="M")
DIM = {"continuant": "C", "occurrent": "O", "N": "C", "V": "O", "M": "M"}


def dim(eid):
    while "is" in E[eid]:
        eid = E[eid]["is"]
    return DIM[eid]


def end(rid, side):
    while rid in R:
        if side in R[rid]:
            return R[rid][side]
        rid = R[rid].get("is")


T = collections.Counter()   # (作るのに使われる側の次元, 作られる側の次元, 何として)
for eid, e in E.items():
    if "is" not in e:
        continue
    d = dim(eid)
    T[(d, d, "上位として")] += 1
    for axis, val in e["where"].items():
        a = A[axis]
        T[("O", "M", "修飾語の動詞の部分として（軸のもとの関係）")] += 1
        T[("M", d, "修飾語を当てる")] += 1
        for v in val if isinstance(val, list) else [val]:
            if "values" in a:
                f = DIM[POS[axis]]
                T[(f, "M", "修飾語の中身として（表示語だけの値）")] += 1
            elif a.get("number"):
                T[("数", "M", "修飾語の中身として")] += 1
            else:
                T[(dim(v), "M", "修飾語の中身として（実体）")] += 1
for aid, a in A.items():
    if aid != "classification" and a.get("of") != "relation":
        T[("O", "C", "軸として（関係を名詞として見る）")] += 1
for rid, r in R.items():
    if rid in ("relation", "from_to"):
        continue
    for side in ("from", "to"):
        t = end(rid, side)
        if t in E:
            T[(dim(t), "O", "関係の端として")] += 1

print("== 1. 次元をまたぐ使われ方（使われる側 → 作られる側） ==")
cells = collections.Counter()
for (s, t, how), n in T.items():
    cells[(s, t)] += n
names = {"C": "持続", "O": "生起", "M": "修飾", "数": "数"}
for s in ("C", "O", "M", "数"):
    print(f"{names[s]}から  " + "  ".join(f"{names[t]}へ {cells[(s, t)]:4d}" for t in ("C", "O", "M")))
print()
for (s, t, how), n in sorted(T.items(), key=lambda x: -x[1]):
    print(f"{n:4d}  {names[s]} → {names[t]}  {how}")

print("\n== 2. 修飾語的な値は、持続か生起の語根から作れるか ==")
by = collections.Counter(v["root_dim"] for v in roots.values())
print(f"全 {len(roots)} 種類: 生起の語根から {by['O']}、持続の語根から {by['C']}、数量詞 {by['Q']}")
need = collections.Counter(n for v in roots.values() for n in v["needs"])
print("語根と補語のほかに必要なもの: " + "、".join(f"{k} {v}" for k, v in need.most_common()))
print(f"何も足さずに作れる: {sum(1 for v in roots.values() if not v['needs'])}")
