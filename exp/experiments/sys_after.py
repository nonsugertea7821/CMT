"""体系そのものを数える: 基礎の関係 after を式に持つ動詞が、何と何の順序を述べているか（時間の順序か、並びの順序か）。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 論理演算（not, some）、一つの評価（step）、時間の連続（after）は、どれもシグネチャになく、コードが意味を与えている。
  時間の芯を step にすれば after は step をたどって導けるが、ontology の after は文の中の並び（v_come_after: 後ろに置かれる）にも使われる。
  一つの after が時間と並びの2つを指しているなら混同。どちらに使われているかを観察で分ける。

数え方（規則で決める）:
  対象: 体系のノードのうち動詞（Ontology.is_verb）で、自分か上位の動詞の holds, pre, post に、関係 after の文（否定も含む）を持つもの。
  端: Ontology.end(動詞, "from") と end(動詞, "to")。any はどちらにも属さないとする。
  行の値（動詞ごと）:
    time    始点も終点も occurrent の下（過程・出来事の順序）
    entity  始点も終点も continuant の下（持続するもの、たとえば語や文の並び）
    open    どちらでもない（端に any がある、または種類が混ざる）
    used    その動詞を is に書いた事実が、体系（個体と事実）に1つ以上ある
  ほかに、規則で書いた法則のうち、前提・導く文・求める文に after を書いたものを行にする:
    "law 法則"  rule_after = 1
訂正（実行の後。1b2a69c の手順で一度走らせた）: used を、ライブラリの事実（O["facts"]）だけから数えていた。領域のファイルの事実が入らず、
  used が 0/17 と出た（grep で v_come_after などを書いた事実は少なくとも 164 行ある）。手順の言葉（体系の個体と事実）どおり、
  ライブラリと領域のすべてのファイルの事実（入れ子の文も含む）から数えるように直した。time, entity, open の値は、この直しで変わらない。
登録の前に分かっていること（会話）: v_come_after と v_come_before は from: continuant, to: continuant。runtime の every_step は
  v_come_after を steps（情報）に使う。型検査器は after を名前で読む（type_checker.py の 2 か所）。ほかの動詞は見ていない。
  見込み: entity が多く、time は少ない。

行（sys_after.json）。値はどれも 0 か 1。
  "verb 動詞":  time, entity, open, used
  "law 法則":   rule_after

使い方:
  python exp/experiments/sys_after.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def rels(x):
    if isinstance(x, dict):
        if isinstance(x.get("is"), str):
            yield x["is"]
        for v in x.values():
            yield from rels(v)
    elif isinstance(x, list):
        for v in x:
            yield from rels(v)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    own = lambda v: any(r == "after" for k in ("holds", "pre", "post") for r in rels(T.N[v].get(k)))
    used = set()   # ライブラリと領域のすべてのファイルの事実（入れ子の文も含む）に出る動詞
    for name, dom in tc.lib_and_domain_files():
        for f in tc.yload((tc.SPEC / name).read_text(encoding="utf-8")).get("facts") or []:
            used |= {T.resolve(r, dom) or r for r in rels(f)}
    rows = {}
    for v in sorted(T.N):
        if not T.is_verb(v) or not any(own(x) for x in [v] + [a for a in T.ancestors(v) if T.is_verb(a)]):
            continue
        ends = [T.end(v, s) for s in ("from", "to")]
        isa = lambda k: all(e not in (None, "any") and T.is_a(e, k) for e in ends)
        r = {"time": int(isa("occurrent")), "entity": int(isa("continuant"))}
        r["open"] = int(not r["time"] and not r["entity"])
        r["used"] = int(v in used)
        rows[f"verb {tc.short(v)}"] = r
        print(tc.short(v), [tc.short(e) if e else e for e in ends], {k: x for k, x in r.items() if x})
    for lid, l in sorted(O["laws"].items()):
        if any(r == "after" for p in ("assume", "derive", "require") for r in rels(l[p])):
            rows[f"law {lid}"] = {"rule_after": 1}
            print("law", lid)
    vs = [r for k, r in rows.items() if k.startswith("verb ")]
    print({c: f"{sum(r[c] for r in vs)}/{len(vs)}" for c in ("time", "entity", "open", "used")})
    (OUT / "sys_after.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_after.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
