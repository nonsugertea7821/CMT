"""試し書き（spec/trial/pilot3.yaml）の検査と集計。"""
import collections
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
P = yaml.safe_load((ROOT / "spec" / "trial" / "pilot3.yaml").read_text(encoding="utf-8"))
N = P["nodes"]
TOPS = ("continuant", "occurrent")
errors = []
err = errors.append


def parent(nid):
    n = N[nid]
    if "is" in n:
        return n["is"]
    if "form" in n:                       # 形: その端の種類を上位とみなす
        return N[n["form"][0]][n["form"][1]]
    return None


def is_a(x, y):
    if y == "any":
        return True
    hops = 0
    while x is not None and x != "any" and hops < 50:
        if x == y:
            return True
        x, hops = parent(x), hops + 1
    return False


def overlaps(x, y):
    return is_a(x, y) or is_a(y, x)


def top(nid):
    while parent(nid) not in (None, "any"):
        nid = parent(nid)
    return nid


def is_relation(nid):
    return nid in N and "from" in N[nid] and "to" in N[nid]


def check_spot(spec, where):
    """[関係, 位置] が正しいか。"""
    if not (isinstance(spec, list) and len(spec) == 2):
        return err(f"{where}: of / form は [関係, 位置] で書く")
    rel, pos = spec
    if not is_relation(rel):
        return err(f"{where}: {rel} は関係でない")
    if pos not in ("from", "to"):
        return err(f"{where}: 位置 {pos} は from か to")
    return rel, pos


seen, forms = {}, {}
for nid, n in N.items():
    ja = n.get("ja")
    if not ja or ja in seen:
        err(f"{nid}: 表示語がない、または {seen.get(ja)} と重複")
    seen[ja] = nid
    if nid in TOPS:
        if set(n) != {"ja", "gloss"}:
            err(f"{nid}: 最上位は gloss だけを持つ")
        continue
    if "gloss" in n:
        err(f"{nid}: gloss を持てるのは最上位だけ")
    if is_relation(nid):
        for side in ("from", "to"):
            if n[side] != "any" and n[side] not in N:
                err(f"{nid}: {side} の {n[side]} が未定義")
        if not is_a(nid, "occurrent"):
            err(f"{nid}: 関係は生起体の下に置く")
        if "mod" not in n:
            continue
    if "form" in n:
        check_spot(n["form"], nid)
        continue
    if "is" not in n or n["is"] not in N:
        err(f"{nid}: 上位がない、または未定義")
        continue
    if "of" in n:                                             # 修飾語
        check_spot(n["of"], nid)
        if not is_a(nid, "specifically_dependent"):
            err(f"{nid}: 修飾語は特定依存持続体（質・実現可能体）の下に置く")
    elif not n.get("mod"):
        err(f"{nid}: 式がない")
    for i, m in enumerate(n.get("mod") or []):
        where = f"{nid}.mod[{i}]"
        if isinstance(m, str):
            if m not in N or "of" not in N[m]:
                err(f"{where}: {m} は修飾語でない")
            continue
        spot = check_spot(m.get("of"), where)
        if not spot:
            continue
        rel, pos = spot
        other = "to" if pos == "from" else "from"
        if not overlaps(n["is"], N[rel][pos]):
            err(f"{where}: {n['is']} は {rel} の {pos}（{N[rel][pos]}）に来られない")
        if "with" in m and (m["with"] not in N or not overlaps(m["with"], N[rel][other])):
            err(f"{where}: {m.get('with')} は {rel} の {other}（{N[rel][other]}）に来られない")
        if set(m) - {"of", "with", "neg", "quant"}:
            err(f"{where}: 知らない項目 {set(m) - {'of', 'with', 'neg', 'quant'}}")
    key = yaml.safe_dump({k: n[k] for k in ("is", "of", "mod", "neg") if k in n}, sort_keys=True)
    if key in forms:
        err(f"{nid}: 式が {forms[key]} と同じ")
    forms[key] = nid

if errors:
    print(f"検査に失敗: {len(errors)} 件")
    for e in errors:
        print(" -", e)
    sys.exit(1)

kind = collections.Counter()
used = collections.Counter()
for nid, n in N.items():
    if nid in TOPS:
        kind["最上位"] += 1
    elif is_relation(nid) and "mod" not in n:
        kind["関係（動詞の語根）"] += 1
    elif "form" in n:
        kind["形（-er / -ee）"] += 1
    elif "of" in n:
        kind["修飾語"] += 1
    else:
        kind[f"修飾で書いた概念（{N[top(nid)]['ja']}の側）"] += 1
    for m in n.get("mod") or []:
        if isinstance(m, str):
            used["名前のある修飾語を当てる"] += 1
        else:
            used[f"位置 {m['of'][1]} を占める"] += 1
            for k, lab in (("with", "相手の端を固定する"), ("neg", "否定"), ("quant", "数量化")):
                if k in m:
                    used[lab] += 1
print(f"検査に成功: ノード {len(N)}")
for k, v in kind.most_common():
    print(f"{v:4d}  {k}")
print("修飾の内訳")
for k, v in used.most_common():
    print(f"{v:4d}  {k}")
print(f"書けなかったもの、無理があったもの: {len(P['unresolved'])} 種類")
