"""h_state_by_genus_display を確かめる: 表示語を「類の語 ＋ 種差」で組むと、隠れ状態は類（extends）に沿ってまとまるか。

仮説（exp.yaml）: {v_depend, from: hidden_state, to: [syntax.extends, syntax.display]}。
  登録（#763）の読み: 状態は式より字面に沿う（#756 ほか）ので、字面を類から組み立てれば、状態は類に沿う。

系列:
  #756（geo_refer_ops_share_direction）: v_refer の下の動詞は、表示語の隠れ状態で共通の向きを持たない（反証）。
  h_state_unique_display・h_expression_makes_state_unique も反証。

手順:
  モデル Qwen/Qwen2.5-1.5B-Instruct（ローカルのキャッシュ、float32、CPU）。チャットの雛形は使わない。
  動詞の集まりは #756 と同じ取り方（collect を写す）。親 = extends の値（接頭辞を除く）。
  類 = 親が動詞の集まりの中にあり、子が 2 つ以上ある親。その子だけを使う。
  動詞 v ごとに 2 つの文字列を通す:
    orig    「<v の display>」
    derived 「<親の display>のうち、<v の display>」
  どちらも、v の display のトークン位置だけで層 L の隠れ状態を平均する（類の語の位置は平均に入れない）。
  判定に使う層は L=8。層 14、20 も記録だけする。
  条件ごとに、使う動詞の平均を引き（中心化）、長さを 1 にそろえる。
  G = 同じ親の対の余弦の平均 − 違う親の対の余弦の平均。
  帰無: derived の行列で親のラベルを並べ替えたもの 2000 回（seed 0）の G。p = G_perm ≥ G_derived の割合。
判定（事前に決める。L8 だけで）:
  up = G_derived − G_orig。
  支持: up ≥ 0.10 かつ p ≤ 0.05。
  反証: up < 0.05。
  その他: 判定しない。

開示（結果を見る前に分かっていること）:
  - derived では、同じ親の子は同じ前置き（親の表示語）を共有する。文脈が状態に入るので、G が上がる見込みは高い。
    この実験が測るのは「字面を類に合わせれば状態が類に沿うか」で、式そのものを状態が読むかではない。
  - 類の語の位置は平均に入れないが、語が重なる表示語（「述べる」「部分になる」など）は orig でもまとまる見込みがある。
  - 動詞の数と顔ぶれは、実行のときの main の体系で決まる。
  - E56（4B）の後に走らせる（重い列は一度に 1 つ）。
使い方:
  python exp/experiments/geo_state_by_genus_display.py
  出力: exp/experiments/results/geo_state_by_genus_display.json
"""
import glob
import itertools
import json
import os
import random
import re
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_state_by_genus_display.json"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LAYERS = [8, 14, 20]
JUDGE = 8
N_NULL = 2000


def collect():
    files = [ROOT / "cscl.yaml"]
    for pat in ("cscl/library/**/*.yaml", "cscl/design/*.yaml", "exp/src/*.yaml"):
        files += sorted(Path(p) for p in glob.glob(str(ROOT / pat), recursive=True))
    verbs = {}
    for f in files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^  (v_[a-z_0-9]+): (\{.*\})\s*$", line)
            if not m or m.group(1) in verbs:
                continue
            try:
                d = yaml.safe_load(m.group(2))
            except yaml.YAMLError:
                continue
            if isinstance(d, dict) and isinstance(d.get("display"), str):
                verbs[m.group(1)] = {"display": d["display"], "parent": str(d.get("extends", "")).split(".")[-1]}
    return verbs


def vectors(pairs):
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
    model.eval()
    out = {L: [] for L in LAYERS}
    with torch.no_grad():
        for pre, t in pairs:
            p = len(tok("「" + pre, add_special_tokens=False)["input_ids"])
            q = len(tok("「" + pre + t, add_special_tokens=False)["input_ids"])
            ids = tok("「" + pre + t + "」", return_tensors="pt", add_special_tokens=False)
            hs = model(**ids, output_hidden_states=True).hidden_states
            for L in LAYERS:
                out[L].append(hs[L][0, p:q].mean(0))
    return {L: torch.stack(v) for L, v in out.items()}


def norm(V):
    X = V - V.mean(0)
    return X / X.norm(dim=1, keepdim=True)


def sep(X, lab):
    same, diff = [], []
    for a, b in itertools.combinations(range(len(lab)), 2):
        (same if lab[a] == lab[b] else diff).append(float(X[a] @ X[b]))
    return sum(same) / len(same) - sum(diff) / len(diff)


def main():
    verbs = collect()
    kids = {}
    for k, v in verbs.items():
        if v["parent"] in verbs:
            kids.setdefault(v["parent"], []).append(k)
    names = [k for par, ks in sorted(kids.items()) if len(ks) >= 2 for k in ks]
    lab = [verbs[k]["parent"] for k in names]
    O = vectors([("", verbs[k]["display"]) for k in names])
    D = vectors([(verbs[verbs[k]["parent"]]["display"] + "のうち、", verbs[k]["display"]) for k in names])
    res = {"verbs": {k: verbs[k] for k in names}, "n": len(names), "genera": sorted(set(lab)), "layers": {}}
    for L in LAYERS:
        Xo, Xd = norm(O[L]), norm(D[L])
        go, gd = sep(Xo, lab), sep(Xd, lab)
        rng = random.Random(0)
        null = []
        for _ in range(N_NULL):
            perm = lab[:]
            rng.shuffle(perm)
            null.append(sep(Xd, perm))
        res["layers"][str(L)] = {"G_orig": go, "G_derived": gd, "up": gd - go,
                                 "null_mean": sum(null) / N_NULL, "p": sum(x >= gd for x in null) / N_NULL}
    j = res["layers"][str(JUDGE)]
    v = "supported" if j["up"] >= 0.10 and j["p"] <= 0.05 else "refuted" if j["up"] < 0.05 else "not_judged"
    res["judgment"] = {"up": j["up"], "p": j["p"], "state_by_genus_display": v}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["layers"], indent=1))
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
