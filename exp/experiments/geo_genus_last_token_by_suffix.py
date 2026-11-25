"""h_genus_last_token_by_suffix を確かめる: 最後のトークンで読んだときの類の分かれの上がりは、表示語の語尾の共有によるか。

仮説（exp.yaml）: {v_depend, from: hidden_state, to: [syntax.display, label_token_positions]}。
  読み: #792 で、最後のトークンで読むと類の分かれ G が 0.082 → 0.219（L8）に上がった。
  最後のトークンが同じ対は、同じ親の対で 0.198、違う親の対で 0.074。上がりは語尾の共有による。

系列:
  #771（geo_state_by_genus_display）: 平均で読み、L8 orig の G 0.082（反証）。
  #792（geo_genus_state_by_token_position）: 最後のトークンで 0.219、dep 0.136（支持）。

手順:
  geo_state_by_genus_display の collect・norm と、geo_genus_state_by_token_position の vectors を読み込む
  （どちらの main も走らせない）。動詞・類・文字列・層は #792 と同じ（orig と derived、L8・14・20）。
  語尾: 表示語 v を「「v」でトークン化した最後のトークン（#792 の last の位置のトークン）。
  対の集め方 2 つ:
    all: すべての対（#792 と同じ G）。
    excl: 最後のトークンが同じ対を除いた対だけ。
  G_excl = excl の中の同じ親の対の余弦の平均 − excl の中の違う親の対の余弦の平均。
  rise_excl = G_excl(last) − G_excl(mean)。
  帰無: 親のラベルを並べ替えた 2000 回（seed 0）で、excl の対の集め方は固定のまま G_excl(last) を計算。
    p_excl = G_perm ≥ G_excl(last) の割合。
判定（事前に決める。L8 の orig で）:
  支持（語尾による）: rise_excl < 0.02。
  反証（語尾を越えて類がある）: rise_excl ≥ 0.05 かつ p_excl ≤ 0.05。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - #792 の値（all の mean 0.082、last 0.219）と、語尾の同じ対の割合（同じ親 0.198、違う親 0.074）を知っている。
  - 語尾が同じでなくても、語尾が似ている対（「する」と「される」など）は残る。excl は完全な一致だけを除く。
  - 除く対は、同じ親の対のほうが多い（約 2 割）。同じ親の対は 172 → 約 138 に減る。
  - モデルは #792 と同じなので、mean と last の all の値は #792 と一致するはず（記録する）。
使い方:
  python exp/experiments/geo_genus_last_token_by_suffix.py
  出力: exp/experiments/results/geo_genus_last_token_by_suffix.json
"""
import importlib.util
import itertools
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_genus_last_token_by_suffix.json"
JUDGE = 8
N_NULL = 2000


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sep(X, lab, pairs):
    same, diff = [], []
    for a, b in pairs:
        (same if lab[a] == lab[b] else diff).append(float(X[a] @ X[b]))
    return sum(same) / len(same) - sum(diff) / len(diff), len(same), len(diff)


def main():
    g = module("geo_state_by_genus_display")
    t = module("geo_genus_state_by_token_position")
    verbs = g.collect()
    kids = {}
    for k, v in verbs.items():
        if v["parent"] in verbs:
            kids.setdefault(v["parent"], []).append(k)
    names = [k for par, ks in sorted(kids.items()) if len(ks) >= 2 for k in ks]
    lab = [verbs[k]["parent"] for k in names]
    tok = AutoTokenizer.from_pretrained(t.MODEL)
    suf = [tok("「" + verbs[k]["display"], add_special_tokens=False)["input_ids"][-1] for k in names]
    allp = list(itertools.combinations(range(len(names)), 2))
    excl = [(a, b) for a, b in allp if suf[a] != suf[b]]
    V = {"orig": t.vectors([("", verbs[k]["display"]) for k in names]),
         "derived": t.vectors([(verbs[verbs[k]["parent"]]["display"] + "のうち、", verbs[k]["display"]) for k in names])}
    res = {"n": len(names), "suffix": {k: tok.decode([s]) for k, s in zip(names, suf)}, "layers": {}}
    for L in t.LAYERS:
        row = {}
        for c in ("orig", "derived"):
            r = {}
            for rd in ("mean", "last"):
                X = g.norm(V[c][rd][L])
                Ga, ns_a, nd_a = sep(X, lab, allp)
                Ge, ns_e, nd_e = sep(X, lab, excl)
                r[rd] = {"G_all": Ga, "G_excl": Ge, "n_same_excl": ns_e, "n_diff_excl": nd_e}
            X = g.norm(V[c]["last"][L])
            rng = random.Random(0)
            null = []
            for _ in range(N_NULL):
                perm = lab[:]
                rng.shuffle(perm)
                null.append(sep(X, perm, excl)[0])
            r["p_excl"] = sum(x >= r["last"]["G_excl"] for x in null) / N_NULL
            r["rise_all"] = r["last"]["G_all"] - r["mean"]["G_all"]
            r["rise_excl"] = r["last"]["G_excl"] - r["mean"]["G_excl"]
            row[c] = r
        res["layers"][str(L)] = row
        print(L, json.dumps(row), flush=True)
    j = res["layers"][str(JUDGE)]["orig"]
    rise = j["rise_excl"]
    v = ("supported" if rise < 0.02 else "refuted" if rise >= 0.05 and j["p_excl"] <= 0.05 else "not_judged")
    res["judgment"] = {"rise_excl": rise, "p_excl": j["p_excl"], "genus_last_token_by_suffix": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = t.MODEL
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
