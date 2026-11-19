"""h_hypothesis_refers_family を確かめる: 仮説が自分を確かめる族を指すことは、式から決まるか。

仮説（exp.yaml）: 述べる(仮説, 測定の族)。#237 の反証（族から仮説への対応は1つにならない）から、向きを逆にした解き方。
  仮説から族へは多くてよい。ここでは、仮説が族を「指す」ことを、名前や手書きの結びでなく式で読む:
  仮説の中身の式の要因（v_refer の式の from）が、根拠の観察が使う族の、軸の値か族自身が表す概念（v_denote の終点）か、
  その上位（extends をたどった祖先）にあるとき、仮説はその族を指すと読む。
  観察がどれも族を参照していること（どの族か）は、#237 の兄弟の実験（sys_value_refers_hypothesis、n_obs_no_value 0）で
  すでに分かっている。なので族の有無は問わず、族の表す概念が仮説の要因に届くかを問う。

手順（規則で決める。族と観察と結びの集め方は sys_value_refers_hypothesis.py と同じ）:
  体系の yaml（cscl.yaml の root・library・include）を読み、最上位の事実と、ノード・個体を集める。名は「.」の最後で読む。
  結び: v_support か v_contradict で、始点が観察（o_）、終点が仮説（h_）のもの。結びのある仮説を数える。
  根拠の族 Fam(h): h に結ばれた観察の v_refer の式の from・to・new の文字列のうち、「族.」で始まるものの最初の区切り。
  表す概念 D(h): Fam(h) の族と、その族の軸（v_axis_of）の値（v_value_of）を始点とする v_denote の終点。
  要因 x(h): h の v_refer の式（終点が辞書）の from（文字列）。辞書でなければ、または from が文字列でなければ、要因なしとして数える。
  上位: ノードの extends（文字列か、リストの各要素）を名の最後でたどった祖先。
  届く: x(h) が D(h) のどれかと等しいか、D(h) のどれかの祖先である。
  あわせて記述として、式の to（測る側）の届き方も同じ規則で数える（判定に使わない）。
  行（sys_hypothesis_refers_family.json）:
    "hyp 仮説": {n_fams, n_denoted, factor, reached（0 か 1）, to_reached（0 か 1）, has_factor（0 か 1）}
  要約: n_hyps_linked, n_no_factor, n_reached, n_unreached, n_fams_without_denote, n_to_reached
判定: 要因を持つ仮説のうち、n_unreached が 0 なら支持。1 以上なら反証。n_no_factor は判定から除き、数を開示する。

開示（結果を見る前に分かっていること）:
  - 体系の実験（sys_）の族には、v_denote を持たないものが多いはず（表す概念を書くのはモデルの実験の族で始めた）。
    体系についての仮説（claims.yaml の h_）の根拠がそれらの族なら、届かない仮説が出る。反証の見込みがある。
  - モデルの実験でも、古い族（e1〜e7 など）は v_denote を後から足したもので、全部の条件に付いているかは数えていない。
  - 数はまだ数えていない。

使い方:
  python exp/experiments/sys_hypothesis_refers_family.py
"""
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_hypothesis_refers_family.json"


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
    val_fam = {f["from"]: axis_fam[f["to"]] for f in facts if short(f.get("is")) == "v_value_of"
               and kind.get(f.get("from")) == "axis_value" and f.get("to") in axis_fam}
    denote = {}
    for f in facts:
        if short(f.get("is")) == "v_denote" and isinstance(f.get("to"), str):
            s = f.get("from")
            fm = s if s in fams else val_fam.get(s)
            if fm:
                denote.setdefault(fm, set()).add(short(f["to"]))

    def ancestors(x):
        seen, todo = set(), [x]
        while todo:
            e = ents.get(todo.pop()) or {}
            ups = e.get("extends")
            for u in [ups] if isinstance(ups, str) else ups if isinstance(ups, list) else []:
                if isinstance(u, str) and short(u) not in seen:
                    seen.add(short(u))
                    todo.append(short(u))
        return seen

    obs_fams, content = {}, {}
    for f in facts:
        if short(f.get("is")) != "v_refer" or not isinstance(f.get("to"), dict):
            continue
        s, F = str(f.get("from", "")), f["to"]
        if s.startswith("o_"):
            for w in strings(F.get("from")) + strings(F.get("to")) + strings(F.get("new")):
                if w.split(".")[0] in fams:
                    obs_fams.setdefault(s, set()).add(w.split(".")[0])
        elif s.startswith("h_"):
            content[s] = F
    links = [(f["from"], f["to"]) for f in facts if short(f.get("is")) in ("v_support", "v_contradict")
             and str(f.get("from", "")).startswith("o_") and str(f.get("to", "")).startswith("h_")]
    hyps = sorted({h for _, h in links})
    rows = {}
    for h in hyps:
        F = {fm for o, hh in links if hh == h for fm in obs_fams.get(o, set())}
        D = set().union(*(denote.get(fm, set()) for fm in F)) if F else set()
        reach = D | set().union(*(ancestors(d) for d in D)) if D else set()
        c = content.get(h) or {}
        x, t = c.get("from"), c.get("to")
        has = isinstance(x, str)
        rows[f"hyp {h}"] = {"n_fams": len(F), "n_denoted": len(D), "factor": x if has else None, "has_factor": int(has),
                            "reached": int(has and short(x) in reach),
                            "to_reached": int(isinstance(t, str) and short(t) in reach)}
    hv = [r for r in rows.values() if r["has_factor"]]
    linked_fams = {fm for o, _ in links for fm in obs_fams.get(o, set())}
    rows["summary 要約"] = {"n_hyps_linked": len(hyps), "n_no_factor": len(hyps) - len(hv),
                          "n_reached": sum(r["reached"] for r in hv), "n_unreached": sum(1 - r["reached"] for r in hv),
                          "n_fams_without_denote": sum(1 for fm in linked_fams if not denote.get(fm)),
                          "n_to_reached": sum(r["to_reached"] for r in rows.values())}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_hypothesis_refers_family.py", "_commit": commit, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if rows["summary 要約"]["n_unreached"] == 0 else "反証")


if __name__ == "__main__":
    main()
