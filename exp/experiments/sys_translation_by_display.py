"""仮説 h_translation_by_display（訳語は領域ではなく、言語に依存する表示語）を確かめる。
結果を見る前に、この説明と手順を登録した。

式: v_depend(syntax.display, syntax.language)。表示語は言語ごとに替えてよく、式（表示語を除く事実）は言語に依存しない、と読む。
  確かめるのはその前提: 型検査の法則が表示語の中身を読まないこと（読むのは、同じ領域で重複しないことだけ）。
  読まなければ、表示語を言語ごとに差し替えても、体系の分類と法則の判定は変わらない。
出どころ: #605。英日で同じ式を別の領域に書くと、法則 one_name に当たった。
系列: sys_law_without_domain と同じく、型検査が組んだ事実（T.syntax_facts()）に法則を当て、導いた関係と違反を数える。
変種（体系のファイルは書き換えない。事実の列だけを変える）:
  L   そのまま。
  T   関係 display の事実の値を、すべて "en:" + 節点の名前 に置き換える（別の言語の表示語に差し替える。値は節点ごとに違う）。
  B   関係 display の事実はそのまま残し、"en:" + 節点の名前 の display の事実を同じ節点に足す（二つの言語の表示語が並ぶ）。
  P   記述だけ（判定に使わない）: #605 の道。節点の最も少ない領域のうち節点が 10 以上のものを一つ選び、
      その領域の節点を名前 "en_" + 元の名前、領域 "__en__" で写す。事実の引数のうち、その領域の節点である文字列を写した名前に替え、
      display は "en:" + 元の名前 にする。限定の中身を書いた文字列（mod の dump）の中の名前は替えない（開示）。
測るもの（変種ごと）:
  n_display      display の事実の数
  viol           法則ごとの違反の数
  same_rel       法則が導いた r_ の関係の項の集合が、すべて L と同じなら 1（T・B）
  same_viol      違反（法則と束縛の組）の集合が L と同じなら 1（T・B）。T は display の値を束縛に含む違反を、値を節点の名前で置き換えて比べる
  changed_rel    L と項の集合が違う r_ の関係と、L だけ・変種だけの項の数（記述）
  new_viol       L になく変種にある違反の、法則ごとの数（記述。P では #605 の再現の観察）
判定（事前に決める）:
  支持: T と B のどちらでも same_rel 1 かつ same_viol 1。
  反証: T か B のどちらかで same_rel 0 か same_viol 0。
  （法則の評価が例外で止まったら、その変種は未決とし、状態は変えない。P は判定に使わない。）
見込み: 表示語を前提に持つ法則は unique_in_domain だけで、値の等しさしか読まないので、支持の見込み。
行（sys_translation_by_display.json）:
  "variant <v>": 上の量（v は L, T, B, P）
  "summary 要約": same_rel_<V>, same_viol_<V>（V は T, B）
使い方:
  python exp/experiments/sys_translation_by_display.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_translation_by_display.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]


def last(rel):
    return str(rel).split(".")[-1]


def pick_domain(items):
    count = collections.Counter(xs[1] for rel, xs in items if last(rel) == "domain")
    cands = sorted((n, str(d)) for d, n in count.items() if n >= 10)
    return cands[0][1] if cands else None


def variant_items(items, v):
    if v == "L":
        return list(items), None
    if v == "T":
        return [(rel, (xs[0], "en:" + str(xs[0])) + tuple(xs[2:])) if last(rel) == "display" else (rel, xs)
                for rel, xs in items], None
    if v == "B":
        extra = [(rel, (xs[0], "en:" + str(xs[0])) + tuple(xs[2:])) for rel, xs in items if last(rel) == "display"]
        return list(items) + extra, None
    dom = pick_domain(items)
    nodes = {xs[0] for rel, xs in items if last(rel) == "domain" and str(xs[1]) == dom}
    out = list(items)
    for rel, xs in items:
        if not any(isinstance(x, str) and x in nodes for x in xs):
            continue
        if last(rel) == "domain" and xs[0] in nodes:
            out.append((rel, ("en_" + xs[0], "__en__") + tuple(xs[2:])))
        elif last(rel) == "display" and xs[0] in nodes:
            out.append((rel, ("en_" + xs[0], "en:" + str(xs[0])) + tuple(xs[2:])))
        else:
            out.append((rel, tuple("en_" + x if isinstance(x, str) and x in nodes else x for x in xs)))
    return out, dom


def derive(tc, O, items):
    F = tc.Facts(items)
    viol = tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rels = {}
    for k in F.by:
        if last(k).startswith("r_"):
            rels.setdefault(last(k), set()).update(map(str, F.by[k]))
    return rels, viol


def viol_key(lid, b, unmap):
    return (str(lid), tuple(sorted((str(k), unmap.get(str(v), str(v))) for k, v in b.items())))


def main():
    import os
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    items = list(T.syntax_facts())
    disp = {str(xs[0]): str(xs[1]) for rel, xs in items if last(rel) == "display"}
    res = {}
    for v in "LTBP":
        its, dom = variant_items(items, v)
        rels, viol = derive(tc, O, its)
        res[v] = (its, dom, rels, viol)
    base_rels = res["L"][2]
    base_viol = {viol_key(l, b, {}) for l, b, _ in res["L"][3]}
    rows, summ = {}, {}
    for v, (its, dom, rels, viol) in res.items():
        unmap = {"en:" + n: d for n, d in disp.items()} if v == "T" else {}
        vk = {viol_key(l, b, unmap) for l, b, _ in viol}
        row = {"n_display": sum(1 for rel, _ in its if last(rel) == "display"),
               "viol": dict(sorted(collections.Counter(str(l) for l, _, _ in viol).items()))}
        if dom is not None:
            row["domain"] = dom
        if v != "L":
            row["changed_rel"] = {k: {"only_L": len(base_rels.get(k, set()) - rels.get(k, set())),
                                      "only_v": len(rels.get(k, set()) - base_rels.get(k, set()))}
                                  for k in sorted(set(base_rels) | set(rels)) if base_rels.get(k, set()) != rels.get(k, set())}
            row["new_viol"] = dict(sorted(collections.Counter(l for l, _ in vk - base_viol).items()))
        if v in "TB":
            row["same_rel"] = int(not row["changed_rel"])
            row["same_viol"] = int(vk == base_viol)
            summ |= {f"same_rel_{v}": row["same_rel"], f"same_viol_{v}": row["same_viol"]}
        rows[f"variant {v}"] = row
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, r in rows.items():
        print(k, json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
