"""h_reading_excludes_claims を確かめる: 体系を測った値は、体系に書いた主張（仮説・観察・残り項目）に依らない。

仮説（exp.yaml）: v_refer(h, v_depend(observation, hypothesis, neg))。登録 #620。
  出どころ: #619 の追記（lang の項に、測る対象についての仮説の登録そのものが入り、錨を動かした）。

問い: #619 の読み方（動詞を使う項の相手の錨の、領域どうしの Jaccard）で、主張の項を除くと値と判定が動くか。
  動くなら、測った値は主張に依っている（仮説の否定、つまり測るときに主張を除かなければならない）。
  ※ 仮説は「依らない」という形で書いてある。判定は「依らない」が成り立つかを問う。
操作: 体系を読むだけ（写しも書き換えもしない）。#619 の結果ファイルは使わず、書き換えない。
  項: #619 と同じ（cscl.yaml の root・library・include の各ファイルの nodes・individuals・axes の値と facts）。
  主張の個体: individuals のうち、is を T.resolve で解決したものが std.hypothesis・exp.observation・exp.backlog_item の
    どれかに T.is_a で届くもの（領域つきの識別子で集める）。
  主張の項: 項の中の文字列を T.resolve で解決する前の形（そのままか、領域を付けた形）が主張の個体に一致するものを
    一つでも含む項。主張の個体自身の定義の項も主張の項。
  動詞: ontology の領域のノードで、自分か祖先が holds・pre・post のどれかを持つもの。
  読み all: すべての項で #619 と同じ J(v) を数える。読み excl: 主張の項を除いて数える。
  対象: 読み all で使う領域が二つ以上の動詞（#619 の 6 語に限らない）。
  形式: J >= 0.5、実在: J < 0.5。
  ずれ: 対象の動詞のうち、読み excl で領域が二つ未満になったもの（n_drop）と、形式・実在が入れ替わったもの（n_flip）。
行（sys_reading_excludes_claims.json）: 動詞ごとに domains_all, domains_excl, J_all, J_excl。
  s: n_claim_ind, n_claim_item, n_item, n_verb, n_drop, n_flip, share_shift（(n_drop + n_flip) / n_verb）, mean_abs_dJ
     （両方で J がある動詞の |J_excl - J_all| の平均）。

判定（事前に決める）:
  tc.build が通らないか n_verb < 4 なら外れ（状態を変えない）。
  支持: n_drop + n_flip = 0 かつ mean_abs_dJ < 0.05（主張を除いても読みは変わらない）。
  反証: share_shift >= 0.1（主張が読みを動かす）。
  mixed: それ以外。
開示: #619 で v_express が手の見積もりで動くことを先に見ている。対象を ontology の動詞すべてに広げたのは、
  その一語だけで決まらないようにするため。走らせる前に、ほかの語の数は計算していない。
使い方:
  python exp/experiments/sys_reading_excludes_claims.py
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
    out = root / "exp/experiments/results/sys_reading_excludes_claims.json"
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

    verbs = sorted(x for x in N if T.domain(x) == "ontology" and is_verb(x))
    A = {"all": {v: {} for v in verbs}, "excl": {v: {} for v in verbs}}
    n_claim_item = 0
    for dom, self_id, self_ind, v in items:
        raw = list(strings(v))
        claim = is_claim(dom, raw, self_ind)
        n_claim_item += claim
        rs = [T.resolve(w, dom) for w in raw]
        rs = [r for r in rs if r in N]
        present = [verb for verb in set(rs) if verb in A["all"] and verb != self_id]
        for verb in present:
            anc = {an for r in rs if r != verb for an in [anchor(r)] if an}
            for mode in ("all", "excl"):
                if mode == "excl" and claim:
                    continue
                A[mode][verb].setdefault(dom, set()).update(anc)

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
    n_drop = n_flip = 0
    dJ = []
    for verb in verbs:
        ja = J(A["all"][verb])
        if ja is None:
            continue
        je = J(A["excl"][verb])
        rows[verb] = {"domains_all": sorted(A["all"][verb]), "domains_excl": sorted(A["excl"][verb]),
                      "J_all": ja, "J_excl": je}
        if je is None:
            n_drop += 1
        else:
            dJ.append(abs(je - ja))
            n_flip += (je >= 0.5) != (ja >= 0.5)
    n_verb = len(rows)
    s = {"n_claim_ind": len(claim_ind), "n_claim_item": n_claim_item, "n_item": len(items), "n_verb": n_verb,
         "n_drop": n_drop, "n_flip": n_flip, "share_shift": (n_drop + n_flip) / n_verb if n_verb else 0.0,
         "mean_abs_dJ": sum(dJ) / len(dJ) if dJ else 0.0}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
