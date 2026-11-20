"""領域 exp に固有の検査。cscl.yaml の checkers に書かれ、型検査器が言語の検査のあとに呼ぶ（check）。
測定の族を結果ファイルから展開して測定値を得、観察・仮説・決定の中身を確かめる。主張（仮説・決定）を置くほかの領域（lang）の主張も、ここで確かめる。
型検査器（cscl/bootstrap/type_checker）には、exp の語を書かない。

  測定値: 族ごとに、軸（axis）の直積で展開する。識別子は「族.軸の値....指標」。値は結果ファイル（cscl.yaml の results）から計算する。
  観察・仮説・決定: どれも「s が、p という関係で、o に」という文。
    観察の s と o は測定値（o は数でもよい）、p は大きさを比べる動詞。真偽は、動詞の式（後ろにある、の成立と不成立）を
    数に当てはめて決める。すべて真でなければ検査は失敗する。
    仮説と決定の s と o はノード、p は動詞。s は p の始点、o は p の終点に来られるものでなければならない。
    仮説の status は、根拠（evidence, against）の有無から決まる。決まり方は、状態のノードの式から読み取る。
    決定の p が is_a のときは、体系の上位・下位の関係そのもの。採用済みなら、検査が構造から確かめる。

使い方:
  python exp/src/exp_check.py              検査（言語の検査を含む）
  python exp/src/exp_check.py --values     測定値をすべて表示
  python exp/src/exp_check.py --show ID    1つの項目を、参照を展開して表示
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cscl/bootstrap/type_checker"))
import yaml  # noqa: E402
import type_checker as tc  # noqa: E402
from type_checker import *  # noqa: E402,F401,F403
from type_checker import err, errors, LAYERS  # noqa: E402,F401

RESULTS = ROOT / yaml.safe_load((ROOT / "cscl.yaml").read_text(encoding="utf-8"))["results"]
_cache = {}

KINDS = {"measurement_family": "families", "observation": "observations", "hypothesis": "hypotheses",
         "decision": "decisions", "backlog_item": "backlog"}   # この検査が中身を確かめる種類



def axes_of(I, T):
    """測定の族の軸と軸の値（個体）を、族ごとの形に並べる。expand が読む形:
    axis: {軸の字: [値の字] | {値の字: 書き方}}、meaning: {軸の字: {値の字: 指すもの | {identifier, value}}}。
    並びは、個体を書いた順。"""
    kind = lambda x: x.get("is")
    for aid, a in I.items():
        if not T.is_a(kind(a), "family_axis"):
            continue
        fam = I.get(a.get("measurement_family"))
        if fam is None or not T.is_a(kind(fam), "measurement_family"):
            err(f"exp {aid}: 測定の族の軸が、どの族の部分でもない")
            continue
        if "pattern" in a:
            fam["row_keys"] = {"axis": label(a), "pattern": a["pattern"]}
        vals = [(vid, v) for vid, v in I.items() if T.is_a(kind(v), "axis_value") and v.get("family_axis") == aid]
        if not vals:
            err(f"exp {aid}: 測定の族の軸に、値がない")
        label = lambda x: (x.get("val") or {}).get("text")
        al = label(a)
        if any("passage" in v for _, v in vals):
            fam.setdefault("axis", {})[al] = {label(v): v.get("passage", label(v)) for _, v in vals}
        else:
            fam.setdefault("axis", {})[al] = [label(v) for _, v in vals]
        for vid, v in vals:
            ids, at = v.get("any", []), v.get("_at", [])
            if isinstance(ids, str):
                ids = [ids]
            if ids or at:
                m = ids[0] if len(ids) == 1 and not at else {"identifier": ids} | ({"value": at} if at else {})
                fam.setdefault("meaning", {}).setdefault(al, {})[label(v)] = m



def sections(name, D, T):
    """領域の個体を、この検査が中身を確かめる種類ごとに分ける。仮説・決定・残り項目は、状態を表す下位の種類に属する。
    個体の形・種類・値・項目の数は、型検査器が確かめてある。"""
    axes_of(D["individuals"], T)
    out = {sect: {} for sect in KINDS.values()}
    for iid, x in D["individuals"].items():
        x = dict(x)
        kind = x.pop("is", None)
        if kind not in T.N:
            continue
        base = [k for k in KINDS if T.is_a(kind, k)]
        if not base:
            continue
        if base[0] in ("hypothesis", "decision", "backlog_item"):
            x["status"] = kind
        if "new" in x:   # 文の動詞が新しく取る位置（v_near の許容幅）
            x["tolerance"] = x.pop("new")
        out[KINDS[base[0]]][iid] = x
    out["backlog"] = [{"identifier": k, **v} for k, v in out["backlog"].items()]
    return {"families": out.pop("families")}, out


# ---------------------------------------------------------------- 規則

def rows_of(file, at):
    key = (file, tuple(at))
    if key not in _cache:
        d = json.loads((RESULTS / file).read_text(encoding="utf-8"))
        for k in at:
            d = d[k]
        _cache[key] = list(d.items()) if isinstance(d, dict) else [(str(i), r) for i, r in enumerate(d)]
    return _cache[key]


def stat(rows, cond, name):
    vals = [r[cond] for _, r in rows if cond in r]
    if not vals:
        raise KeyError(f"条件 {cond} の行がない")
    # 選択肢の順序ごとの値を並べた形（[順序1, 順序2]）は、平均と「両方とも正」に直す
    vals = [{"margin": sum(v) / len(v), "both": all(x > 0 for x in v)} if isinstance(v, list) else v for v in vals]
    n = len(vals)
    if name == "accuracy":
        return sum(v["margin"] > 0 for v in vals) / n, n
    if name == "order_robust_accuracy":
        return sum(bool(v["both"]) for v in vals) / n, n
    if name == "logit_margin":
        return sum(v["margin"] for v in vals) / n, n
    if name == "judged_accuracy":
        rs = [r for _, r in rows if cond in r]
        return sum(r[cond]["judged"] == r["correct"] for r in rs) / n, n
    if name == "mean_value":
        return sum(vals) / n, n
    raise KeyError(f"指標 {name} の計算方法が、検査ツールにない")


def check_meaning(val, T, where):
    if isinstance(val, str):
        if val not in T.N and val not in T.I:
            err(f"{where}: ノード {val} が未定義")
        return
    for nid in val.get("identifier", []):
        if nid not in T.N:
            err(f"{where}: ノード {nid} が未定義")
    for v in val.get("value", []):
        if v.get("s") not in T.N:
            err(f"{where}: 値の s {v.get('s')} が未定義")
        T.check_value(v.get("axis"), v.get("o"), where)


def expand(M, T):
    values, meanings = {}, {}
    for fid, f in M["families"].items():
        for st in f["metric"]:
            if st not in T.N or not (T.is_a(st, "metric") or T.is_a(st, "magnitude")):
                err(f"measurements.{fid}: 指標 {st} は、体系の指標でも大きさでもない")
        axes = f["axis"]
        names = list(axes)
        keys = [list(axes[a]) if isinstance(axes[a], dict) else axes[a] for a in names]
        for a, mp in (f.get("meaning") or {}).items():
            for k, v in mp.items():
                check_meaning(v, T, f"measurements.{fid}.meaning.{a}.{k}")
        for combo in itertools.product(*keys):
            b = dict(zip(names, combo))
            sub = {a: (axes[a][b[a]] if isinstance(axes[a], dict) else b[a]) for a in names}
            fmt = lambda x: x.format(**{k: v for k, v in sub.items() if not isinstance(v, list)}) if isinstance(x, str) else x
            try:
                rows = rows_of(fmt(f["result_file"]), [fmt(x) for x in f.get("row_collection", [])])
            except (FileNotFoundError, KeyError) as e:
                err(f"measurements.{fid}: {b} のファイルまたは位置が見つからない: {e}")
                continue
            for field, want in (f.get("row_filter") or {}).items():
                want = sub[want[1:-1]] if isinstance(want, str) and want[1:-1] in sub and isinstance(sub[want[1:-1]], list) else fmt(want)
                ok = (lambda x, w=want: x in w) if isinstance(want, list) else (lambda x, w=want: x == w)
                rows = [(k, r) for k, r in rows if ok(r.get(field))]
            if "row_keys" in f:
                axis = f["row_keys"]["axis"]
                allowed = {fmt(f["row_keys"]["pattern"]).replace("#", str(x)) for x in sub[axis]}
                rows = [(k, r) for k, r in rows if k in allowed]
            for st in f["metric"]:
                mid = ".".join([fid] + [str(b[a]) for a in names] + [short(st)])
                try:
                    values[mid] = stat(rows, fmt(f["condition_entry"]), short(st))
                except KeyError as e:
                    err(f"measurements: {mid}: {e}")
                meanings[mid] = {a: (f.get("meaning") or {}).get(a, {}).get(b[a], b[a]) for a in names} | {"metric": st}
    return values, meanings


# ---------------------------------------------------------------- 観察・仮説・決定
def check_claims(C, values, T):
    # 観察: 測定値どうし（または測定値と数）を、大きさを比べる動詞で結んだ文。すべて真であること
    obs = C["observations"]
    gap = {}   # 大小を述べる観察について、2つの値の差を問数に直したもの
    for oid, o in obs.items():
        vals = []
        for side in ("s", "o"):
            x = o[side]
            if isinstance(x, (int, float)) and side == "o":
                vals.append(float(x))
            elif isinstance(x, str) and x in values:
                vals.append(values[x][0])
            else:
                err(f"{oid}: {side} の {x} は、測定値でない")
        if len(vals) < 2:
            continue
        if not T.is_verb(o["p"]):
            err(f"{oid}: p の {o['p']} は動詞でない")
            continue
        near = short(T.end(o["p"], "new_kind")) == "tolerance"
        if near != ("tolerance" in o):
            err(f"{oid}: 許容幅は、動詞 {o['p']} の第三のものが許容幅であるときにだけ、必ず書く")
            continue
        holds = T.compare(o["p"], vals[0], vals[1], o["tolerance"] + 1e-9 if near else 1e-6)
        if holds is None:
            err(f"{oid}: 動詞 {o['p']} は、大きさを比べる動詞（「後ろにある」だけで書かれた静的な動詞）でない")
        elif not holds:
            err(f"observations: {oid} が成り立たない（{T.N[o['p']]['display']}: s={vals[0]:.3f}, o={vals[1]:.3f}）")
        ns = [values[x][1] for x in (o["s"], o["o"]) if isinstance(x, str) and x in values]
        gap[oid] = abs(vals[0] - vals[1]) * min(ns) if T.is_strict(o["p"]) else None

    hyps, decs = C["hypotheses"], C["decisions"]

    def triple(x, where, structural_ok=False):
        if any(k not in x for k in ("s", "p", "o")):
            return err(f"{where}: 中身（v_refer で述べる文）がない")
        ss = x["s"] if isinstance(x["s"], list) else [x["s"]]
        oo = x["o"] if isinstance(x["o"], list) else [x["o"]]
        for t in ss + oo:
            if t not in T.N and t not in T.I:
                err(f"{where}: ノード {t} が未定義")
                return
        if x["p"] == "is_a":
            if not structural_ok:
                err(f"{where}: is_a を使えるのは決定だけ")
            elif T.is_a(x.get("status"), "dec_adopted") and not all(T.is_a(a, b) for a in ss for b in oo):
                err(f"{where}: 採用済みの決定だが、体系の上で {ss} は {oo} の下位になっていない")
            return
        if not T.is_verb(x["p"]):
            return err(f"{where}: {x['p']} は動詞でない")
        for side, ts in (("from", ss), ("to", oo)):
            bound = T.end(x["p"], side)
            for t in ts:
                if not T.overlaps(t, bound):
                    err(f"{where}: {t} は動詞 {x['p']} の {side}（{bound}）に来られない")

    patterns = {k: status_pattern(T, k) for k in T.kinds_of("hypothesis")}
    patterns = {k: v for k, v in patterns.items() if v}
    for hid, h in hyps.items():
        triple(h, hid)
        have = {"evidence": bool(h.get("evidence")), "against": bool(h.get("against"))}
        want = [k for k, v in patterns.items() if v == have]
        if T.is_a(h["status"], "withdrawn_sentence"):
            pass
        elif short(h["status"]) not in {short(k) for k in patterns}:
            err(f"{hid}: 種類 {h["status"]} は、仮説の状態のノードでない")
        elif want != [h["status"]]:
            err(f"{hid}: 種類は {h["status"]} と書かれているが、根拠の有無からは {want} になる")
        for t in h.get("scope", []):
            if t not in T.N and t not in T.I:
                err(f"{hid}: scope のノード {t} が未定義")
        for k in ("evidence", "against"):
            for r in h.get(k, []):
                if r not in obs:
                    err(f"{hid}: {k} の観察 {r} が未定義")
        for lim in h.get("limitation", []):
            if lim not in T.kinds_of("limitation"):
                err(f"{hid}: 留保 {lim} は、留保のノードでない")
        if "lim_one_item" in [short(x) for x in h.get("limitation", [])]:
            gs = [gap.get(r) for r in h.get("evidence", []) + h.get("against", [])]
            if not any(g is not None and g <= 1.0 + 1e-6 for g in gs):
                err(f"{hid}: 留保「差が1問以内」と書かれているが、根拠のうち大小を述べる観察に、差が1問以内のものがない")
        for r in h.get("supersedes", []):
            if r not in hyps:
                err(f"{hid}: supersedes の仮説 {r} が未定義")
    for did, d in decs.items():
        if d["status"] not in T.kinds_of("decision"):
            err(f"{did}: status の {d['status']} は、決定の状態のノードでない")
        triple(d, did, structural_ok=True)
        for r in d.get("basis", []):
            if r not in hyps:
                err(f"{did}: basis の仮説 {r} が未定義")
        for r in d.get("supersedes", []):
            if r not in decs:
                err(f"{did}: supersedes の決定 {r} が未定義")
    for b in C["backlog"]:
        if b["status"] not in T.kinds_of("backlog_item"):
            err(f"backlog {b['identifier']}: status の {b['status']} は、残り項目の状態のノードでない")
        for r in b.get("tests", []):
            if r not in hyps:
                err(f"backlog {b['identifier']}: tests の仮説 {r} が未定義")



CLAIM_DOMAINS = {"lang"}   # exp のほかに、仮説・決定を置く領域（言語そのものについての主張）


def check_sides(C, T):
    """主張がどちらの側のものかを、中身が参照する語で確かめる。
    lang の主張は、言語の層（signature, ontology, syntax, runtime, std）と lang の語だけを参照する。exp の主張は、exp か subj の語（動詞を含む）を少なくとも1つ参照する。"""
    def words(x):
        out = []
        for k in ("s", "o", "p"):
            v = x.get(k)
            out += v if isinstance(v, list) else [v]
        return [w for w in out if isinstance(w, str) and w != "is_a"]

    def dom(w):
        if w in T.Isubj:
            return T.Isubj[w]
        if w in T.I:
            return T.Idom if w not in (T.O.get("individuals") or {}) else "signature"
        return T.domain(w)
    for sect in ("hypotheses", "decisions"):
        for i, x in C[sect].items():
            side, ds = C["side"].get(i), {dom(w) for w in words(x)}
            if side in CLAIM_DOMAINS and ds - set(LAYERS) - {side}:
                err(f"{i}: {side} の主張が、{side} と言語の層以外の語を参照している（{sorted(ds - set(LAYERS) - {side})}）")
            if side == "exp" and ds and ds <= set(LAYERS):
                err(f"{i}: exp の主張が、signature の語だけを参照している。言語についての主張なら cscl の側に置く")


def status_pattern(T, nid):
    """状態のノードの式から、「支持する観察がある / 反する観察がある」の組を読み取る。"""
    pat = {}
    for m in [m for x in [nid] + T.ancestors(nid) for m in (T.N[x].get("mod") or [])]:
        if isinstance(m, dict) and m.get("of") == ["syntax.v_agree", "to"] and short(m.get("with")) in ("evidence", "against"):
            pat[short(m["with"])] = not m.get("neg")
    return pat if set(pat) == {"evidence", "against"} else None


def check(T, O, Dm):
    """型検査器が呼ぶ。測定値を展開し、観察・仮説・決定を確かめる。結果の要約（1行）を返す。"""
    T.Idom = "exp"
    name, D = Dm["exp"]
    M, C = sections(name, D, T)
    C["side"] = {i: "exp" for sect in ("hypotheses", "decisions") for i in C[sect]}
    for dom in CLAIM_DOMAINS & set(Dm):
        n2, X = Dm[dom]
        _, C2 = sections(n2, X, T)
        for sect in ("hypotheses", "decisions", "observations"):
            for i, x in C2[sect].items():
                C[sect][i] = x
                if sect != "observations":
                    C["side"][i] = dom
        C["backlog"] += C2["backlog"]
    check_sides(C, T)
    values, meanings = expand(M, T)
    check_claims(C, values, T)
    _last.update(M=M, C=C, values=values, meanings=meanings)
    return f"測定値 {len(values)}、観察 {len(C['observations'])}、仮説 {len(C['hypotheses'])}、決定 {len(C['decisions'])}、残り項目 {len(C['backlog'])}"


_last = {}


def build():
    """体系を読み、言語の検査と exp の検査をする。(体系, ontology, 領域 subj, 測定の族, 文) を返す（呼び出し側の互換）。"""
    T, O, Dm = tc.build()
    check(T, O, Dm)
    S = Dm.get("subj", (None, {"individuals": {}, "facts": [], "_local": set()}))[1]
    return T, O, S, _last["M"], _last["C"]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--values", action="store_true")
    ap.add_argument("--show")
    args = ap.parse_args()
    T, O, S, M, C = build()
    values, meanings = _last["values"], _last["meanings"]
    if args.values:
        for mid, (v, n) in sorted(values.items()):
            print(f"{mid} = {v:.2f} (n={n})")
    if args.show:
        for sect in ("observations", "hypotheses", "decisions"):
            if args.show in C[sect]:
                x = C[sect][args.show]
                print(yaml.safe_dump({args.show: x}, allow_unicode=True, sort_keys=False))
                for k in ("s", "o"):
                    if isinstance(x.get(k), str) and x[k] in values:
                        v, n = values[x[k]]
                        print(f"{x[k]} = {v:.2f} (n={n})  {meanings[x[k]]}")
        if args.show in values:
            print(values[args.show], meanings[args.show])
    if errors:
        print(f"検査に失敗: {len(errors)} 件")
        for e in errors:
            print(" -", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
