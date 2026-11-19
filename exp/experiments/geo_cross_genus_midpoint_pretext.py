"""h_midpoint_depends_pretext を確かめる: 日本語をほとんど学んでいないモデルでは、日本語の語から上位概念のまとまりが出ないか。

仮説（exp.yaml）: v_depend(midpoint_membership, pre_model_passage)。
  読み: 上位概念ではまとまり、性質ではまとまらない形は、モデルが前に読んだ文章に依存する。
  ある言語の文章をほとんど読んでいないモデルでは、その言語の語からは、その形が弱まる。

手順（関数と英語の語の表は geo_cross_genus_midpoint_english から、日本語の語の表と率の関数は geo_cross_genus_midpoint から読み込む。
     どちらの main も走らせない）:
  モデル（英語中心。日本語の学習はごく少ない）: HuggingFaceTB/SmolLM2-1.7B-Instruct（24 層）、allenai/OLMo-2-0425-1B-Instruct（16 層）。
  モデルごとに、同じ 120 語を英語（"Word: w"）と日本語（「w）で通し、それぞれで #364 と同じ量を測る
    （G_rate・C_rate・R_rate・diff_GC・perm_p・precondition・holds。層は深さの相対位置 8/28・14/28・20/28）。
  結果を見る前に、2 つのモデルで、どの語も前置きの符号化が先頭で一致し、語の分のトークンが 1 つ以上あることを確かめた。
    日本語の語は、SmolLM2 で平均 4.4 トークン、OLMo-2 で平均 3.0 トークンに分かれる（llm-jp は 1.1、Qwen2.5-1.5B は 1.8）。
  drop = diff_GC（英語）− diff_GC（日本語）。
  行（geo_cross_genus_midpoint_pretext.json）: "model <名前> <en/ja>": {...},
    "summary 要約": {n_judged（英語で holds = 1 のモデルの数）、n_drop（そのうち drop ≥ 0.15 の数）、n_ja_hold（そのうち日本語で holds = 1 の数）、
                     drop_<名前>、verdict（1 = 支持、0 = 反証、2 = mixed、−1 = 未検証）}
判定（事前に決める。判定の層だけで）:
  英語で holds = 1 のモデルだけを判定に使う（その言語を学んだときに、この検査が形を捉えることの確かめ）。n_judged = 0 なら未検証。
  n_drop = n_judged なら支持（読んでいない言語では、どのモデルでも差が 0.15 以上弱まる）。
  n_drop = 0 なら反証（読んでいない言語でも、差は弱まらない）。
  それ以外は mixed。

開示（結果を見る前に分かっていること）:
  - どちらのモデルの学習データにも、日本語はわずかに混じる。「まったく読んでいない」ではなく「ごく少ない」との比べである。
  - 日本語の語は細かいトークン（バイトの断片を含む）に分かれる。同じ文字を共有する語（例: 赤・赤い）が近くなるといった、
    字面からのまとまりが出うる。日本語で差が残った場合、意味ではなく字面による可能性を、この実験では分けられない。
  - 英語と日本語で前置きが違う（"Word: w" と「w）。
  - 多言語の 4 つのモデルでの英語の結果（#366）は、この実験の判定には使わない。
使い方:
  python exp/experiments/geo_cross_genus_midpoint_pretext.py
"""
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/geo_cross_genus_midpoint_pretext.json"
MODELS = [
    ("smollm2", "HuggingFaceTB/SmolLM2-1.7B-Instruct"),
    ("olmo2", "allenai/OLMo-2-0425-1B-Instruct"),
]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"exp/experiments/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    e = module("geo_cross_genus_midpoint_english")
    g = module("geo_cross_genus_midpoint")
    tables = {"en": (e.GENUS, e.CROSS, e.FILLER), "ja": (g.GENUS, g.CROSS, g.FILLER)}
    rows = {}
    for key, name in MODELS:
        tok, model = e.load(name)
        for lang, (genus, cross, filler) in tables.items():
            words = [w for ws in list(genus.values()) + list(cross.values()) for w in ws] + filler
            layers, vec = e.vectors(tok, model, words, lang)
            row = {"model": name, "lang": lang, **e.measure(g.rate, genus, cross, filler, layers, vec)}
            rows[f"model {key} {lang}"] = row
            print(key, lang, json.dumps(row, ensure_ascii=False), flush=True)
        del model
    judged = [k for k, _ in MODELS if rows[f"model {k} en"]["holds"]]
    s = {"n_judged": len(judged)}
    drops = {k: rows[f"model {k} en"]["diff_GC"] - rows[f"model {k} ja"]["diff_GC"] for k, _ in MODELS}
    s["n_drop"] = sum(1 for k in judged if drops[k] >= 0.15)
    s["n_ja_hold"] = sum(rows[f"model {k} ja"]["holds"] for k in judged)
    for k, _ in MODELS:
        s[f"drop_{k}"] = drops[k]
    if not judged:
        s["verdict"] = -1
    elif s["n_drop"] == len(judged):
        s["verdict"] = 1
    elif s["n_drop"] == 0:
        s["verdict"] = 0
    else:
        s["verdict"] = 2
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary", json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
