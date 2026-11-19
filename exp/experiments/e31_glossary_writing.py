"""E31: 使える動詞と種類の一覧（用語集）を見せると、モデルが書く cscl の行は、型検査器に受け付けられやすくなるか
（h_glossary_raises_writing）。

仮説（exp.yaml）: v_raise(glossary, formalization_accuracy)。
  E29（#305）で 24 件中 5 件だけが受け付けられ、落ちた行は体系にない動詞・上位を作っていた。
  E30（#308）で、誤りの文を返して書き直させても増えなかった（5 件）。誤りの文は「何がだめか」しか言わない。
  ここでは、書く前に、使える語を見せる。

手順（規則で決める）:
  項目と例とプロンプトの後半は E29 と同じ（同じ 24 件、同じ 8 行の例、同じ HEAD と末尾）。その前に用語集を置く:
    "使える語の一覧です。\n動詞（from → to）:\n" + 動詞ごとに "- <名>（<表示>）: <from の端> → <to の端>\n"
    + "種類:\n" + 種類ごとに "- <名>（<表示>）: 上位 <上位>\n" + "\n" + E29 のプロンプト
  用語集に載せる語:
    tc.build() の体系のノードのうち、層が subj か ontology のもの全部と、subj.yaml の nodes の extends と mod に
    現れる語を subj から解決したもののうち、ほかの層のもの。ただし、その項目自身は載せない（項目ごとに外す）。
    動詞は T.is_verb で分け、端は T.end で読む。名は短い名（tc.short）。表示がなければ名だけ。上位は T.up の短い名
    （ないものは「なし」）。
  生成と評価は E29 と同じ（Qwen/Qwen2.5-1.5B-Instruct、float32、CPU、貪欲、最大 96 トークン、最初の改行で切る。
    写しの subj.yaml で元の行を置き換え、tc.build() の誤りが 0 なら受け付けられた）。体系と検査器は E29 から変わっていない。
  用語集の外の語: 書いた行の extends と mod.of[0] が用語集（項目自身を足したもの）にないなら 1。E29 の行にも同じ数え方をする
    （報告だけ）。
  行（e31_glossary_writing.json）: "item <識別子>": {before, typechecks, extends_match, exact, oov, before_oov, n_errors,
    written, err_text}
  要約: n_items, n_before, n_gl, n_gl_extends_match, n_gl_exact, n_oov, n_before_oov, n_glossary_verbs, n_glossary_kinds,
    base_errors
判定（事前に決める）:
  n_gl が n_before（E29 の 5）より 3 以上多ければ支持。n_gl が n_before 以下なら反証。差が 1 か 2 なら「決まらない」とし、
  仮説は未検証のまま残す。

開示（結果を見る前に分かっていること）:
  - 対照は E29（用語集なし、同じ項目と例と生成の設定）。プロンプトが長くなる効果と、語の中身の効果は分けない。
  - 用語集には、ほかの項目の語（その上位も）が載る。項目自身の名と上位は載らない。項目の元の行が使う動詞と上位は、
    体系にある語なので載る（それが用語集の働き）。
  - 用語集の語の選びは、subj.yaml が実際に使う語でほかの層のものを足すので、ファイルが使う語に寄る。
  - 結果は予想しない。
使い方:
  python exp/experiments/e31_glossary_writing.py
"""
import contextlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e29_model_writes_cscl import HEAD, MAX_NEW, MODEL, N_EX, pool_lines, tc_errors  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
E29 = ROOT / "exp/experiments/results/e29_model_writes_cscl.json"
OUT = ROOT / "exp/experiments/results/e31_glossary_writing.json"


def words_in(x, out):
    if isinstance(x, str):
        out.add(x)
    elif isinstance(x, dict):
        for v in x.values():
            words_in(v, out)
    elif isinstance(x, list):
        for v in x:
            words_in(v, out)


