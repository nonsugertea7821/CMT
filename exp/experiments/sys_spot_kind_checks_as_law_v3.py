"""h_spot_kind_checks_as_law の 3 版目: 2版目で一度も出なかった K3（相手が動詞でない）を、それが働く位置だけで確かめる。

2版目（sys_spot_kind_checks_as_law_v2.py、結果 results/sys_spot_kind_checks_as_law_v2.json）:
  404 件すべて一致、K1 42・K2 3 を対応する法則がすべて名指した（C = 1）。K3 は before で 0 回で、事前登録どおり判定しなかった。
  結果を見た後に読んだこと: K3 が働くのは、限定の相手の側の端の種類が ontology.verb_ref の下のときだけ。
  体系の範囲（cscl.yaml の root・library・include）で、端に verb_ref を持つ動詞は std.v_close だけ（to: verb_ref。下位の動詞はない）。
  v_close を限定に使うのは、std.yaml の 2 か所: composable_set の {of: [v_close, from], with: v_sum} と、closed_set の {of: [v_close, from]}（相手なし）。
  2版目は 10 に 1 つの選び方で、どちらも選ばなかった。また、2版目の材料の 236 件は cscl/trial/ の下で、型検査器の範囲の外だった。

手（2版目と同じ）: before は今の木、after は 2版目と同じ patch（sys_spot_kind_checks_as_law_v2 の NODES・FACTS と、K1〜K3 の err を pass に）。

材料（モデルは走らせない。std.yaml の 2 か所だけ）:
  S1: composable_set の「of: [v_close, from], with: v_sum」の with の名を、次に替える。
      ind: 個体 ontology.var1、kind: 種類 ontology.kind、modnode: 名前を付けた限定 ontology.not_before_from、
      verb: 動詞 ontology.v_rely、verb2: 動詞 std.v_close（自分の動詞）。
      ほかに new: 位置を new に替える（K1）。
  S2: closed_set の「of: [v_close, from]」の後ろに「, with: <名>」を足す。名は S1 の ind・kind・modnode・verb・verb2 と、元の S1 の相手 v_sum。
  合わせて 12 件。1 件ずつ、ほかは元のままの写しで type_checker.py を before と after で走らせる。
  受け入れ・退け・壊れの分け方、一致・不一致、覆い（K3→verb_ref_with_verb_from か _to、K1→mod_new_no_with、K2→is_from_with_concept）は 2版目と同じ。

判定（事前登録）:
  A は走らせない（patch は 2版目と同じで、2版目の A は前後とも通った）。
  前提: before で K3 が 1 度以上出ること。出なければ判定しない。12 件のうち両方が走ったものが 10 未満なら判定しない。
  h_spot_kind_checks_as_law（2版目と合わせて決める）:
    この 12 件の不一致が 0、かつ 12 件の覆い C3 = 1（K3 だけでなく、出た K の文すべて）なら支持（2版目の A・B の一致、K1・K2 の C = 1 と合わせて）。
    不一致が 1 以上なら反証。
    不一致が 0 で C3 < 1 なら決まらない。

開示（結果を見る前に分かっていること）:
  - 2版目の結果をすべて見ている。
  - 端に verb_ref を持つ動詞が v_close だけであることは、体系の yaml を grep して読んだ（to: verb_ref・from: verb_ref と、v_close の下位）。
  - 見込み: コードの is_verb は「from と to の端を持つ（上位から受け継ぐのも含む）」、法則の r_two_ends は r_end_from と r_end_to から出る。
    名前を付けた限定（modnode）は of を持ち、from・to を持たないので、どちらも動詞でないとする見込み。確かめていない。
  - 支持でも、K3 について言えるのは、体系に 1 つしかない動詞の位置での一致。位置が増えたときの一致ではない。

出力: results/sys_spot_kind_checks_as_law_v3.json
使い方:
  python exp/experiments/sys_spot_kind_checks_as_law_v3.py
"""
import json
import tempfile
import time
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_spot_kind_checks_as_law_v2 as v2

