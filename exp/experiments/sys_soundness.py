"""体系そのものを数える（3）。真偽の対称性の崩れは、欠陥の場所を示すか（仮説 h_symmetry_soundness の確かめ）。

この手順は、結果を見る前に登録した（cscl/design/claims.yaml の h_symmetry_soundness と b_symmetry_soundness）。
手順・基準・判定のしかたは、登録した版から変えない。

版
  C0  48a43c9  main の first-parent で、いまの置き場（cscl/library/*）が初めて現れた版。対称性はこの版で測る
  C1  933ddd6  main の版のうち、対称性を主題にした作業（PR #93 とその後）を含まない最後の版。書き換えはここまでで測る
  C0 と C1 は、どちらもこの手順を書く前に決まっていた版。C1 より後の変更は、この仮説を調べる作業が混ざるので使わない。

単位（C0 の体系のノード。cscl/library/*、cscl/design/claims.yaml、exp/src/* に書いたもの）
  動詞    holds・pre・post のどれかに原子を持つノード
  限定    動詞でなく、自分の限定（mod）を1つ以上持つノード。名前を付けた限定は、その中身に直してから見る
  どちらにも当たらないノード（根・限定を持たない種類・個体）は数えない。

対（C0 の体系の中だけで見る）
  動詞    原子（neg, 関係, 位置）の否定をすべて反転した holds・pre・post を持つ、別の動詞がある
  限定    自分の限定それぞれについて、同じ of・with で否定が逆の限定を持つノードが、体系のどこかにある
  対がそろっていれば paired、そうでなければ unpaired。

欠陥の基準（対称性と別に決める）
  changed  C1 でそのノードが消えているか、定義（表示・説明・原文を除くすべての項目）が C0 と違う
  比べる前に、名前の領域の接頭辞（ontology. など）は外し、名前を付けた限定は中身に直す。

判定（登録した基準）
  支持      unpaired の changed の割合が paired より大きく、片側 Fisher の正確検定で p < 0.05
  反証      unpaired の changed の割合が paired 以下
  どちらでもない  大きいが p >= 0.05
  主の判定は動詞と限定を合わせた全体。動詞だけ、限定だけの値も記録する（副）。

結果ファイル sys_soundness.json
  単位ごとに1行。列は {paired|unpaired}_changed と、{verb|mod}_{paired|unpaired}_changed（0 か 1）。
  行 "test" に p_value（全体の片側 Fisher の p）。

使い方:
  python exp/experiments/sys_soundness.py
"""
import json
import subprocess
from math import comb
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
C0, C1 = "48a43c9", "933ddd6"
SKIP = {"display", "gloss", "verbatim"}
DOMS = ("axiom", "ontology", "syntax", "runtime", "std")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def files(c):
    names = git("ls-tree", "-r", "--name-only", c).split()
    return [n for n in names if n.endswith(".yaml") and (n.startswith("cscl/library/") or n.startswith("exp/src/")
                                                      or n == "cscl/design/claims.yaml")]


def strip(x):
    if isinstance(x, str):
        head, _, tail = x.partition(".")
        return tail if tail and head in DOMS + ("lang", "exp", "subj") else x
    if isinstance(x, list):
        return [strip(v) for v in x]
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items()}
    return x


def nodes(c):
    out = {}
    for f in files(c):
        d = yaml.safe_load(git("show", f"{c}:{f}")) or {}
        for k, v in (d.get("nodes") or {}).items():
            if isinstance(v, dict):
                out[(Path(f).stem, k)] = strip(v)
    named = {k: {x: v[x] for x in ("of", "with", "neg", "at") if x in v} for (_, k), v in out.items() if "of" in v}
    for v in out.values():
        if "mod" in v:
            ms = v["mod"] if isinstance(v["mod"], list) else [v["mod"]]
            v["mod"] = [named.get(m, m) if isinstance(m, str) else m for m in ms]
    return out


def atoms(v, part):
    return frozenset((bool(a.get("neg")), a.get("is"), a.get("from"), a.get("to"))
                     for a in v.get(part) or [] if isinstance(a, dict))


def sig(v, flip=False):
    return tuple(frozenset((n != flip, r, f, t) for n, r, f, t in atoms(v, p)) for p in ("holds", "pre", "post"))


def fisher_greater(a, b, c, d):
    """2x2 表 [[a, b], [c, d]]（行: unpaired, paired、列: changed, 変わらない）で、a 以上になる片側の p。"""
    n1, k, n = a + b, a + c, a + b + c + d
    tot = comb(n, n1)
    return sum(comb(k, i) * comb(n - k, n1 - i) for i in range(a, min(n1, k) + 1)) / tot


def main():
    N0, N1 = nodes(C0), nodes(C1)
    verbs = {k: v for k, v in N0.items() if any(atoms(v, p) for p in ("holds", "pre", "post"))}
    sigs = {}
    for k, v in verbs.items():
        sigs.setdefault(sig(v), set()).add(k)
    pol = {}
    for v in N0.values():
        for m in v.get("mod") or []:
            if isinstance(m, dict) and "of" in m:
                pol.setdefault((json.dumps(m["of"]), json.dumps(m.get("with"))), set()).add(bool(m.get("neg")))
    rows = {}
    for k, v in N0.items():
        if k in verbs:
            kind, paired = "verb", bool(sigs.get(sig(v, flip=True), set()) - {k})
        else:
            ms = [m for m in v.get("mod") or [] if isinstance(m, dict) and "of" in m]
            if not ms:
                continue
            kind = "mod"
            paired = all((not m.get("neg")) in pol[(json.dumps(m["of"]), json.dumps(m.get("with")))] for m in ms)
        defn = lambda x: {a: b for a, b in x.items() if a not in SKIP}
        changed = int(k not in N1 or defn(N1[k]) != defn(v))
        side = "paired" if paired else "unpaired"
        rows[f"{k[0]}.{k[1]}"] = {f"{side}_changed": changed, f"{kind}_{side}_changed": changed}
    col = lambda c: [r[c] for r in rows.values() if c in r]
    u, p = col("unpaired_changed"), col("paired_changed")
    rows["test"] = {"p_value": fisher_greater(sum(u), len(u) - sum(u), sum(p), len(p) - sum(p))}
    (OUT / "sys_soundness.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_soundness.py", "_commit": git("rev-parse", "HEAD").strip(),
         "_versions": {"C0": C0, "C1": C1}, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in ("unpaired_changed", "paired_changed", "verb_unpaired_changed", "verb_paired_changed",
              "mod_unpaired_changed", "mod_paired_changed"):
        xs = col(c)
        print(f"{c:24} n={len(xs):4} changed={sum(xs):4} rate={sum(xs) / len(xs) if xs else float('nan'):.3f}")
    print("p_value", rows["test"]["p_value"])


if __name__ == "__main__":
    main()
