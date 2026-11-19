"""h_definition_bridges_value を確かめる: 仮説の要因と比べの条件の表すものは、定義をたどれば会うか。

仮説（exp.yaml）: 依る(要因, 定義)。#244 で h_denote_meets_hypothesis が反証された（結び 159 のうち会わない 92、
  うち片側が空 53）。広げを mod の with の1段に限っていた。登録の commit（ce656df）の読み: 名の mod と個体の is まで
  たどれば届く。ここでは、広げを定義の閉包にして、両側が空でない結びがどれも会うかを数える。

手順（族・軸の値・観察・結び・比べで違う軸の値・表すもの D・仮説の側の名の集め方は sys_denote_meets_hypothesis.py と同じ）:
  広げ E1(x): 兄弟と同じ（x と、x の mod の with の1段）。
  広げ E*(x): x から、定義（ノードか個体）の mod の with（並び・入れ子の mod も）と、個体の is を、閉じるまでたどった集合。
    is は、extends を持たない定義（個体）のものだけたどる。ノードの extends（親）はたどらない。
  会う1・会う*: 両側の E1・E* の共通が空でない。
  比べる結び: E1 で両側が空でない結び（兄弟の empty_side 0 にあたる）。
  行（sys_definition_bridges_value.json）: "link 観察 仮説": {meets1, meets_star, empty_side1, empty_side_star}
  要約: n_links, n_nonempty, n_miss1_nonempty, n_miss_star_nonempty, n_bridged（会う1 でなく会う* の、比べる結び）,
        n_miss_star_all, n_empty_side_star
判定: 比べる結びのうち n_miss_star_nonempty が 0 なら支持。1 以上なら反証。

開示（結果を見る前に分かっていること）:
  - 兄弟の結果で、片側が空でない会わない結びは 39（92 − 53）。数えるのはこの範囲。
  - 片側が空の 53 は、定義をたどっても空の側に広がる語がなければ会わない。判定から除き、数を開示する。
  - 閉包は広い語（quality・passage など）に届くことがあり、会う*は甘く出うる。extends をたどらないので、親を通した会いは数えない。
  - 結果は予想しない。
使い方:
  python exp/experiments/sys_definition_bridges_value.py
"""
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_definition_bridges_value.json"


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


def main():
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
        misses.append({"obs": o, "hyp": h, "meets_star": int(bool(os_ & hs)), "via": sorted(os_ & hs)[:10]})
    R = list(rows.values())
    N = [r for r in R if not r["empty_side1"]]
    rows["summary 要約"] = {"n_links": len(R), "n_nonempty": len(N),
                          "n_miss1_nonempty": sum(1 - r["meets1"] for r in N),
                          "n_miss_star_nonempty": sum(1 - r["meets_star"] for r in N),
                          "n_bridged": sum(r["meets_star"] * (1 - r["meets1"]) for r in N),
                          "n_miss_star_all": sum(1 - r["meets_star"] for r in R),
                          "n_empty_side_star": sum(r["empty_side_star"] for r in R)}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_definition_bridges_value.py", "_commit": commit,
                               "rows": rows, "misses": misses}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if rows["summary 要約"]["n_miss_star_nonempty"] == 0 else "反証")


if __name__ == "__main__":
    main()
