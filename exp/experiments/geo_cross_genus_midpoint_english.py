"""h_midpoint_language_invariant を確かめる: 上位概念の集まりと上位をまたぐ性質の集まりの差は、英語の語でも出るか。

仮説（exp.yaml）: lang.v_not_depend(midpoint_membership, natural_language)。
  読み: 上位概念ではまとまり、性質ではまとまらない形（#353・#364、日本語の語）は、言語の表面によらない。
  日本語の語の表を英語に訳し、日本語で測ったのと同じ 4 つのモデルで測る。

手順（ここに書かないことは geo_cross_genus_midpoint_models と同じ。関数はそのスクリプトから読み込み、その main は走らせない）:
  語の表: geo_cross_genus_midpoint の 120 語を、同じ並びのまま英語の 1 語に訳した（下の GENUS・CROSS・FILLER）。
    訳で性質がずれうる語: ポスト → mailbox（英語圏のポストは赤とは限らない）、紅葉 → maple、うどん → noodle、帯 → belt、
    タンス → wardrobe、鏡台 → dresser、みかん → tangerine。
  語の通し方: 文字列 "Word: w" を通し、"Word:" だけの符号化の長さから "Word: w" の符号化の長さまでのトークン位置で平均する。
    日本語の「w とは前置きが違う（英語の語を「 」で囲むのは不自然なため）。
    結果を見る前に、4 つのモデルすべてで、120 語のどれについても "Word: w" の符号化の先頭が "Word:" だけの符号化と一致し、
    w の分のトークンが 1 つ以上あることを確かめた。
  モデル: llm-jp-3-1.8b-instruct、sarashina2.2-1b-instruct-v0.1、Qwen2.5-1.5B-Instruct、Qwen2.5-0.5B-Instruct（#364 と同じ 4 つ。どれも英語も学んでいる）。
  層・率・でたらめの対照・並べ替えの検定・precondition・holds は #364 と同じ。
  行（geo_cross_genus_midpoint_english.json）: "model <名前>": {...#364 と同じ}, "summary 要約": {n_judged, n_hold, diff_<名前>, verdict_support}
判定（事前に決める。判定の層だけで）:
  n_judged（precondition = 1 のモデルの数）= 0 なら、未検証のまま残す。
  n_hold = n_judged なら支持（英語でも、前提を満たすどのモデルでも差が #353 の基準に届く）。
  n_hold < n_judged なら反証。

開示（結果を見る前に分かっていること）:
  - 日本語の 4 つのモデルの結果（#364）はすべて基準に届いた。差は 0.50〜0.64。
  - 英語の語は 1 トークンになりやすく、日本語の語とトークンの数が違う。
  - この判定は 2 つの言語（日本語・英語）だけを比べる。言語一般に依存しないとまでは言えない。
使い方:
  python exp/experiments/geo_cross_genus_midpoint_english.py
"""
import importlib.util
import itertools
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_cross_genus_midpoint_english.json"
MODELS = [
    ("llmjp", "llm-jp/llm-jp-3-1.8b-instruct", "judged"),
    ("sarashina", "sbintuitions/sarashina2.2-1b-instruct-v0.1", "judged"),
    ("qwen15", "Qwen/Qwen2.5-1.5B-Instruct", "judged"),
    ("qwen05", "Qwen/Qwen2.5-0.5B-Instruct", "judged"),
]
GENUS = {
    "動物": ["dog", "cat", "horse", "cow", "elephant", "lion", "rabbit", "bear"],
    "果物": ["apple", "tangerine", "grape", "banana", "peach", "pear", "melon", "watermelon"],
    "乗り物": ["bicycle", "bus", "train", "airplane", "ship", "truck", "taxi", "motorcycle"],
    "楽器": ["piano", "guitar", "violin", "drum", "flute", "trumpet", "harp", "xylophone"],
    "家具": ["chair", "desk", "bed", "shelf", "sofa", "wardrobe", "table", "dresser"],
}
CROSS = {
    "赤いもの": ["strawberry", "tomato", "mailbox", "firetruck", "blood", "sunset", "maple", "goldfish"],
    "丸いもの": ["ball", "moon", "coin", "plate", "donut", "earth", "button", "tire"],
    "柔らかいもの": ["cotton", "pillow", "blanket", "tofu", "sponge", "marshmallow", "feather", "clay"],
    "光るもの": ["sun", "lightbulb", "star", "firefly", "lightning", "jewel", "fireworks", "flashlight"],
    "長いもの": ["river", "snake", "railway", "noodle", "hair", "rope", "belt", "hose"],
}
FILLER = ["school", "hospital", "teacher", "doctor", "time", "music", "math", "history", "rain", "wind",
          "mountain", "sea", "town", "station", "book", "newspaper", "letter", "telephone", "clock", "pencil",
          "shoes", "hat", "clothes", "umbrella", "key", "window", "door", "road", "bridge", "park",
          "rice", "bread", "water", "fire", "stone", "tree", "grass", "flower", "paper", "box"]
