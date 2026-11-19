"""E29: モデルは、概念の表示名から、型検査器が受け付ける cscl の行を書けるか（h_model_can_write_cscl、#58）。

仮説（exp.yaml）: v_speak(model, concept_expression)。
  トリアージ B の先頭。体系（型検査器）に依存するので、検査器の版を固定する: この commit の
  cscl/bootstrap/type_checker/type_checker.py と体系のまま測る。

手順（規則で決める）:
  項目: exp/src/subj.yaml の nodes のうち、mod を持ち、from も axis も持たないもの（種類の定義）を、ファイルの順に並べ、
    0 番目から 3 つおきに取る（72 なら 24）。
  例: 各項目について、同じ並び（mod を持ち from・axis のないもの）で項目より前の 8 つ（先頭なら末尾から回る）を、
    ファイルに書かれたままの行で並べる。項目そのものは例に入れない。
  プロンプト（生のテキスト、チャットの型は使わない）:
    "次は、概念を定義する行の例です。各行の前に、その概念の名前を書きます。\n\n"
    + 例ごとに "名前: <display>\n<行>\n\n"
    + "名前: <項目の display>\n  <項目の識別子>: {"
  生成: Qwen/Qwen2.5-1.5B-Instruct、float32、CPU、貪欲、最大 96 トークン、最初の改行で切る。
    書いた行は "  <識別子>: {" + 生成。
  評価:
    parsed: 書いた行が yaml として読め、識別子の下に dict がある。
    typechecks: 写し（cscl.yaml・cscl・exp/src・exp/tests・exp/experiments/results）の subj.yaml で、項目の元の行を
      書いた行に置き換え、tc.build() の誤りが 0（置き換えない写しの誤りも測り、0 であることを確かめる）。
    extends_match: 書いた行の extends が元の行と同じ。
    exact: extends と mod がどちらも元の行と同じ（yaml として読んだ値で比べる）。
  行（e29_model_writes_cscl.json）: "item <識別子>": {parsed, typechecks, extends_match, exact, n_errors, written（書いた行）}
  要約: n_items, n_parsed, n_typechecks, n_extends_match, n_exact, typecheck_rate, exact_rate, base_errors
判定（事前に決める）: typecheck_rate が 0.5 以上なら支持、0.5 未満なら反証。exact_rate は判定に使わず、あわせて報告する。

開示（結果を見る前に分かっていること）:
  - E10・E11 で、概念式を与えたときモデルが定義に従うかは測ったが、モデルに cscl を書かせたことはない。結果は予想しない。
  - 例は項目の近く（ファイルの順で前）から取るので、似た形の行が例に入りやすい。写しで当てているかは exact で見る。
  - 型検査器が受け付けることは、意味が正しいことではない。意味の近さは extends_match と exact で見る。
使い方:
  python exp/experiments/e29_model_writes_cscl.py
"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SUBJ = "exp/src/subj.yaml"
OUT = ROOT / "exp/experiments/results/e29_model_writes_cscl.json"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
N_EX, STEP, MAX_NEW = 8, 3, 96
HEAD = "次は、概念を定義する行の例です。各行の前に、その概念の名前を書きます。\n\n"

PROBE = r'''
import contextlib, io, json, sys
sys.path[:0] = ["cscl/bootstrap/type_checker"]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    tc.build()
print(json.dumps({"errors": len(tc.errors), "err_text": [str(e) for e in tc.errors[:5]]}, ensure_ascii=False))
'''


def pool_lines():
    text = (ROOT / SUBJ).read_text(encoding="utf-8")
    nodes = yaml.safe_load(text)["nodes"]
    lines = {}
    for ln in text.split("\n"):
        k = ln.strip().split(":", 1)[0]
        if ln.startswith("  ") and not ln.startswith("   ") and k in nodes and k not in lines:
            lines[k] = ln
    pool = [k for k, n in nodes.items() if "mod" in n and "from" not in n and "axis" not in n]
    return text, nodes, pool, lines


def tc_errors(replace=None):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src", "exp/tests", "exp/experiments/results"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        if replace:
            f = Path(d) / SUBJ
            s = f.read_text(encoding="utf-8")
            assert s.count(replace[0] + "\n") == 1, replace[0]
            f.write_text(s.replace(replace[0] + "\n", replace[1] + "\n"), encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        if out.returncode != 0:
            return {"errors": -1, "err_text": [out.stderr[-500:]]}
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(0)
    text, nodes, pool, lines = pool_lines()
    items = pool[::STEP]
    base = tc_errors()
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
    model.eval()
    rows = {}
    t0 = time.time()
    for k in items:
        i = pool.index(k)
        ex = [pool[(i - j) % len(pool)] for j in range(N_EX, 0, -1)]
        prompt = HEAD + "".join(f"名前: {nodes[e].get('display', e)}\n{lines[e]}\n\n" for e in ex)
        prefix = f"  {k}: {{"
        prompt += f"名前: {nodes[k].get('display', k)}\n{prefix}"
        enc = tok(prompt, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.eos_token_id)
        gen = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).split("\n")[0]
        written = prefix + gen
        try:
            got = (yaml.safe_load(written) or {}).get(k)
        except yaml.YAMLError:
            got = None
        parsed = isinstance(got, dict)
        r = tc_errors((lines[k], written)) if parsed else {"errors": -1, "err_text": []}
        gold = nodes[k]
        rows[f"item {k}"] = {"parsed": int(parsed), "typechecks": int(parsed and r["errors"] == 0),
                             "extends_match": int(parsed and got.get("extends") == gold.get("extends")),
                             "exact": int(parsed and got.get("extends") == gold.get("extends") and got.get("mod") == gold.get("mod")),
                             "n_errors": r["errors"], "written": written, "gold": lines[k], "err_text": r["err_text"][:3]}
        print(k, json.dumps({x: rows[f"item {k}"][x] for x in ("parsed", "typechecks", "extends_match", "exact", "n_errors")}),
              f"{time.time() - t0:.0f}s", flush=True)
    R = [v for v in rows.values()]
    n = len(R)
    rows["summary 要約"] = {"n_items": n, **{f"n_{x}": sum(r[x] for r in R) for x in ("parsed", "typechecks", "extends_match", "exact")},
                          "typecheck_rate": sum(r["typechecks"] for r in R) / n, "exact_rate": sum(r["exact"] for r in R) / n,
                          "base_errors": base["errors"]}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "model": MODEL, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rows["summary 要約"], ensure_ascii=False))
    print("判定:", "支持" if rows["summary 要約"]["typecheck_rate"] >= 0.5 else "反証")


if __name__ == "__main__":
    main()