def glossary(nodes):
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    used = set()
    for n in nodes.values():
        words_in(n.get("extends"), used)
        words_in(n.get("mod"), used)
    qs = [q for q in T.N if q.split(".")[0] in ("subj", "ontology")]
    for w in sorted(used):
        try:
            q = T.resolve(w, "subj")
        except Exception:
            q = None
        if q in T.N and q not in qs:
            qs.append(q)
    S = tc.short
    verbs, kinds = {}, {}
    for q in qs:
        d = T.N[q].get("display")
        name = S(q) + (f"（{d}）" if d else "")
        if T.is_verb(q):
            verbs[S(q)] = f"- {name}: {S(T.end(q, 'from'))} → {S(T.end(q, 'to'))}\n"
        else:
            u = T.up(q)
            kinds[S(q)] = f"- {name}: 上位 {S(u) if u else 'なし'}\n"
    return verbs, kinds


def oov(got, vocab):
    if not isinstance(got, dict):
        return 1
    ws = [got.get("extends")]
    m = got.get("mod")
    if isinstance(m, dict) and isinstance(m.get("of"), list) and m["of"]:
        ws.append(m["of"][0])
    return int(any(not isinstance(w, str) or w not in vocab for w in ws))


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(0)
    prev = json.loads(E29.read_text(encoding="utf-8"))["rows"]
    text, nodes, pool, lines = pool_lines()
    verbs, kinds = glossary(nodes)
    base = tc_errors()
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
    model.eval()
    rows = {}
    t0 = time.time()
    for key, p in prev.items():
        if not key.startswith("item "):
            continue
        k = key[len("item "):]
        gl = ("使える語の一覧です。\n動詞（from → to）:\n" + "".join(v for w, v in verbs.items() if w != k)
              + "種類:\n" + "".join(v for w, v in kinds.items() if w != k) + "\n")
        vocab = set(verbs) | set(kinds) | {k}
        i = pool.index(k)
        ex = [pool[(i - j) % len(pool)] for j in range(N_EX, 0, -1)]
        prefix = f"  {k}: {{"
        prompt = gl + HEAD + "".join(f"名前: {nodes[e].get('display', e)}\n{lines[e]}\n\n" for e in ex) \
            + f"名前: {nodes[k].get('display', k)}\n{prefix}"
        enc = tok(prompt, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.eos_token_id)
        written = prefix + tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).split("\n")[0]
        try:
            got = (yaml.safe_load(written) or {}).get(k)
        except yaml.YAMLError:
            got = None
        try:
            pgot = (yaml.safe_load(p["written"]) or {}).get(k)
        except yaml.YAMLError:
            pgot = None
        parsed = isinstance(got, dict)
        r = tc_errors((lines[k], written)) if parsed else {"errors": -1, "err_text": []}
        gold = nodes[k]
        rows[key] = {"before": p["typechecks"], "typechecks": int(parsed and r["errors"] == 0),
                     "extends_match": int(parsed and got.get("extends") == gold.get("extends")),
                     "exact": int(parsed and got.get("extends") == gold.get("extends") and got.get("mod") == gold.get("mod")),
                     "oov": oov(got, vocab), "before_oov": oov(pgot, vocab), "n_errors": r["errors"],
                     "written": written, "err_text": r["err_text"][:3], "prompt_tokens": int(enc["input_ids"].shape[1])}
        print(k, json.dumps({x: rows[key][x] for x in ("before", "typechecks", "exact", "oov", "before_oov", "prompt_tokens")}),
              f"{time.time() - t0:.0f}s", flush=True)
    R = list(rows.values())
    s = {"n_items": len(R), "n_before": sum(r["before"] for r in R), "n_gl": sum(r["typechecks"] for r in R),
         "n_gl_extends_match": sum(r["extends_match"] for r in R), "n_gl_exact": sum(r["exact"] for r in R),
         "n_oov": sum(r["oov"] for r in R), "n_before_oov": sum(r["before_oov"] for r in R),
         "n_glossary_verbs": len(verbs), "n_glossary_kinds": len(kinds), "base_errors": base["errors"]}
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    d = s["n_gl"] - s["n_before"]
    print("判定:", "支持" if d >= 3 else "反証" if d <= 0 else "決まらない")


if __name__ == "__main__":
    main()
