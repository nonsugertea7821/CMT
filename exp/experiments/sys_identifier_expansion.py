"""h_identifier_by_expansion を確かめる: 概念をシグネチャの語まで展開すると、違う識別子は違う展開になるか。

仮説（claims.yaml）: v_depend(syntax.identifier, signature_class)。
  登録（6044c82）の読み: 識別子は、シグネチャに展開した概念式で定まる。表示語はそこから訳した名前になり、
  いずれ独立の置き場としては消える。確かめ方の候補は、全概念をシグネチャの語まで展開し、展開が一致する対を数えること。

手順（体系のファイルは変えない。tc.build() の T.N を読むだけ）:
  展開 E(q):
    ノードの値から display と gloss を除き、残りの値を再帰でたどる。
    文字列が T.N のノードなら、そのノードの展開 E に置き換える（名前は残さない）。
    文字列が T.N のノードでなければ（基礎の関係・位置・文法の語・値）、そのまま残す。
    辞書は鍵の順に、並びは要素を正規の形にして並べ替えて比べる（並びの順は区別しない）。
    たどる途中で、たどっている最中のノードにまた来たら（循環）、そこを "CYCLE" に置き換える。
    比べるのは展開の正規の形のハッシュ（sha256）。
  集計:
    n_nodes          T.N のノードの数
    n_classes        展開のハッシュの種類の数
    n_collide_class  2 つ以上の識別子が同じ展開になる組（類）の数
    n_collide_nodes  そうした類に入る識別子の数
    n_empty          展開が空（display と gloss のほかに何も持たない）のノードの数
    n_cycle          展開の途中で循環に出会ったノードの数
  行（sys_identifier_expansion.json）: "class <i>": {size, members}（類ごと、大きい順）、"summary 要約": {...}
判定（事前に決める）: n_collide_class が 0 なら支持。1 以上なら反証。

開示（結果を見る前に分かっていること）:
  - h_appear_root（#322）で、v_design と v_compute は出現の形のほかに式の差がないと分かった。
    ただし to の種類（continuant と any）が違うので、この展開では別になる見込み。
  - 型検査は「動詞の式が同じ」を、動詞の枠と端の名前（展開しない）で調べている。展開すると、
    名前は違うが中身が同じ端を持つ動詞が、新たに一致しうる。
  - 上位を持たず display だけのノード（根）があれば、それらはどれも空に展開され、互いに一致する。
    そうしたノードがいくつあるかは数えていない。
  - 循環のあるノードでは、展開がたどり始めた場所によって変わりうる（"CYCLE" を置く位置が違う）。
    この版はそれを正さない。
  - 型検査は 1 回だけ（軽い）。
使い方:
  python exp/experiments/sys_identifier_expansion.py
"""
import collections
import contextlib
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_identifier_expansion.json"
DROP = ("display", "gloss")


def main():
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    base_errors = len(tc.errors)
    N = T.N
    memo, stack, hit_cycle = {}, [], set()

    def canon(x):
        if isinstance(x, str):
            return E(x) if x in N else json.dumps(x, ensure_ascii=False)
        if isinstance(x, dict):
            return "{" + ",".join(f"{json.dumps(k)}:{canon(v)}" for k, v in sorted(x.items())) + "}"
        if isinstance(x, list):
            return "[" + ",".join(sorted(canon(v) for v in x)) + "]"
        return json.dumps(x)

    def E(q):
        if q in memo:
            return memo[q]
        if q in stack:
            for s in stack[stack.index(q):]:
                hit_cycle.add(s)
            return '"CYCLE"'
        stack.append(q)
        body = {k: v for k, v in N[q].items() if k not in DROP}
        h = "#" + hashlib.sha256(canon(body).encode()).hexdigest()[:20]
        stack.pop()
        memo[q] = h
        return h

    by = collections.defaultdict(list)
    for q in sorted(N):
        by[E(q)].append(q)
    empty = sum(1 for q in N if not {k for k in N[q] if k not in DROP})
    classes = sorted((v for v in by.values() if len(v) > 1), key=lambda v: (-len(v), v))
    rows = {f"class {i}": {"size": len(v), "members": v} for i, v in enumerate(classes)}
    s = {"n_nodes": len(N), "n_classes": len(by), "n_collide_class": len(classes),
         "n_collide_nodes": sum(len(v) for v in classes), "n_empty": empty, "n_cycle": len(hit_cycle),
         "base_errors": base_errors, "verdict_support": int(not classes)}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in classes[:30]:
        print(len(v), v[:8])
    print(json.dumps(s, ensure_ascii=False))
    print("判定:", "支持" if not classes else "反証")


if __name__ == "__main__":
    main()