v1 = v2.v1
OUT = v1.ROOT / "exp/experiments/results/sys_spot_kind_checks_as_law_v3.json"
F = "cscl/library/std/std.yaml"
S1 = "of: [v_close, from], with: v_sum"
S2 = "of: [v_close, from]}"
NAMES = (("ind", "ontology.var1"), ("kind", "ontology.kind"), ("modnode", "ontology.not_before_from"),
         ("verb", "ontology.v_rely"), ("verb2", "std.v_close"))


def tasks(text):
    assert text.count(S1) == 1, "S1"
    s2 = [i for i in range(len(text)) if text.startswith(S2, i)]
    assert len(s2) == 1, "S2"
    out = [("S1", p, S1, S1.replace("with: v_sum", "with: " + v)) for p, v in NAMES]
    out.append(("S1", "new", S1, S1.replace(", from], with:", ", new], with:")))
    out += [("S2", p, S2, S2[:-1] + ", with: " + v + "}") for p, v in NAMES + (("orig", "v_sum"),)]
    return out


def main():
    t0 = time.time()
    rows = []
    with tempfile.TemporaryDirectory() as td:
        trees = {}
        for side in ("before", "after"):
            trees[side] = Path(td) / side
            trees[side].mkdir()
            v1.ws.copy_tree(trees[side])
        v1.patch(trees["after"])
        text = (trees["before"] / F).read_text(encoding="utf-8")
        for site, probe, old, new in tasks(text):
            res = {"site": site, "probe": probe, "old": old, "new": new}
            for side, tree in trees.items():
                p = tree / F
                orig = p.read_text(encoding="utf-8")
                assert orig.count(old) == 1
                p.write_text(orig.replace(old, new), encoding="utf-8")
                try:
                    r = v1.ws.run(tree, v1.TC)
                finally:
                    p.write_text(orig, encoding="utf-8")
                res[side] = {"verdict": v1.ws.verdict(r), "errors": r["errors"], "secs": r["secs"], "stderr": r["stderr"]}
            rows.append(res)
            print("B", site, probe, res["before"]["verdict"], res["after"]["verdict"], flush=True)
    status, k_before, k_covered = Counter(), Counter(), Counter()
    for r in rows:
        b, a = r["before"]["verdict"], r["after"]["verdict"]
        r["status"] = ("not_run" if b == a == "broke" else "agree" if b == a else
                       "missed" if (b, a) == ("reject", "accept") else "over" if (b, a) == ("accept", "reject") else "broke")
        status[r["status"]] += 1
        la = v1.laws(r["after"]["errors"])
        for k in v1.ks(r["before"]["errors"]):
            k_before[k] += 1
            if la & set(v1.K_LAWS[k]):
                k_covered[k] += 1
    n_ran = len(rows) - status["not_run"]
    n_disagree = status["missed"] + status["over"] + status["broke"]
    n_k = sum(k_before.values())
    C = sum(k_covered.values()) / n_k if n_k else None
    summary = {"n_tasks": len(rows), "n_ran": n_ran, "n_agree": status["agree"], "n_missed": status["missed"],
               "n_over": status["over"], "n_broke": status["broke"], "n_not_run": status["not_run"], "n_disagree": n_disagree,
               "n_k3_before": k_before["K3"], "n_k3_covered": k_covered["K3"],
               "k_before": dict(k_before), "k_covered": dict(k_covered), "C": C,
               "secs": round(time.time() - t0, 1)}
    if k_before["K3"] == 0 or n_ran < 10:
        judgment = "not_judged"
    elif n_disagree > 0:
        judgment = "refute"
    elif C == 1:
        judgment = "support"
    else:
        judgment = "undecided"
    OUT.write_text(json.dumps({"summary": summary, "judgment": {"h_spot_kind_checks_as_law": judgment}, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps({"h_spot_kind_checks_as_law": judgment}))


if __name__ == "__main__":
    main()
