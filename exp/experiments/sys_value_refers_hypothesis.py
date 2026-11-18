"""h_value_refers_hypothesis を確かめる: いまの根拠の結びは、軸の値から仮説への1つの対応で言い表せるか。

仮説（exp.yaml）: 述べる(軸の値, 仮説)。#237 で、族から仮説への対応では言い表せなかった（結びのある族 69 のうち 17 が
  2つ以上の仮説に結ばれる）。共有の多くは、族の中の条件ごとに別の仮説に使われていた。指す単位を軸の値に細かくすれば、
  対応が1つになるかを数える。ここでも、軸の値を指す式は足さない。

手順（規則で決める。族と観察と結びの集め方は #237 の sys_family_refers_hypothesis.py と同じ）:
  体系の yaml（cscl.yaml の root・library・include）を読み、最上位の事実と、ノード・個体を集める。
  族: {is: measurement_family}。軸: {is: family_axis} で、v_axis_of で族に結ばれるもの。
  軸の値: {is: axis_value} で、v_value_of で軸に結ばれるもの。綴りは val の text。
  観察の値: 観察 o の v_refer の式の from・to・new の文字列のうち、「族.」で始まるもの。
    「.」で分け、最初が族、最後が指標、その間の区切りを、その族の軸の値の綴りに照らして軸の値に解く。
    解けない区切りは、数えて行に出す（unresolved）。
  結び: v_support か v_contradict で、始点が観察、終点が仮説（h_ で始まる）のもの。
  軸の値ごとに、その値を含む観察から結ばれた仮説の集まりを作る。
  あわせて、値の区切りの並び全体（族と軸の値の組、cell）ごとにも同じ集まりを作る。これは判定に使わない（開示の欄）。
  行（sys_value_refers_hypothesis.json）:
    "value 軸の値": {n_obs, n_hyps, shared（n_hyps が2以上なら 1）}
    "cell 族.値…": {n_obs, n_hyps, shared}
  要約: n_values_linked, n_shared, n_cells_linked, n_cells_shared, n_links, n_obs_linked, n_obs_no_value, n_unresolved
判定: n_shared（軸の値の）が 0 なら支持。1 以上なら反証。

開示（結果を見る前に分かっていること）:
  - 体系の実験（sys_）の族の軸は、ふつう列を値にした軸1つ（cond）で、値は指標の名に近い。
  - モデルの実験の族には軸が2つのもの（e7 の group と cond など）がある。group の値は、cond の値どうしで共有されうる。
    そのため軸の値の単位では共有が残ることは見込まれるが、数は数えていない。cell の単位でどうなるかも予想しない。
  - 共有があっても結びが誤りとは限らない。同じ条件が別々の仮説に効くことはある。
使い方:
  python exp/experiments/sys_value_refers_hypothesis.py
"""
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_value_refers_hypothesis.json"


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
            v = f["from"]
            t = ((ents[v].get("val") or {}).get("text"))
            if t is not None:
                spell.setdefault(axis_fam[f["to"]], {}).setdefault(str(t), set()).add(v)
    obs_vals, obs_cells, unresolved = {}, {}, []
    for f in facts:
        if short(f.get("is")) == "v_refer" and str(f.get("from", "")).startswith("o_") and isinstance(f.get("to"), dict):
            o, F = f["from"], f["to"]
            for w in strings(F.get("from")) + strings(F.get("to")) + strings(F.get("new")):
                parts = w.split(".")
                if len(parts) < 2 or parts[0] not in fams:
                    continue
                fm, mid = parts[0], parts[1:-1]
                obs_cells.setdefault(o, set()).add(".".join(parts[:-1]))
                for s in mid:
                    vs = spell.get(fm, {}).get(s)
                    if vs:
                        obs_vals.setdefault(o, set()).update(vs)
                    else:
                        unresolved.append([o, w, s])
    links = [(f["from"], f["to"]) for f in facts if short(f.get("is")) in ("v_support", "v_contradict")
             and str(f.get("from", "")).startswith("o_") and str(f.get("to", "")).startswith("h_")]

    def table(obs_map, tag):
        H, O = {}, {}
        for o, h in links:
            for x in obs_map.get(o, set()):
                H.setdefault(x, set()).add(h)
                O.setdefault(x, set()).add(o)
        return {f"{tag} {x}": {"n_obs": len(O[x]), "n_hyps": len(H[x]), "shared": int(len(H[x]) > 1)} for x in sorted(H)}, H

    vrows, vH = table(obs_vals, "value")
    crows, cH = table(obs_cells, "cell")
    linked = sorted({o for o, _ in links})
    rows = {**vrows, **crows}
    rows["summary 要約"] = {"n_values_linked": len(vrows), "n_shared": sum(r["shared"] for r in vrows.values()),
                          "n_cells_linked": len(crows), "n_cells_shared": sum(r["shared"] for r in crows.values()),
                          "n_links": len(links), "n_obs_linked": len(linked),
                          "n_obs_no_value": sum(1 for o in linked if not obs_vals.get(o)),
                          "n_unresolved": len(unresolved)}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_value_refers_hypothesis.py", "_commit": commit, "rows": rows,
                               "shared_values": {x: sorted(vH[x]) for x in vH if len(vH[x]) > 1},
                               "shared_cells": {x: sorted(cH[x]) for x in cH if len(cH[x]) > 1},
                               "no_value": [o for o in linked if not obs_vals.get(o)], "unresolved": unresolved},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if rows["summary 要約"]["n_shared"] == 0 else "反証")


if __name__ == "__main__":
    main()
