"""仮説 h_signature_all_charts（どの領域も signature に依存する。signature は、すべての領域が述べる語の共通部分）を確かめる。
結果を見る前に、この説明と手順を登録した。

式: v_depend(syntax.domain, any)。登録（edab56f）の確かめ方の案: 各領域が使う語を数え、すべての領域が使う語の集まりが
  signature と一致するか、syntax の語がどれだけ混ざるかを数える。
系列: sys_law_without_domain・sys_translation_by_display と同じく、型検査が組んだ事実（T.syntax_facts()）を読む。体系のファイルは書き換えない。
語: 関係 domain の事実の第1引数（節点と個体）。その領域は第2引数。signature の語は、領域が signature の語。
領域 D が使う語:
  直に（主の読み）: 第1引数が D の語である事実の、ほかの引数のうち語であるもの（D の語も含む）。
  閉包（記述）: 直に使う語から、同じく事実の引数を辿って届く語すべて（どの領域の語でも辿る）。
共通部分: signature を除くすべての領域について、使う語の集合の共通部分 I。
  直に使う語が一つもない領域（語を持たない領域）は、共通部分から外し、その名前と数を記録する（n_domain_used、domains_without_use）。
測るもの:
  n_domain      signature を除く領域の数
  n_sig         signature の語の数
  n_I           |I|（直に）
  n_I_sig       |I ∩ signature|
  n_I_nonsig    |I − signature|
  n_sig_not_I   |signature − I|
  any_all       語 any を、すべての領域が直に使えば 1
  I_nonsig      I − signature の語を、領域ごとに数えたもの（記述）
  closure_*     閉包の読みで同じ量（記述。判定に使わない）
判定（事前に決める。直の読みで）:
  支持: n_I >= 1、n_I_nonsig = 0、any_all = 1。
  反証: n_I = 0、n_I_nonsig >= 1、any_all = 0 のどれか。
開示: 型検査が事実を組む過程で足す語（解決した名前、文法の語）が引数に入る。syntax の語は文法の語として、どの領域の事実にも出うる。
  そのため I − signature に syntax の語が入る見込みがあり、反証の見込みもある。
行（sys_signature_all_charts.json）:
  "summary 要約": 上の量のうち数のもの
  "I": 直の読みの I の語の並び、"closure_I_nonsig_by_domain": 閉包の読みの I − signature の、領域ごとの数
使い方:
  python exp/experiments/sys_signature_all_charts.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_signature_all_charts.json"
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]


def last(rel):
    return str(rel).split(".")[-1]


def dom_of_word(w, home):
    return home.get(w, str(w).split(".", 1)[0] if "." in str(w) else None)


def main():
    import os
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    items = list(T.syntax_facts())
    home = {}
    for rel, xs in items:
        if last(rel) == "domain" and isinstance(xs[0], str):
            home.setdefault(xs[0], str(xs[1]))
    words = set(home)
    sig = {w for w, d in home.items() if d == "signature"}
    doms = sorted({d for d in home.values() if d != "signature"})
    edges = collections.defaultdict(set)
    for rel, xs in items:
        if last(rel) == "domain":
            continue
        if isinstance(xs[0], str) and xs[0] in words:
            edges[xs[0]] |= {x for x in xs[1:] if isinstance(x, str) and x in words}
    direct = {d: set() for d in doms}
    for w, d in home.items():
        if d in direct:
            direct[d] |= edges[w]
    closure = {}
    for d in doms:
        seen, stack = set(direct[d]), list(direct[d])
        while stack:
            for y in edges[stack.pop()]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        closure[d] = seen
    used = [d for d in doms if direct[d]]
    I = set.intersection(*(direct[d] for d in used)) if used else set()
    C = set.intersection(*(closure[d] for d in used)) if used else set()
    def summ(S, prefix=""):
        return {f"{prefix}n_I": len(S), f"{prefix}n_I_sig": len(S & sig), f"{prefix}n_I_nonsig": len(S - sig),
                f"{prefix}n_sig_not_I": len(sig - S)}
    s = {"n_domain": len(doms), "n_domain_used": len(used), "n_sig": len(sig)} | summ(I) | summ(C, "closure_")
    s["any_all"] = int(all("any" in direct[d] for d in used))
    s["closure_any_all"] = int(all("any" in closure[d] for d in used))
    by_dom = lambda S: dict(sorted(collections.Counter(dom_of_word(w, home) for w in S - sig).items()))
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"rev": rev, "rows": {"summary 要約": s}, "I": sorted(I), "I_nonsig_by_domain": by_dom(I),
           "closure_I_nonsig_by_domain": by_dom(C), "sig_not_I": sorted(sig - I),
           "domains_without_use": [d for d in doms if not direct[d]]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
