"""E30: 型検査の誤りを返すと、モデルが書き直した cscl の行は、型検査器に受け付けられやすくなるか（h_typecheck_feedback_raises_writing、#90）。

仮説（exp.yaml）: v_raise(type_check_result, formalization_accuracy)。
  トリアージ B の 2 つ目。E29（#305）の続き。E29 では 24 件中 5 件だけが受け付けられた（体系にない動詞・上位を作る）。
  先行研究（Poiroux et al. 2024）は、型検査を通らない候補を捨てる（選ぶ）形で正しさを上げた。ここでは選ぶのではなく、
  誤りの文を返して書き直させる。

手順（規則で決める）:
  項目: E29 と同じ 24 件。E29 の結果ファイル（e29_model_writes_cscl.json）から、書いた行と誤りの文を読む（E29 は走らせない）。
  E29 で受け付けられた項目（typechecks=1）は書き直さず、どの条件でも受け付けられたと数える。
  受け付けられなかった項目ごとに、E29 と同じプロンプト（同じ 8 行の例と HEAD）の後に、次を足して 1 回だけ書き直させる:
    条件 fb（誤りを返す）:
      "名前: <display>\n<E29 で書いた行>\n型検査の誤り: <E29 の err_text を ' / ' でつなぐ>\n書き直した行:\n  <識別子>: {"
    条件 ctl（誤りを返さない対照）:
      "名前: <display>\n<E29 で書いた行>\n型検査の誤り: この行は受け付けられなかった。\n書き直した行:\n  <識別子>: {"
  生成と評価は E29 と同じ（Qwen/Qwen2.5-1.5B-Instruct、float32、CPU、貪欲、最大 96 トークン、最初の改行で切る。
    写しの subj.yaml で元の行を置き換え、tc.build() の誤りが 0 なら受け付けられた）。型検査器は E29 と同じ版のものを使う
    （この commit の体系と検査器。E29 から体系の subj.yaml は変わっていない）。
  行（e30_typecheck_feedback.json）: "item <識別子>": {before, fb_typechecks, ctl_typechecks, fb_extends_match,
    ctl_extends_match, fb_exact, ctl_exact, fb_written, ctl_written, fb_err_text, ctl_err_text}
  要約: n_items, n_before, n_fb, n_ctl（受け付けられた数、E29 で受け付けられた分を含む）, n_fb_exact, n_ctl_exact,
    n_fb_extends_match, n_ctl_extends_match, base_errors
判定（事前に決める）:
  n_fb が n_ctl より 3 以上多く、かつ n_before より多ければ支持。n_fb が n_ctl 以下なら反証。
  そのあいだ（n_fb - n_ctl が 1 か 2）は「決まらない」とし、仮説は未検証のまま残す。

開示（結果を見る前に分かっていること）:
  - E29 の誤りの文は各項目で最大 3 つまで記録されている。誤りの文のなかには、項目でなく、項目を参照するほかのノードの誤り
    （たとえば agent を変えると subj.age が落ちる）がある。そのまま返す。
  - 誤りの文は体系の名前（subj.agent など、層の付いた名）を含む。どの動詞と上位があるかの一覧は与えない
    （それは h_glossary_raises_writing の側）。
  - 書き直しは 1 回だけ。結果は予想しない。
使い方:
  python exp/experiments/e30_typecheck_feedback.py
"""
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
OUT = ROOT / "exp/experiments/results/e30_typecheck_feedback.json"
CTL_MSG = "この行は受け付けられなかった。"


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(0)
    prev = json.loads(E29.read_text(encoding="utf-8"))["rows"]
    text, nodes, pool, lines = pool_lines()
    base = tc_errors()
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
    model.eval()

    def write(prompt, prefix, k):
        enc = tok(prompt, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.eos_token_id)
        written = prefix + tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).split("\n")[0]
        try:
            got = (yaml.safe_load(written) or {}).get(k)
        except yaml.YAMLError:
            got = None
        parsed = isinstance(got, dict)
        r = tc_errors((lines[k], written)) if parsed else {"errors": -1, "err_text": []}
        gold = nodes[k]
        return {"typechecks": int(parsed and r["errors"] == 0),
                "extends_match": int(parsed and got.get("extends") == gold.get("extends")),
                "exact": int(parsed and got.get("extends") == gold.get("extends") and got.get("mod") == gold.get("mod")),
                "written": written, "err_text": r["err_text"][:3]}

    rows = {}
    t0 = time.time()
    for key, p in prev.items():
        if not key.startswith("item "):
            continue
        k = key[len("item "):]
        row = {"before": p["typechecks"]}
        if p["typechecks"]:
            for c in ("fb", "ctl"):
                row |= {f"{c}_typechecks": 1, f"{c}_extends_match": p["extends_match"], f"{c}_exact": p["exact"],
                        f"{c}_written": p["written"], f"{c}_err_text": []}
        else:
            i = pool.index(k)
            ex = [pool[(i - j) % len(pool)] for j in range(N_EX, 0, -1)]
            prompt = HEAD + "".join(f"名前: {nodes[e].get('display', e)}\n{lines[e]}\n\n" for e in ex)
            prefix = f"  {k}: {{"
            msgs = {"fb": " / ".join(p["err_text"]), "ctl": CTL_MSG}
            for c, msg in msgs.items():
                q = prompt + f"名前: {nodes[k].get('display', k)}\n{p['written']}\n型検査の誤り: {msg}\n書き直した行:\n{prefix}"
                w = write(q, prefix, k)
                row |= {f"{c}_{x}": v for x, v in w.items()}
        rows[key] = row
        print(k, json.dumps({x: row[x] for x in ("before", "fb_typechecks", "ctl_typechecks", "fb_exact", "ctl_exact")}),
              f"{time.time() - t0:.0f}s", flush=True)
    R = list(rows.values())
    s = {"n_items": len(R), "n_before": sum(r["before"] for r in R)}
    for c in ("fb", "ctl"):
        s[f"n_{c}"] = sum(r[f"{c}_typechecks"] for r in R)
        s[f"n_{c}_extends_match"] = sum(r[f"{c}_extends_match"] for r in R)
        s[f"n_{c}_exact"] = sum(r[f"{c}_exact"] for r in R)
    s["base_errors"] = base["errors"]
    rows["summary 要約"] = s
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    d = s["n_fb"] - s["n_ctl"]
    print("判定:", "支持" if d >= 3 and s["n_fb"] > s["n_before"] else "反証" if d <= 0 else "決まらない")


if __name__ == "__main__":
    main()
