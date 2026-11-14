"""候補1の試験: いまの語彙を「関係 → 修飾 → 分類」の3操作だけで書き直せるかを数える。

候補1:
  次元は、開いている端の数で分かれる。生起=2、修飾=1、持続=0。
  関係: 持続 → 生起（物と物の間に結び付きを立てる）
  修飾: 生起 → 修飾（結び付きの一方の端を固定する）
  分類: 修飾 → 持続（限定する働きを物に当てて、種類を切り出す）

いまの実体は「上位 [軸=値]」で書かれている。軸のもとになる関係を生起、値を固定する端の中身とみなすと、
各実体は「上位 | 関係(_, 値)」に機械的に写せる。写した結果を、候補1の操作で足りるかどうかで分類する。
"""
import collections
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
O = yaml.safe_load((ROOT / "spec" / "ontology.yaml").read_text(encoding="utf-8"))
E, R, A = O["entities"], O["relations"], O["classifications"]


def top(eid):
    while "is" in E[eid]:
        eid = E[eid]["is"]
    return eid


def rel_kind(rid):
    r = R[rid]
    if "def" in r:
        return "述語論理の定義を添えた合成"
    w = r.get("where") or {}
    if "via" in w:
        return "生起体を介する"
    if "value_space" in w or rid in ("takes", "has_count"):
        return "値へ結ぶ"
    if "inverse_of" in w:
        return "逆向き"
    return "両端の種類と法則だけ"


stats = collections.Counter()
by_problem = collections.defaultdict(list)
verbs = collections.Counter()
for eid, e in E.items():
    if "is" not in e:
        continue
    side = top(eid)
    stats[f"実体: {E[side]['ja']}の側"] += 1
    problems = set()
    if side == "occurrent":
        problems.add("P1 生起体を修飾して生起体の下位を作っている（候補1の分類は持続へしか写さない）")
    for axis, val in e["where"].items():
        a = A[axis]
        verbs[a["from"]] += 1
        for v in val if isinstance(val, list) else [val]:
            if "values" in a:
                stats["修飾の中身: 列挙した値（実体でない）"] += 1
                problems.add("P2 固定する端の中身が実体でなく、表示語だけの値である")
            elif a.get("number"):
                stats["修飾の中身: 数"] += 1
                problems.add("P3 固定する端の中身が数である")
            else:
                stats[f"修飾の中身: 実体（{E[top(v)]['ja']}）"] += 1
        if isinstance(val, list):
            problems.add("P4 1つの端に複数の中身を入れている")
    if not problems:
        by_problem["問題なし"].append(eid)
    for pr in problems:
        by_problem[pr].append(eid)

print("== 実体と修飾の中身 ==")
for k, v in sorted(stats.items()):
    print(f"{v:4d}  {k}")
print("\n== 候補1で書けるか ==")
n = sum(1 for e in E.values() if "is" in e)
for k in sorted(by_problem):
    ids = by_problem[k]
    print(f"{len(ids):4d} / {n}  {k}")
    print("        例: " + "、".join(E[i]["ja"] for i in ids[:6]))
print("\n== 生起（関係）の出どころ ==")
kinds = collections.Counter(rel_kind(r) for r in verbs)
for k, v in kinds.most_common():
    print(f"{v:4d}  {k}")
print(f"  軸のもとになっている関係: {len(verbs)} 個")
unused = [r for r in R if r not in verbs and r not in ("relation", "from_to")]
print(f"  軸になっていない関係: {len(unused)} 個")
