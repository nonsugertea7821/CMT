"""h_denote_meets_hypothesis を確かめる: 観察の比べる軸の値が表すものは、結ばれた仮説の指すものに会うか。

仮説（exp.yaml）: 表す(軸の値, 仮説)。#241 で、軸の値や cell の単位では、1つの比べが2つ以上の仮説に結ばれた。
  どの仮説に効くかを分けるのは、比べる値の表すもの（v_denote・v_compose）だと見る。ここでは、いまの結びのそれぞれで、
  観察の比べで違う軸の値が表すものが、仮説の式の指すものに会うかを数える。

手順（規則で決める。族・軸の値・観察・結びの集め方は #241 の sys_value_refers_hypothesis.py と同じ）:
  cell: 観察の値「族.値….指標」から指標を除いた並び。cell の軸の値は、区切りを族の軸の値の綴りに照らして解いたもの。
  比べで違う軸の値: 観察の cell が2つ以上なら、どれかの cell にあって全部の cell にはない軸の値。cell が1つなら、その軸の値全部。
  表すもの D(v): 事実 {is: v_denote, from: v, to: x} の x と、{is: v_compose, from: x, to: v} の x。
  広げ E(x): x と、x の定義（ノードか個体）の mod の with（1段だけ。並びならそれぞれ）。is・extends の親はたどらない。
  観察の側: 比べで違う軸の値の D の和を、E で広げたもの。
  仮説の側: 仮説の v_refer の式（入れ子を含む）の、is 以外の値の文字列（領域の接頭辞は外す）を、E で広げたもの。
  会う: 両側の共通が空でない。
  行（sys_denote_meets_hypothesis.json）: "link 観察 仮説": {meets（0 か 1）, n_diff_values, empty_side（どちらかの側が空なら 1）}
  要約: n_links, n_meets, n_miss, n_empty_side
判定: n_miss が 0 なら支持。1 以上なら反証。どちらかの側が空の結びも、会わないに数える。

開示（結果を見る前に分かっていること）:
  - e7 の sys1 と sys1-far2000 は、v_denote が同じで、far2000 にだけ v_compose following_text がある。
    h_distance_does_not_lower の distance_to_question は mod の with に following_text をもつ。
    h_length_does_not_lower の context_length の with は context。会うかは数えていない。
  - group（G2c など）や model（4b など）の軸の値に v_denote がどれだけあるかは数えていない。結果は予想しない。
  - 広げを1段に限り、親をたどらないのは、passage・definition のような広い親で何でも会ってしまうのを避けるため。
    そのぶん、言い換えで会うものを取りこぼしうる。
使い方:
  python exp/experiments/sys_denote_meets_hypothesis.py
"""
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_denote_meets_hypothesis.json"


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
        oside = set().union(*[E(x) for v in diff for x in den.get(v, ())]) if diff else set()
        hside = set().union(*[E(x) for F in hyp_f.get(h, []) for x in formula_names(F)]) if hyp_f.get(h) else set()
        meet = oside & hside
        rows[f"link {o} {h}"] = {"meets": int(bool(meet)), "n_diff_values": len(diff),
                                 "empty_side": int(not oside or not hside)}
        if not meet:
            misses.append({"obs": o, "hyp": h, "diff": sorted(diff), "obs_side": sorted(oside), "hyp_side": sorted(hside)})
    R = list(rows.values())
    rows["summary 要約"] = {"n_links": len(R), "n_meets": sum(r["meets"] for r in R),
                          "n_miss": sum(1 - r["meets"] for r in R), "n_empty_side": sum(r["empty_side"] for r in R)}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_denote_meets_hypothesis.py", "_commit": commit,
                               "rows": rows, "misses": misses}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if rows["summary 要約"]["n_miss"] == 0 else "反証")


if __name__ == "__main__":
    main()
