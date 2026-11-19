"""h_factor_depends_value を確かめる: 仮説の要因と比べの条件は、事実として置いた橋 依る(要因, 軸の値) で結べるか。

仮説（exp.yaml）: v_depend(factor, axis_value)。登録（ce656df）の読み: #244 で h_denote_meets_hypothesis が反証された。
  解き方を対で出した。橋は定義にすでにある（h_definition_bridges_value）は反証された（#246 の記録: 両側が空でない
  結び 118 のうち、定義の閉包でも会わない 37）。もう一方: 橋を事実として置く。要因が軸の値に依る（v_depend）。

手順（結び・比べで違う軸の値 diff・表すもの・広げ E1・E* は sys_definition_bridges_value.py と同じ。その関数の本体を写して使い、
     その main は走らせない。記録済みの結果ファイルは書き換えない）:
  会わない結び: 両側の E1 が空でなく、E* でも会わない結び（今の main で数え直す）。
  橋の候補: 会わない結び (o, h) ごとに、仮説の側 E1 の名のうち、上位（extends）をたどって factor に届くもの f と、
            diff の軸の値 v の組 (f, v)。f か v がなければ、その結びは橋を置けない。
  変種 B: 写しの exp.yaml の facts の末尾に、橋の候補をすべて {is: v_depend, from: f, to: v} として足す。
  測るもの: n_miss（会わない結び）、n_unbridgeable（橋を置けない結び）、n_bridge_facts（足した事実の数、重複を除く）、
            share（n_bridge_facts / 橋を置けた結びの数）、B_errors（tc の誤り）、B_ec_errors（ec の誤り）、L_errors、L_ec_errors。
  行（sys_factor_depends_value.json）: "link 観察 仮説": {bridgeable, n_factor, n_value}, "summary 要約": {...}
判定（事前に決める）:
  L_errors か L_ec_errors が 0 でなければ外れ（状態は変えない）。
  n_unbridgeable = 0、B_errors = 0、B_ec_errors = 0 なら支持。どれかが満たされなければ反証。

開示（結果を見る前に分かっていること）:
  - #246 の記録で、会わない結びは 37。今の main では数が変わりうる。
  - v_depend の to は continuant。軸の値（axis_value、value を上位に持つ）が来られるかは確かめていない。
  - 橋は、結びごとに機械的に作る。橋が結びの宣言を写しただけか（共有されるか）は share で見るが、判定には使わない。
  - 型検査と ec は 2 回ずつ走る。
使い方:
  python exp/experiments/sys_factor_depends_value.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_factor_depends_value.json"


def yaml_files():
    c = yaml.safe_load((ROOT / "cscl.yaml").read_text(encoding="utf-8"))
    pats = [c["root"]] + c.get("library", []) + c.get("include", [])
    return [p for g in pats for p in sorted(ROOT.glob(g))]


def short(x):
    return str(x).split(".")[-1]


def strings(x):
    if isinstance(x, str):
        return [x]
    if isinstance(x, list):
        return [s for y in x for s in strings(y)]
    return []


def formula_names(F):
    out = []
    if isinstance(F, dict):
        for k, v in F.items():
            if k != "is":
                out += formula_names(v)
    elif isinstance(F, list):
        for y in F:
            out += formula_names(y)
    elif isinstance(F, str):
        out.append(short(F))
    return out


def links_and_misses():
    ents, facts = {}, []
    for p in yaml_files():
        D = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for sec in ("nodes", "individuals"):
            for k, v in (D.get(sec) or {}).items():
                if isinstance(v, dict):
                    ents[k] = v
        facts += [f for f in D.get("facts") or [] if isinstance(f, dict)]
    kind = {k: short(v.get("is", "")) for k, v in ents.items()}
    fams = {k for k, t in kind.items() if t == "measurement_family"}
    axis_fam = {f["from"]: f["to"] for f in facts if short(f.get("is")) == "v_axis_of"
                and kind.get(f.get("from")) == "family_axis" and f.get("to") in fams}
    spell = {}
    for f in facts:
        if short(f.get("is")) == "v_value_of" and kind.get(f.get("from")) == "axis_value" and f.get("to") in axis_fam:
            t = (ents[f["from"]].get("val") or {}).get("text")
            if t is not None:
                spell.setdefault(axis_fam[f["to"]], {}).setdefault(str(t), set()).add(f["from"])
    den = {}
    for f in facts:
        vb = short(f.get("is"))
        if vb == "v_denote" and kind.get(f.get("from")) == "axis_value":
            den.setdefault(f["from"], set()).update(short(x) for x in strings(f.get("to")))
        if vb == "v_compose" and kind.get(f.get("to")) == "axis_value":
            den.setdefault(f["to"], set()).update(short(x) for x in strings(f.get("from")))

    def E(x):
        out = {x}
        d = ents.get(x)
        if isinstance(d, dict):
            mods = d.get("mod") or []
            for m in mods if isinstance(mods, list) else [mods]:
                if isinstance(m, dict):
                    out.update(short(w) for w in strings(m.get("with")))
        return out

    def withs(m):
        out = []
        if isinstance(m, list):
            for y in m:
                out += withs(y)
        elif isinstance(m, dict):
            out += [short(w) for w in strings(m.get("with"))]
            out += withs(m.get("mod"))
        return out

    def Estar(x):
        seen, todo = {x}, [x]
        while todo:
            d = ents.get(todo.pop())
            if not isinstance(d, dict):
                continue
            nxt = withs(d.get("mod"))
            if "extends" not in d and isinstance(d.get("is"), str):
                nxt.append(short(d["is"]))
            for y in nxt:
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return seen

    obs_cells, hyp_f = {}, {}
    for f in facts:
        if short(f.get("is")) != "v_refer" or not isinstance(f.get("to"), dict):
            continue
        s, F = str(f.get("from", "")), f["to"]
        if s.startswith("h_"):
            hyp_f.setdefault(s, []).append(F)
        if s.startswith("o_"):
            for w in strings(F.get("from")) + strings(F.get("to")) + strings(F.get("new")):
                parts = w.split(".")
                if len(parts) < 2 or parts[0] not in fams:
                    continue
                vals = frozenset(v for seg in parts[1:-1] for v in spell.get(parts[0], {}).get(seg, ()))
                obs_cells.setdefault(s, {})[".".join(parts[:-1])] = vals
    links = [(f["from"], f["to"]) for f in facts if short(f.get("is")) in ("v_support", "v_contradict")
             and str(f.get("from", "")).startswith("o_") and str(f.get("to", "")).startswith("h_")]
    rows, misses = {}, []
    for o, h in links:
        cells = list(obs_cells.get(o, {}).values())
        if len(cells) > 1:
            diff = set().union(*cells) - set.intersection(*[set(c) for c in cells])
        else:
            diff = set(cells[0]) if cells else set()
        dv = [x for v in diff for x in den.get(v, ())]
        hv = [x for F in hyp_f.get(h, []) for x in formula_names(F)]
        o1 = set().union(*[E(x) for x in dv]) if dv else set()
        h1 = set().union(*[E(x) for x in hv]) if hv else set()
        os_ = set().union(*[Estar(x) for x in dv]) if dv else set()
        hs = set().union(*[Estar(x) for x in hv]) if hv else set()
        rows[f"link {o} {h}"] = {"meets1": int(bool(o1 & h1)), "meets_star": int(bool(os_ & hs)),
                                 "empty_side1": int(not o1 or not h1), "empty_side_star": int(not os_ or not hs)}
        if not o1 or not h1 or (o1 & h1):
            continue
        misses.append({"obs": o, "hyp": h, "meets_star": int(bool(os_ & hs)), "diff": sorted(diff), "h1": sorted(h1)})
    return rows, misses, ents, links, obs_cells, hyp_f, E, den


def reaches_factor(ents, x):
    seen = set()
    while x and x not in seen:
        seen.add(x)
        if x == "factor":
            return True
        d = ents.get(x)
        if not isinstance(d, dict):
            return False
        x = short(d.get("extends") or "")
    return False


def check(d):
    r1 = subprocess.run([sys.executable, "cscl/bootstrap/type_checker/type_checker.py"], cwd=d, capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, "exp/src/exp_check.py"], cwd=d, capture_output=True, text=True)
    def n(r):
        ls = [l for l in (r.stdout + r.stderr).split("\n") if l.startswith(" - ")]
        return (len(ls) if r.returncode else 0), ls[:8]
    (e1, t1), (e2, t2) = n(r1), n(r2)
    return {"errors": e1, "ec_errors": e2, "rc": r1.returncode, "ec_rc": r2.returncode, "err_text": t1 + t2}


def main():
    spec = importlib.util.spec_from_file_location("unhardcode", ROOT / "exp/experiments/sys_rule_verbs_unhardcode.py")
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    rows0, misses, ents, *_ = links_and_misses()
    miss = [m for m in misses if not m["meets_star"]]
    rows, bridges = {}, set()
    for m in miss:
        fs = [x for x in m["h1"] if reaches_factor(ents, x)]
        vs = m["diff"]
        ok = int(bool(fs) and bool(vs))
        if ok:
            bridges.update((f, v) for f in fs for v in vs)
        rows[f"link {m['obs']} {m['hyp']}"] = {"bridgeable": ok, "n_factor": len(fs), "n_value": len(vs)}
    res = {}
    for k in ("L", "B"):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            B.copy_tree(d)
            if k == "B":
                p = d / "exp/src/exp.yaml"
                txt = p.read_text(encoding="utf-8").rstrip("\n") + "\n"
                txt += "".join(f"  - {{is: v_depend, from: {f}, to: {v}}}\n" for f, v in sorted(bridges))
                p.write_text(txt, encoding="utf-8")
            res[k] = check(d)
    nb = sum(r["bridgeable"] for r in rows.values())
    s = {"n_miss": len(miss), "n_unbridgeable": len(miss) - nb, "n_bridge_facts": len(bridges),
         "share": round(len(bridges) / nb, 3) if nb else -1,
         "L_errors": res["L"]["errors"], "L_ec_errors": res["L"]["ec_errors"],
         "B_errors": res["B"]["errors"], "B_ec_errors": res["B"]["ec_errors"]}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows, "variants": res, "bridges": sorted(bridges)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False)[:1500])
    print(json.dumps(s, ensure_ascii=False))
    valid = s["L_errors"] == 0 and s["L_ec_errors"] == 0
    sup = s["n_unbridgeable"] == 0 and s["B_errors"] == 0 and s["B_ec_errors"] == 0
    print("判定:", "外れ" if not valid else ("支持" if sup else "反証"))


if __name__ == "__main__":
    main()
