"""仮説 h_w_from_frames（依存する(最上位の置き場, 後の状態の痕跡)）を確かめる: 持続体と生起体の置き場が、
フレームの変化の痕跡（pre・post の有無と宣言）から決まるか。結果を見る前に、この説明と手順と判定を登録した（issue #152）。

類比（commit 702414b）: 点（持続体, w=1）は、どのフレームでも同じであるもの。変位（生起体, w=0）は、フレームを
動かすもの。静的な座標（修飾 mod）からは決まらない（sys_above_sound の zero）。holds だけの動詞は点でも変位でもない
第三のもの（関係）。

痕跡から導く分類（名前・表示語・最上位への extends は読まない）:
  宣言された個体             点。宣言は減らないので、どのフレームでも在る。
  動詞で、自分か上位が pre か post を持つ（sys_tops.is_dynamic）   変位
  動詞で、holds だけ          関係（第三の分類。仮説がそう予言するので、生起体の下にあっても食い違いに数えない）
  動詞でないノード           否定でない定義の辺（sys_layers.edges）をたどって動的な動詞に届けば変位、届かなければ点
                            （sys_tops.reaches_dynamic と同じ）。

今の置き場: ontology.continuant の下か ontology.occurrent の下か（T.is_a）。どちらの下にもないもの、最上位そのものは除く。

行（sys_w_from_frames.json）。値はどれも 0 か 1。
  "individual <i>":  ind_point     個体の種類が持続体の下にある
  "verb <n>":        dyn_occ       動的な動詞のときだけ: 生起体の下にある
                     relation      静的な動詞のときだけ: 1（関係の数を数えるための記述）
  "con <n>":         con_point     持続体の下の、動詞でないノード: 痕跡から点と導かれる（動的な動詞に届かない）
  "occ <n>":         occ_move      生起体の下の、動詞でないノード: 痕跡から変位と導かれる（動的な動詞に届く）
  "summary 要約":     n_ind, n_dyn, n_static, n_con, n_occ, n_untopped（どちらの下にもない、動詞でないノードの数）, errors

判定（ec が通るもとで。どの率も、その列の平均）:
  ind_point, dyn_occ, con_point, occ_move のすべてが 0.9 以上なら支持（v_support）。
  どれかが 0.5 未満なら反証（v_contradict）: 今の置き場は、フレームの痕跡では決まっていない。
  そのほかは mixed。

登録の前に分かっていること（開示）:
  sys_tops（h_tops_derivable、反証）で、同じ is_dynamic と reaches_dynamic を使って数えた。個体はすべて持続体の下、
  動的な動詞はすべて生起体の下だった。生起体の下の名詞 49 のうち多くは動的な動詞に届かなかった（subj.day・week・
  morning のような時間の区間、ontology.process・temporal_part、ontology.concept など）。だから occ_move は 0.5 未満の
  見込みで、反証が見込まれる。持続体の下の名詞（con_point）は、まだ数えていない。
  この実験が sys_tops に足すのは、静的な動詞を食い違いでなく第三の分類として扱うこと、持続体の側も痕跡で導くこと、
  判定を率の閾値にしたこと。分類の規則は sys_tops から変えていない（結果に合わせて規則を選ばないため）。

使い方:
  python exp/experiments/sys_w_from_frames.py
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
    from sys_tops import is_dynamic, reaches_dynamic  # noqa: E402

OUT = ROOT / "exp/experiments/results"
CON, OCC = "ontology.continuant", "ontology.occurrent"


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    errors = len(tc.errors)
    if errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows, untopped = {}, []
    for i, k in sorted(T.I.items()):
        if k in T.N:
            rows[f"individual {i}"] = {"ind_point": int(T.is_a(k, CON))}
    for n in sorted(T.N):
        if n in (CON, OCC):
            continue
        if T.is_verb(n):
            if is_dynamic(T, n):
                rows[f"verb {n}"] = {"dyn_occ": int(T.is_a(n, OCC))}
            else:
                rows[f"verb {n}"] = {"relation": 1}
            continue
        con, occ = T.is_a(n, CON), T.is_a(n, OCC)
        if con and not occ:
            rows[f"con {n}"] = {"con_point": int(not reaches_dynamic(T, n))}
        elif occ and not con:
            rows[f"occ {n}"] = {"occ_move": int(reaches_dynamic(T, n))}
        else:
            untopped.append(n)
    col = lambda c: [r[c] for r in rows.values() if c in r]
    rate = lambda c: (sum(col(c)) / len(col(c))) if col(c) else None
    cols = ("ind_point", "dyn_occ", "con_point", "occ_move")
    rs = {c: rate(c) for c in cols}
    if all(v is not None and v >= 0.9 for v in rs.values()):
        verdict = "支持"
    elif any(v is None or v < 0.5 for v in rs.values()):
        verdict = "反証"
    else:
        verdict = "mixed"
    rows["summary 要約"] = {"n_ind": len(col("ind_point")), "n_dyn": len(col("dyn_occ")), "n_static": len(col("relation")),
                          "n_con": len(col("con_point")), "n_occ": len(col("occ_move")), "n_untopped": len(untopped),
                          "errors": errors}
    (OUT / "sys_w_from_frames.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_w_from_frames.py", "_commit": commit, "rows": rows,
         "untopped": untopped,
         "con_moving": [k[4:] for k, r in rows.items() if r.get("con_point") == 0],
         "occ_still": [k[4:] for k, r in rows.items() if r.get("occ_move") == 0]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print({c: (round(v, 4) if v is not None else None) for c, v in rs.items()})
    print("判定:", verdict)


if __name__ == "__main__":
    main()
