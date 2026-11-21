"""h_claims_apart_by_domain を確かめる: 主張を領域で分けて置けば、領域で除くだけで、種類で除いたのと同じ読みになるか。

仮説（exp.yaml）: v_refer(h, v_depend(hypothesis, [syntax.domain, measurement_family]))。登録 #620（issue #622）。
  出どころ: #629（主張の項を種類で除くと、15 語のうち 6 語の読みが動いた）。対の解き方は h_measure_excludes_claim_kinds（#631）。

操作: 体系を読むだけ。#629 のスクリプトと同じ項・錨・J・動詞を使う（コードは写した）。#629 の結果ファイルは使わず、書き換えない。
  主張の領域: 主張の個体（#629 と同じ定め方）を一つでも持つ領域。
  読み kind: 主張の項を除く（#629 の excl と同じ）。
  読み dom: 主張の領域の項をすべて除く（主張の項かどうかを問わない）。
  対象: 読み kind で J がある動詞。
  一致: 読み dom でも J があり、形式・実在（J >= 0.5）が kind と同じもの。
行（sys_claims_apart_by_domain.json）: 動詞ごとに domains_kind, domains_dom, J_kind, J_dom。
  s: claim_domains, n_claim_dom_item（主張の領域の項の数）, n_claim_item, n_verb, n_agree, n_lost（dom で J がなくなったもの）,
     share_agree（n_agree / n_verb）, mean_abs_dJ（両方で J がある動詞の |J_dom - J_kind| の平均）。

判定（事前に決める）:
  tc.build が通らないか n_verb < 4 なら外れ（状態を変えない）。
  支持: share_agree >= 0.9 かつ mean_abs_dJ < 0.05（領域で除くだけで、種類で除いたのと同じ読みになる）。
  反証: share_agree < 0.7（領域で除くと、主張でない内容も失って読みが変わる）。
  mixed: それ以外。
開示: 主張の領域は exp と lang になると見込んでいる（exp.yaml と claims.yaml の領域）。lang には主張でない概念も多く、
  反証の側に寄ると見込んでいるが、数は走らせる前に計算していない。
使い方:
  python exp/experiments/sys_claims_apart_by_domain.py
"""
import contextlib
import io
import itertools
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
KEYS = ("holds", "pre", "post")
CLAIM_KINDS = ("std.hypothesis", "exp.observation", "exp.backlog_item")


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k != "display":
                yield from strings(x)


def main():
    root = HERE.parents[2]
    out = root / "exp/experiments/results/sys_claims_apart_by_domain.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    os.chdir(root)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N

    def anchor(x):
        for y in [x] + list(T.ancestors(x)):
            if T.domain(y) == "ontology":
                return y
        return None

    def is_verb(x):
        return any(N.get(y, {}).get(k) for y in [x] + list(T.ancestors(x)) for k in KEYS)

    cfg = tc.yload((root / "cscl.yaml").read_text(encoding="utf-8"))
    files = [root / cfg["root"]]
    for pat in list(cfg.get("library") or []) + list(cfg.get("include") or []):
        files += sorted(root.glob(pat))
    loaded = []
    claim_ind = set()
    for f in files:
        y = tc.yload(f.read_text(encoding="utf-8")) or {}
        dom = y.get("domain")
        if not isinstance(dom, str):
            continue
        loaded.append((dom, y))
        for k, v in (y.get("individuals") or {}).items():
            k_is = v.get("is") if isinstance(v, dict) else None
            r = T.resolve(k_is, dom) if isinstance(k_is, str) else None
            if r in N and any(c in N and T.is_a(r, c) for c in CLAIM_KINDS):
                claim_ind.add(f"{dom}.{k}")

    def is_claim(dom, raw, self_ind):
        if self_ind in claim_ind:
            return True
        return any(w in claim_ind or f"{dom}.{w}" in claim_ind for w in raw)

    items = []
    for dom, y in loaded:
        for sec in ("nodes", "individuals", "axes"):
            for k, v in (y.get(sec) or {}).items():
                self_id = f"{dom}.{k}" if sec == "nodes" else None
                self_ind = f"{dom}.{k}" if sec == "individuals" else None
                items.append((dom, self_id, self_ind, v))
        for v in y.get("facts") or []:
            items.append((dom, None, None, v))

    claim_dom = sorted({c.split(".", 1)[0] for c in claim_ind})
    verbs = sorted(x for x in N if T.domain(x) == "ontology" and is_verb(x))
    A = {"kind": {v: {} for v in verbs}, "dom": {v: {} for v in verbs}}
    n_claim_dom_item = sum(1 for it in items if it[0] in claim_dom)
    n_claim_item = 0
    for dom, self_id, self_ind, v in items:
        raw = list(strings(v))
        claim = is_claim(dom, raw, self_ind)
        n_claim_item += claim
        rs = [T.resolve(w, dom) for w in raw]
        rs = [r for r in rs if r in N]
        present = [verb for verb in set(rs) if verb in A["kind"] and verb != self_id]
        for verb in present:
            anc = {an for r in rs if r != verb for an in [anchor(r)] if an}
            if not claim:
                A["kind"][verb].setdefault(dom, set()).update(anc)
            if dom not in claim_dom:
                A["dom"][verb].setdefault(dom, set()).update(anc)

    def J(byd):
        doms = sorted(byd)
        if len(doms) < 2:
            return None
        js = []
        for a, b in itertools.combinations(doms, 2):
            u = byd[a] | byd[b]
            js.append(len(byd[a] & byd[b]) / len(u) if u else 1.0)
        return sum(js) / len(js)

    rows = {}
    n_agree = n_lost = 0
    dJ = []
    for verb in verbs:
        jk = J(A["kind"][verb])
        if jk is None:
            continue
        jd = J(A["dom"][verb])
        rows[verb] = {"domains_kind": sorted(A["kind"][verb]), "domains_dom": sorted(A["dom"][verb]),
                      "J_kind": jk, "J_dom": jd}
        if jd is None:
            n_lost += 1
        else:
            dJ.append(abs(jd - jk))
            n_agree += (jd >= 0.5) == (jk >= 0.5)
    n_verb = len(rows)
    s = {"claim_domains": claim_dom, "n_claim_dom_item": n_claim_dom_item, "n_claim_item": n_claim_item,
         "n_verb": n_verb, "n_agree": n_agree, "n_lost": n_lost, "share_agree": n_agree / n_verb if n_verb else 0.0,
         "mean_abs_dJ": sum(dJ) / len(dJ) if dJ else 0.0}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
