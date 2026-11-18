"""体系そのものを数える: 持続体と生起体を、self・same とフレームの変化から導いたものと、今の体系の置き場を比べる。仮説 h_tops_derivable の確かめ。
結果を見る前に、この説明と手順を登録した。

導いた定義（利用者と決めた。生起体は D2）:
  持続体  どのフレームでも自分と同じであるもの（∀t, t'. same(self_t, self_t')）。宣言は減らないので、宣言された個体は持続体。
  生起体  前後のフレームを同じでなくするもの（¬same(frame_t, frame_t+1)）。動詞では、pre か post を持つ（自分か上位が）動的な動詞。
          静的な動詞（holds だけ）はフレームを変えないので、生起体ではない（関係）。
  概念    語が引き起こす推論（今の定義）。生起体なら、フレームを変える（宣言を在るようにする）中身を持つ。

行（sys_tops.json）。値はどれも 0 か 1。
  "individual 個体":  ind_continuant   個体の種類が持続体の下にある
  "verb 動詞":        dynamic          動的な動詞である（自分か上位が pre か post を持つ）
                      dyn_occurrent    動的な動詞のときだけ: 生起体の下にある
                      static_occurrent 静的な動詞のときだけ: 生起体の下にある（D2 では 0 であるべき）
  "noun ノード":      生起体の下にある、動詞でないノードだけ。
                      reaches_dynamic  否定でない定義の辺（sys_layers.edges）をたどって、動的な動詞に届く
  "concept":          concept_dynamic  ontology.concept が、否定でない定義の辺をたどって、動的な動詞に届く
  summary 行: supported

仮説 h_tops_derivable: 体系の持続体と生起体の置き場は、self・same とフレームの変化から導いたものと一致する。
判定（登録した基準）: 次のすべてが成り立てば支持、どれかが破れれば反証。
  ind_continuant の平均 1.0、dyn_occurrent の平均 1.0、static_occurrent の平均 0.0、reaches_dynamic の平均 1.0、concept_dynamic が 1。
登録の前に分かっていること（会話の中で数えた）: 個体 1052 はすべて持続体の下にある。動詞 118 はすべて生起体の下にあり、
  動的な動詞は 16 前後（sys_frames）なので、static_occurrent は 0 にならない見込み。concept は sys_layers で refer（変化に届かない）だった。
  だから反証が見込まれる。目的は、導いた定義と今の体系の食い違いを記録し、そこから直すものを導くこと。

使い方:
  python exp/experiments/sys_tops.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import sys_layers  # noqa: E402

OUT = ROOT / "exp/experiments/results"
CON, OCC = "ontology.continuant", "ontology.occurrent"


def is_dynamic(T, n):
    x = n
    while x in T.N:
        if "pre" in T.N[x] or "post" in T.N[x]:
            return True
        if T.N[x].get("extends") not in T.N:
            return False
        x = T.N[x]["extends"]
    return False


def reaches_dynamic(T, n):
    seen, todo = {n}, [n]
    while todo:
        x = todo.pop()
        if T.is_verb(x) and is_dynamic(T, x):
            return True
        for b in sys_layers.edges(T, x, True):
            if b not in seen:
                seen.add(b)
                todo.append(b)
    return False


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = {}
    for i, k in sorted(T.I.items()):
        if k in T.N:
            rows[f"individual {i}"] = {"ind_continuant": int(T.is_a(k, CON))}
    for n in sorted(T.N):
        occ = T.is_a(n, OCC)
        if T.is_verb(n):
            d = is_dynamic(T, n)
            rows[f"verb {n}"] = {"dynamic": int(d)} | ({"dyn_occurrent": int(occ)} if d else {"static_occurrent": int(occ)})
        elif occ and n != OCC:
            rows[f"noun {n}"] = {"reaches_dynamic": int(reaches_dynamic(T, n))}
    rows["concept"] = {"concept_dynamic": int(reaches_dynamic(T, "ontology.concept"))}
    mean = lambda c: (lambda v: sum(v) / len(v) if v else None)([r[c] for r in rows.values() if c in r])
    supported = (mean("ind_continuant") == 1.0 and mean("dyn_occurrent") == 1.0 and mean("static_occurrent") == 0.0
                 and mean("reaches_dynamic") == 1.0 and rows["concept"]["concept_dynamic"] == 1)
    rows["summary"] = {"supported": int(supported)}
    cols = ["ind_continuant", "dynamic", "dyn_occurrent", "static_occurrent", "reaches_dynamic", "concept_dynamic"]
    for c in cols:
        v = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(v)}/{len(v)}")
    print("生起体の名詞で動的な動詞に届かないもの:", [k for k, r in rows.items() if r.get("reaches_dynamic") == 0])
    (OUT / "sys_tops.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_tops.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("判定:", "支持" if supported else "反証")


if __name__ == "__main__":
    main()