FRACS = [8 / 28, 14 / 28, 20 / 28]
PREFIX = {"ja": ("「", ""), "en": ("Word:", " ")}


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load(name):
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.float32)
    model.eval()
    return tok, model


def vectors(tok, model, words, lang):
    pfx, sep = PREFIX[lang]
    N = model.config.num_hidden_layers
    layers = [round(N * f) for f in FRACS]
    pre = tok(pfx, add_special_tokens=False)["input_ids"]
    p = len(pre)
    out = {L: {} for L in layers}
    with torch.no_grad():
        for w in words:
            ids = tok(pfx + sep + w, add_special_tokens=False, return_tensors="pt")["input_ids"]
            q = ids.shape[1]
            assert q > p and ids[0, :p].tolist() == pre, w
            hs = model(ids, output_hidden_states=True).hidden_states
            for L in layers:
                out[L][w] = hs[L][0, p:q].mean(0)
    return layers, out


def mean(xs):
    return sum(xs) / len(xs)


def measure(rate, genus, cross, filler, layers, vec):
    sets = {**{k: v for k, v in genus.items()}, **{k: v for k, v in cross.items()}}
    vocab = [w for ws in sets.values() for w in ws] + filler
    assert len(vocab) == len(set(vocab)) == 120
    idx = {w: i for i, w in enumerate(vocab)}
    names = list(sets)
    J = layers[0]
    rates = {}
    for L in layers:
        X = torch.stack([vec[L][w] for w in vocab])
        X = X - X.mean(0, keepdim=True)
        rates[L] = {k: rate(ws, vocab, X, idx) for k, ws in sets.items()}
        if L == J:
            XJ = X
    G = mean([rates[J][k] for k in genus])
    C = mean([rates[J][k] for k in cross])
    rng = random.Random(0)
    R = mean([rate(rng.sample(vocab, 8), vocab, XJ, idx) for _ in range(200)])
    obs = G - C
    ge = sum(1 for s in itertools.combinations(names, 5)
             if mean([rates[J][k] for k in s]) - mean([rates[J][k] for k in names if k not in s]) >= obs - 1e-12)
    perm_p = ge / 252
    pre = 1 if G - R >= 0.15 else 0
    row = {"layers": layers, "G_rate": G, "C_rate": C, "R_rate": R, "diff_GC": obs, "perm_p": perm_p,
           "precondition": pre, "holds": 1 if pre and obs >= 0.15 and perm_p <= 0.05 else 0}
    for L in layers[1:]:
        row[f"G_rate_L{L}"] = mean([rates[L][k] for k in genus])
        row[f"C_rate_L{L}"] = mean([rates[L][k] for k in cross])
    return row


def main():
    g = module("geo_cross_genus_midpoint")
    words = [w for ws in list(GENUS.values()) + list(CROSS.values()) for w in ws] + FILLER
    rows = {}
    for key, name, role in MODELS:
        tok, model = load(name)
        layers, vec = vectors(tok, model, words, "en")
        del model
        row = {"role": role, "model": name, **measure(g.rate, GENUS, CROSS, FILLER, layers, vec)}
        rows[f"model {key}"] = row
        print(key, json.dumps(row, ensure_ascii=False), flush=True)
    judged = [r for r in rows.values() if r["role"] == "judged" and r["precondition"]]
    s = {"n_judged": len(judged), "n_hold": sum(r["holds"] for r in judged)}
    for key, _, _ in MODELS:
        s[f"diff_{key}"] = rows[f"model {key}"]["diff_GC"]
    s["verdict_support"] = 1 if judged and s["n_hold"] == s["n_judged"] else 0
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
