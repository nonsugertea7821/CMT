"""h_family_refers_hypothesis を確かめる: いまの根拠の結びは、測定値の族から仮説への1つの対応で言い表せるか。

仮説（exp.yaml）: 述べる(測定値の族, 仮説)。族が確かめる仮説を式で指せば、観察と仮説の結び（v_support・v_contradict）を
  族から導けるか、照らせる。ここでは族を指す式は足さない。いまの結びが、族から仮説への対応（族ごとに仮説が1つ）と
  食い違わないかを数える。食い違う族があれば、族が仮説を1つ指すという書き方では、いまの結びを言い表せない。

手順（規則で決める）:
  体系の yaml（cscl.yaml の root・library・include）を読み、最上位の事実を集める。
  族: {is: measurement_family} のノード（名前）。
  観察の族: 観察 o（v_refer の始点が o_ で始まり、終点が式のもの。同じ主語の式はすべて）の式の from・to・new
    （文字列か、文字列の並び）のうち、「名前.」で始まり、名前が族であるものの、その名前。
  結び: 動詞が v_support か v_contradict（領域の接頭辞は外して読む）で、始点が観察、終点が仮説（h_ で始まる）のもの。
  族ごとに、その族を式に含む観察から結ばれた仮説の集まりを作る。
  行（sys_family_refers_hypothesis.json）:
    "family 族": {n_obs（族を含む観察で結びのあるもの）, n_hyps（結ばれた仮説の数）, shared（n_hyps が2以上なら 1）}
    "link 観察": {n_families（観察の式に含まれる族の数）, no_family（族を含まなければ 1）}
  要約: n_families_linked, n_shared, n_links, n_obs_linked, n_obs_no_family, n_obs_multi_family
判定: n_shared が 0 なら支持（族ごとに仮説が1つで、族から仮説を指す式で、いまの結びを言い表せる）。1 以上なら反証。

開示（結果を見る前に分かっていること）:
  - 族は exp.yaml に 127。族の値は「族.条件….指標」の形で書かれる。
  - 1つの族が複数の仮説の根拠になっているか、族を含まない観察がどれだけあるかは、数えていない。結果は予想しない。
  - 族が2つ以上の仮説に結ばれていても、結びが誤りとは限らない（同じ測定が別々の仮説に効くことはある）。
    その場合、族が指すものを仮説1つでなく仮説の集まりにする書き方が残る。解釈で書く。

使い方:
  python exp/experiments/sys_family_refers_hypothesis.py
"""
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_family_refers_hypothesis.json"


def yaml_files():
    c = yaml.safe_load((ROOT / "cscl.yaml").read_text(encoding="utf-8"))
    pats = [c["root"]] + c.get("library", []) + c.get("include", [])
    return [p for g in pats for p in sorted(ROOT.glob(g))]


def verb(f):
    return str(f.get("is", "")).split(".")[-1]


def strings(x):
    if isinstance(x, str):
        return [x]
    if isinstance(x, list):
        return [s for y in x for s in strings(y)]
    return []


def main():
    fams, facts = set(), []
    for p in yaml_files():
        D = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for k, v in (D.get("nodes") or {}).items():
            if isinstance(v, dict) and str(v.get("is", "")).split(".")[-1] == "measurement_family":
                fams.add(k)
        for k, v in (D.get("individuals") or {}).items():
            if isinstance(v, dict) and str(v.get("is", "")).split(".")[-1] == "measurement_family":
                fams.add(k)
        facts += [f for f in D.get("facts") or [] if isinstance(f, dict)]
    obs_fams = {}
    for f in facts:
        if verb(f) == "v_refer" and str(f.get("from", "")).startswith("o_") and isinstance(f.get("to"), dict):
            F = f["to"]
            ws = strings(F.get("from")) + strings(F.get("to")) + strings(F.get("new"))
            obs_fams.setdefault(f["from"], set()).update(w.split(".")[0] for w in ws if "." in w and w.split(".")[0] in fams)
    links = [(f["from"], f["to"]) for f in facts if verb(f) in ("v_support", "v_contradict")
             and str(f.get("from", "")).startswith("o_") and str(f.get("to", "")).startswith("h_")]
    fam_h, fam_o = {}, {}
    for o, h in links:
        for fm in obs_fams.get(o, set()):
            fam_h.setdefault(fm, set()).add(h)
            fam_o.setdefault(fm, set()).add(o)
    rows = {}
    for fm in sorted(fam_h):
        rows[f"family {fm}"] = {"n_obs": len(fam_o[fm]), "n_hyps": len(fam_h[fm]), "shared": int(len(fam_h[fm]) > 1)}
    linked_obs = sorted({o for o, _ in links})
    for o in linked_obs:
        n = len(obs_fams.get(o, set()))
        rows[f"link {o}"] = {"n_families": n, "no_family": int(n == 0)}
    F = [r for k, r in rows.items() if k.startswith("family ")]
    L = [r for k, r in rows.items() if k.startswith("link ")]
    rows["summary 要約"] = {"n_families_linked": len(F), "n_shared": sum(r["shared"] for r in F), "n_links": len(links),
                          "n_obs_linked": len(L), "n_obs_no_family": sum(r["no_family"] for r in L),
                          "n_obs_multi_family": sum(r["n_families"] > 1 for r in L)}
    shared = {fm: sorted(fam_h[fm]) for fm in fam_h if len(fam_h[fm]) > 1}
    no_family = [o for o in linked_obs if not obs_fams.get(o)]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"_source": "exp/experiments/sys_family_refers_hypothesis.py", "_commit": commit, "rows": rows,
                               "shared": shared, "no_family": no_family}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print(json.dumps(shared, ensure_ascii=False))
    print(no_family[:20])
    print("判定:", "支持" if rows["summary 要約"]["n_shared"] == 0 else "反証")


if __name__ == "__main__":
    main()
