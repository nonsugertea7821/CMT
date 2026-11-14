"""動詞の語根の試験（spec/trial/verb_roots.yaml）。表示語を見ずに、式だけで語根を区別できるかを数える。"""
import collections
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
D = yaml.safe_load((ROOT / "spec" / "trial" / "verb_roots.yaml").read_text(encoding="utf-8"))
B, V = D["base_relations"], D["roots"]
errors = []
for vid, v in V.items():
    for key in ("holds", "before", "after"):
        for f in v.get(key, []):
            m = re.fullmatch(r"(not )?(\w+)\((\w+)(?:, (\w+))?\)", f)
            if not m:
                errors.append(f"{vid}: 式 {f} が読めない")
                continue
            rel, args = m.group(2), [a for a in m.groups()[2:] if a]
            if rel not in B or len(args) != B[rel]["arity"] or any(a not in ("from", "to", "new") for a in args):
                errors.append(f"{vid}: 式 {f} が基礎の関係に合わない")
    if ("holds" in v) == ("before" in v or "after" in v):
        errors.append(f"{vid}: 静的（holds）か動的（before / after）のどちらかで書く")
if errors:
    print("\n".join(errors))
    sys.exit(1)


def signature(v, level):
    """level 1: 状態の関係だけ / 2: + 両端の種類 / 3: + 終点や第三のものの種類"""
    sig = [tuple(sorted(v.get(k, []))) for k in ("holds", "before", "after")]
    if level >= 2:
        sig.append(tuple(v["ends"]))
    if level >= 3:
        sig.append((v.get("to_kind"), v.get("new_kind")))
    return tuple(sig)


print(f"語根 {len(V)} 個（静的 {sum('holds' in v for v in V.values())}、動的 {sum('holds' not in v for v in V.values())}）")
use = collections.Counter(re.search(r"(\w+)\(", f).group(1) for v in V.values() for k in ("holds", "before", "after") for f in v.get(k, []))
print("基礎の関係の使用回数: " + "、".join(f"{B[k]['ja']} {n}" for k, n in use.most_common()))
print(f"第三のもの（new）を使う語根: {sum(any('new' in f for k in ('holds', 'before', 'after') for f in v.get(k, [])) for v in V.values())}")
for level, name in ((1, "状態の関係だけ"), (2, "＋両端の種類"), (3, "＋終点・第三のものの種類")):
    groups = collections.defaultdict(list)
    for vid, v in V.items():
        groups[signature(v, level)].append(v["ja"])
    clash = [g for g in groups.values() if len(g) > 1]
    print(f"\n[{name}] 区別できる式 {len(groups)} 種類 / 語根 {len(V)} 個")
    for g in clash:
        print("   区別できない組: " + "、".join(g))
