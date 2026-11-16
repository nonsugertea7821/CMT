"""語彙の全体を書き直す試み（spec/trial/full3.yaml）の検査と集計。"""
import collections
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
P = yaml.safe_load((ROOT / "spec" / "trial" / "full3.yaml").read_text(encoding="utf-8"))
B, N = P["base"], P["nodes"]
TOPS = ("continuant", "occurrent")
errors = []
err = errors.append


def end(nid, side):
    """動詞の端の種類。自分になければ上位の動詞から受け継ぐ。"""
    hops = 0
    while nid in N and hops < 50:
        if side in N[nid]:
            return N[nid][side]
        nid, hops = N[nid].get("is"), hops + 1
    return None


def is_verb(nid):
    return nid in N and end(nid, "from") is not None and end(nid, "to") is not None


def spot_type(verb, pos):
    """動詞のある位置に来るものの種類。"""
    return end(verb, "new_kind") or "any" if pos == "new" else end(verb, pos)


def parent(nid):
    n = N[nid]
    if "is" in n:
        return n["is"]
    if "form" in n:
        return spot_type(*n["form"])
    return None


def is_a(x, y):
    if y == "any":
        return True
    hops = 0
    while x is not None and x != "any" and hops < 80:
        if x == y:
            return True
        x, hops = parent(x), hops + 1
    return False


def overlaps(x, y):
    return x == "any" or is_a(x, y) or is_a(y, x)


def top(nid):
    hops = 0
    while parent(nid) not in (None, "any") and hops < 80:
        nid, hops = parent(nid), hops + 1
    return nid


def check_spot(spec, where):
    if not (isinstance(spec, list) and len(spec) == 2):
        return err(f"{where}: of / form は [動詞, 位置] で書く")
    verb, pos = spec
    if not is_verb(verb):
        return err(f"{where}: {verb} は動詞でない")
    if pos not in ("from", "to", "new"):
        return err(f"{where}: 位置 {pos} は from / to / new")
    return verb, pos


def check_state(vid, n):
    static = "holds" in n
    if static == ("before" in n or "after" in n):
        err(f"{vid}: 静的（holds）か動的（before / after）のどちらかで書く")
    for key in ("holds", "before", "after"):
        for f in n.get(key, []):
            m = re.fullmatch(r"(not )?(\w+)\((\w+)(?:, (\w+))?\)", f)
            args = [a for a in m.groups()[2:] if a] if m else []
            if not m or m.group(2) not in B or len(args) != B[m.group(2)]["arity"] or any(a not in ("from", "to", "new") for a in args):
                err(f"{vid}: 式 {f} が基礎の関係に合わない")


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
    extra = set(n) - {"ja", "is", "from", "to", "new_kind", "holds", "before", "after", "form", "of", "neg", "mod", "issue"}
    if extra:
        err(f"{nid}: 知らない項目 {extra}")
    for side in ("from", "to", "new_kind"):
        if side in n and n[side] != "any" and n[side] not in N:
            err(f"{nid}: {side} の {n[side]} が未定義")
    if "form" in n:
        check_spot(n["form"], nid)
        continue
    if n.get("is") not in N:
        err(f"{nid}: 上位がない、または未定義")
        continue
    if is_verb(nid):
        if not is_a(nid, "occurrent"):
            err(f"{nid}: 動詞は生起体の下に置く")
        if is_verb(n["is"]):                                  # 動詞の下位: 端を狭めること
            for side in ("from", "to"):
                if side in n and not is_a(n[side], end(n["is"], side)):
                    err(f"{nid}: {side} の {n[side]} は、上位の {end(n['is'], side)} を狭めていない")
            if not any(k in n for k in ("from", "to", "mod")) and "issue" not in n:
                err(f"{nid}: 上位の動詞と区別する式がない")
        else:
            check_state(nid, n)
    elif "of" in n:
        check_spot(n["of"], nid)
        if not is_a(nid, "specifically_dependent_continuant"):
            err(f"{nid}: 修飾語は特定依存持続体の下に置く")
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
        verb, pos = spot
        if not overlaps(spot_type(verb, pos), n["is"]) and not overlaps(n["is"], spot_type(verb, pos)):
            err(f"{where}: {n['is']} は {verb} の {pos}（{spot_type(verb, pos)}）に来られない")
        if "with" in m:
            other = {"from": "to", "to": "from"}.get(pos)
            if other is None:
                err(f"{where}: 位置 new には with を付けられない")
            elif m["with"] not in N or not overlaps(m["with"], end(verb, other)):
                err(f"{where}: {m['with']} は {verb} の {other}（{end(verb, other)}）に来られない")
        if set(m) - {"of", "with", "neg", "quant"}:
            err(f"{where}: 知らない項目")
    if not ("holds" in n or "before" in n):
        key = yaml.safe_dump({k: n[k] for k in ("is", "from", "to", "of", "mod", "neg") if k in n}, sort_keys=True)
        if key in forms and "issue" not in n:
            err(f"{nid}: 式が {forms[key]} と同じ")
        forms.setdefault(key, nid)

# 動詞の式（状態の関係・両端・第三のものの種類）の重複
sig = collections.defaultdict(list)
for nid, n in N.items():
    if "holds" in n or "before" in n:
        s = tuple(tuple(sorted(n.get(k, []))) for k in ("holds", "before", "after")) + (n["from"], n["to"], n.get("new_kind"))
        sig[s].append(nid)
for s, ids in sig.items():
    if len(ids) > 1:
        err(f"動詞の式が同じ: {ids}")

if errors:
    print(f"検査に失敗: {len(errors)} 件")
    for e in errors:
        print(" -", e)
    sys.exit(1)

kind, used = collections.Counter(), collections.Counter()
issues = []
for nid, n in N.items():
    if nid in TOPS:
        k = "最上位"
    elif "holds" in n:
        k = "動詞（静的）"
    elif "before" in n:
        k = "動詞（動的）"
    elif is_verb(nid):
        k = "動詞の下位（端を狭めたもの）"
    elif "form" in n:
        k = "形"
    elif "of" in n:
        k = "修飾語"
    else:
        k = f"修飾で書いた概念（{N[top(nid)]['ja']}の側）"
    kind[k] += 1
    if "issue" in n:
        issues.append((k, n["ja"], n["issue"]))
    for m in n.get("mod") or []:
        if isinstance(m, str):
            used["名前のある修飾語を当てる"] += 1
        else:
            used[f"位置 {m['of'][1]} を占める"] += 1
            for key, lab in (("with", "もう一方の端を固定する"), ("neg", "否定"), ("quant", "数量化")):
                if key in m:
                    used[lab] += 1
print(f"検査に成功: ノード {len(N)}、基礎の関係 {len(B)}")
for k, v in kind.most_common():
    print(f"{v:4d}  {k}")
print("修飾の内訳")
for k, v in used.most_common():
    print(f"{v:4d}  {k}")
n_concepts = len(N) - 2
print(f"\n無理がある、または内容が落ちたもの: {len(issues)} / {n_concepts}（{len(issues) / n_concepts:.0%}）")
if "--issues" in sys.argv:
    for k, ja, why in issues:
        print(f"  [{k}] {ja}: {why}")
