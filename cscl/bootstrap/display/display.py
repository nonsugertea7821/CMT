"""体系の表示（自然言語）。正本は体系で、ここはその表示への変換。どの領域にも使える。

1行に1つの種類を書く:  表示名 ＝ 上位 ∧ 限定
限定は 動詞(始点, 終点) の形で、自分の位置を「これ」と書く。否定は ¬、量の条件は 相手<25 のように書く。
事実は 動詞(始点, 終点)。

T は型検査器が作る体系（type_checker.build() の最初の値）。individuals は個体の表（{識別子: {is, display}}）。
"""
OPS = {"lt": "<", "le": "≤", "gt": ">", "ge": "≥"}


def ja(T, x, individuals=None):
    """ノードか個体の表示名。なければ識別子のまま。"""
    if x in T.N:
        return T.N[x].get("display", x)
    return ((individuals or {}).get(x) or {}).get("display", x)


def val(v):
    if isinstance(v, dict):
        (op, a), = v.items()
        if op == "between":
            return f"{a[0]}〜{a[1]}"
        return f"{OPS[op]}{a}"
    return f"={v}"


def mod(T, m, individuals=None):
    verb, pos = m["of"]
    other = ja(T, m["with"], individuals) if "with" in m else "何か"
    for ax, v in (m.get("at") or {}).items():
        other += f"（{'個数' if ax == 'count' else '順番' if ax == 'order' else ''}{val(v)}）"
    if m.get("quant") == "all":
        other = "すべての" + other
    me = "これ"
    args = {"from": (me, other), "to": (other, me), "new": ("何か", "何か")}[pos]
    s = f"{ja(T, verb, individuals)}({args[0]}, {args[1]})"
    return ("¬" if m.get("neg") else "") + s


def mods(n):
    ms = n.get("mod") or []
    return ms if isinstance(ms, list) else [ms]


def line(T, nid, individuals=None):
    """種類の1行: 表示名 ＝ 上位 ∧ 限定。"""
    n, parts = T.N[nid], []
    if isinstance(n.get("extends"), str):
        parts.append(ja(T, n["extends"], individuals))
    for m in mods(n):
        parts.append(mod(T, m, individuals) if isinstance(m, dict) else ja(T, m, individuals))
    if "axis" in n:
        parts.append("量")
    return f"{n['display']} ＝ " + " ∧ ".join(parts)


def refs(T, nid):
    """種類の行が参照する語（上位、限定の動詞と相手、動詞の端）。"""
    n, out = T.N[nid], []
    if isinstance(n.get("extends"), str):
        out.append(n["extends"])
    for m in mods(n):
        if isinstance(m, dict):
            out += [m["with"]] if "with" in m else []
            out.append(m["of"][0])
    out += [n[k] for k in ("from", "to", "new_kind") if isinstance(n.get(k), str)]
    return out


def fact(T, verb, a, b, individuals=None):
    """事実の1行: 動詞(始点, 終点)。"""
    return f"{ja(T, verb, individuals)}({ja(T, a, individuals)}, {ja(T, b, individuals)})"


P1 = ("について", "から", "より", "に", "で", "と", "を", "へ")


def case_mark(vd):
    """動詞の表示語から、目的語に付ける印を決める（h_ja_case_frame の F の枠）。"""
    if vd.startswith(P1):
        return ""
    i = min((vd.find(p) for p in P1 if vd.find(p) > 0), default=-1)
    if i > 0 and ("一" <= vd[0] <= "鿿" or "゠" <= vd[0] <= "ヿ"):
        return "の"
    return "を"


def sentence(T, verb, a, b, individuals=None):
    """事実の文: 「Aが B〈印〉〈動詞〉」、種類の事実は「Aは Bの一種である」。読み戻しが一つに決まることは h_ja_roundtrip で確かめた。"""
    if verb == "is_a":
        return f"{ja(T, a, individuals)}は{ja(T, b, individuals)}の一種である"
    vd = ja(T, verb, individuals)
    return f"{ja(T, a, individuals)}が{ja(T, b, individuals)}{case_mark(vd)}{vd}"
