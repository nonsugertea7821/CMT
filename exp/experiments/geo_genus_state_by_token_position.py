"""h_genus_state_by_token_position を確かめる: 隠れ状態が類（extends）に沿う度合いは、語のどのトークン位置を読むかに依存するか。

仮説（exp.yaml）: {v_depend, from: hidden_state, to: [syntax.extends, label_token_positions]}。
  登録（#787）の読み: 平均で読んで反証になった類の測り（#771 など）は、最後のトークンで読むと類に依存する。
  根拠は #782（中点、Qwen L20 で orig の G_rate が平均 0.579、最後のトークン 0.829）。

系列:
  #771（geo_state_by_genus_display）: 動詞の表示語の状態で、類の分かれ G は L8 で orig 0.082、derived 0.108（反証）。
  #782（geo_midpoint_by_token_position）: 中点の帰属は、最後のトークンで読むと L20 で上がる（判定なし）。

手順:
  geo_state_by_genus_display の collect・norm・sep を読み込む（その main は走らせない）。
  動詞と類の選び方は #771 と同じ（親が動詞の集まりにあり、子が 2 つ以上）。顔ぶれは実行のときの main の体系で決まる。
  動詞 v ごとに #771 と同じ 2 つの文字列（orig「<v>」、derived「<親>のうち、<v>」）を通し、
  v の display のトークン位置について 2 通りに読む:
    mean: 位置の平均（#771 と同じ）。
    last: v の display の最後のトークンの位置。
  層 8・14・20。中心化して長さを 1 にそろえ、G = 同じ親の対の余弦の平均 − 違う親の対の余弦の平均。
  帰無: 親のラベルを並べ替えた 2000 回（seed 0）。p_<read>_<cond> = G_perm ≥ G の割合。
判定（事前に決める。L8 の orig で）:
  dep = G_last − G_mean。
  支持: dep ≥ 0.05 かつ p_last_orig ≤ 0.05。
  反証: dep < 0.02。
  その他: 判定しない。
  L14・L20 と derived は記録のみ。

開示（結果を見る前に分かっていること）:
  - #771 の平均の値（L8 orig 0.082）を知っている。体系が #771 の後に変わっているので、顔ぶれと値は同じとは限らない。
  - #782 では、最後のトークンでの上がりは L20 で大きく、L8 では小さかった（swap 0.229 → 0.314）。判定を L8 にしたのは
    #771 と揃えるため。L8 で外れても、L20 で上がる見込みはある（記録のみ）。
  - 表示語の最後のトークンは、語尾（「する」「なる」「の」など）になりやすい。語尾が共通な動詞どうしは、最後のトークンで
    近くなりうる。それは類ではなく字面のまとまりで、G を上げも下げもしうる。
使い方:
  python exp/experiments/geo_genus_state_by_token_position.py
  出力: exp/experiments/results/geo_genus_state_by_token_position.json
"""
import importlib.util
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_genus_state_by_token_position.json"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LAYERS = [8, 14, 20]
JUDGE = 8
N_NULL = 2000


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def vectors(pairs):
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
    model.eval()
    out = {r: {L: [] for L in LAYERS} for r in ("mean", "last")}
    with torch.no_grad():
        for pre, t in pairs:
            p = len(tok("「" + pre, add_special_tokens=False)["input_ids"])
            q = len(tok("「" + pre + t, add_special_tokens=False)["input_ids"])
            assert q > p, (pre, t)
            ids = tok("「" + pre + t + "」", return_tensors="pt", add_special_tokens=False)
            hs = model(**ids, output_hidden_states=True).hidden_states
            for L in LAYERS:
                out["mean"][L].append(hs[L][0, p:q].mean(0))
                out["last"][L].append(hs[L][0, q - 1])
    return {r: {L: torch.stack(v) for L, v in d.items()} for r, d in out.items()}


def main():
    g = module("geo_state_by_genus_display")
    verbs = g.collect()
    kids = {}
    for k, v in verbs.items():
        if v["parent"] in verbs:
            kids.setdefault(v["parent"], []).append(k)
    names = [k for par, ks in sorted(kids.items()) if len(ks) >= 2 for k in ks]
    lab = [verbs[k]["parent"] for k in names]
    V = {"orig": vectors([("", verbs[k]["display"]) for k in names]),
         "derived": vectors([(verbs[verbs[k]["parent"]]["display"] + "のうち、", verbs[k]["display"]) for k in names])}
    res = {"verbs": {k: verbs[k] for k in names}, "n": len(names), "genera": sorted(set(lab)), "layers": {}}
    for L in LAYERS:
        row = {}
        for rd in ("mean", "last"):
            r = {}
            for c in ("orig", "derived"):
                X = g.norm(V[c][rd][L])
                G = g.sep(X, lab)
                rng = random.Random(0)
                null = []
                for _ in range(N_NULL):
                    perm = lab[:]
                    rng.shuffle(perm)
                    null.append(g.sep(X, perm))
                r[c] = {"G": G, "null_mean": sum(null) / N_NULL, "p": sum(x >= G for x in null) / N_NULL}
            row[rd] = r
        row["dep_orig"] = row["last"]["orig"]["G"] - row["mean"]["orig"]["G"]
        row["dep_derived"] = row["last"]["derived"]["G"] - row["mean"]["derived"]["G"]
        res["layers"][str(L)] = row
        print(L, json.dumps(row), flush=True)
    j = res["layers"][str(JUDGE)]
    dep = j["dep_orig"]
    v = ("supported" if dep >= 0.05 and j["last"]["orig"]["p"] <= 0.05 else "refuted" if dep < 0.02 else "not_judged")
    res["judgment"] = {"dep": dep, "p_last_orig": j["last"]["orig"]["p"], "genus_state_by_token_position": v}
    res["rev"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res["model"] = MODEL
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["judgment"]))


if __name__ == "__main__":
    main()
