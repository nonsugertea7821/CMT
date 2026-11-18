"""仮説 h_comment_ban（に依存しない(定義, 注釈)）を確かめる: 体系のファイルに残るコメントをすべて消しても、
定義から失われるものはないか。失われるもの（式にない定義の中身）は、式に移せるか。
結果を見る前に、この説明と手順と判定を登録した（issue #143）。

対象: 版 a7a1943 の体系のファイル（cscl.yaml、cscl/library、cscl/design、exp/src の yaml）に残るコメント。
  コメントの取り出しは sys_comments.py と同じ（yaml の字句の外にある # から行末まで）。
  この版では cscl.yaml の 14 行と cscl/design/claims.yaml の 281 行の、計 295 行（登録の前に数えた）。
分け方（一行ずつ。一人（Claude）が読んで付ける。表は sys_comment_ban_labels.json に、登録の後に書く）:
  head    見出し: 後に続く行のまとまりに名前を付けるもの、またはファイルの役目を述べるもの
  record  記録: 実験や決定の手順・結果・実行の後の読み・出どころ（利用者の問い、会話）・予定
  code    コード: 型検査器・実行器・道具がすることを述べるもの
  para    言い換え: 体系の式（仮説の中身など）を言い直すだけのもの
  defn    定義: 体系のどの式も述べていない、言語や概念についての中身。言い換えのうち式より多くを言う部分と、
          仮説を結果の前に立てたか後に立てたかを含む
  迷ったら、消して失われるものが大きい側（defn > para > code > record > head）に付ける。
扱い: すべての行を消す。defn は、同じ変更の中で式に移す。移した先を表の to に書く（移せないなら "left" と書き、
  その行はコメントとして残す）。record と head と code は、元の文が git の履歴に残り、手順はスクリプトの説明に、
  数は結果のファイルにあるので、移さない。record が名を挙げるスクリプトが今あるかを数えて確かめる。
数える量（要約。行の鍵と重ならない名前にする）:
  n_total, n_head, n_record, n_code, n_para, n_defn  表の行の数（n_total は版 a7a1943 のコメントの数）
  n_unlabeled      表にない行の数（0 でなければ手順の誤り）
  n_defn_formal    defn のうち式に移した数。n_defn_left = n_defn − n_defn_formal
  n_after          今の作業ツリーの体系のファイルに残るコメントの数
  n_script_missing record が名を挙げる exp/experiments/*.py のうち、今ないものの数
  errors           今の体系の型検査の誤りの数
判定（ec が通るもとで）:
  n_unlabeled = 0, errors = 0, n_defn_left = 0, n_after = 0 なら支持（v_support）。
  n_defn_left > 0 なら反証（v_contradict）: 今の式では書けない定義の中身が注釈にある。
見込み（開示）: 登録の前に 295 行をすべて読んだ。大半は record と head で、支持の見込みが高い。
  defn の候補として見えたのは、h_open_declaration の言い換えの後半（各時点では宣言＝存在で閉じている）、
  h_definition_positive と h_neg_not_self の「観察の後に立てた」、h_tops_derivable の持続体と生起体の定義、
  cscl.yaml の層の説明。式に移すときに概念を足すかもしれない（足せば手で見る PR になる）。
  分けるのも移すのも一人の判断で、外の基準ではない。

行（sys_comment_ban.json）:
  "summary 要約": 上の数
  "class <k>": n（その種類の行の数）, formal（式に移した数。defn のほか 0）
  "texts": 行ごとの元の文、種類、移した先（記述）

使い方:
  python exp/experiments/sys_comment_ban.py
"""
import collections
import contextlib
import glob
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
LABELS = ROOT / "exp/experiments/sys_comment_ban_labels.json"
BASE = "a7a1943"
KINDS = ("head", "record", "code", "para", "defn")
SCRIPT = re.compile(r"exp/experiments/([A-Za-z0-9_]+\.py)")


def comments(src):
    L = src.split("\n")
    spans = collections.defaultdict(list)
    for t in yaml.scan(src, Loader=yaml.SafeLoader):
        s, e = t.start_mark, t.end_mark
        for ln in range(s.line, e.line + 1):
            a = s.column if ln == s.line else 0
            b = e.column if ln == e.line else 10 ** 9
            if (a, b) != (0, 0):
                spans[ln].append((a, b))
    out = []
    for i, l in enumerate(L):
        for j, ch in enumerate(l):
            if ch == "#" and not any(a <= j < b for a, b in spans[i]):
                out.append((i + 1, l[j:]))
                break
    return out


def files_at(rev):
    ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", rev], cwd=ROOT, capture_output=True, text=True).stdout.split()
    pat = re.compile(r"^(cscl\.yaml|cscl/library/.*\.ya?ml|cscl/design/.*\.ya?ml|exp/src/.*\.ya?ml)$")
    return sorted(f for f in ls if pat.match(f))


def main():
    base = {}
    for f in files_at(BASE):
        src = subprocess.run(["git", "show", f"{BASE}:{f}"], cwd=ROOT, capture_output=True, text=True).stdout
        for ln, text in comments(src):
            base[f"{f}:{ln}"] = text
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    unl = [k for k in base if k not in labels or labels[k].get("k") not in KINDS]
    cnt, formal = collections.Counter(), collections.Counter()
    missing = set()
    for k in base:
        lb = labels.get(k, {})
        c = lb.get("k")
        if c not in KINDS:
            continue
        cnt[c] += 1
        if c == "defn" and lb.get("to") and lb["to"] != "left":
            formal[c] += 1
        if c == "record":
            for s in SCRIPT.findall(base[k]):
                if not (ROOT / "exp/experiments" / s).exists():
                    missing.add(s)
    now = 0
    for f in sorted(["cscl.yaml"] + glob.glob("cscl/library/*/*.yaml", root_dir=ROOT) + glob.glob("cscl/design/*.yaml", root_dir=ROOT)
                    + glob.glob("exp/src/*.yaml", root_dir=ROOT)):
        now += len(comments((ROOT / f).read_text(encoding="utf-8")))
    with contextlib.redirect_stdout(io.StringIO()):
        tc.build()
    errors = len(tc.errors)
    summ = {"n_total": len(base), **{f"n_{c}": cnt[c] for c in KINDS}, "n_unlabeled": len(unl),
            "n_defn_formal": formal["defn"], "n_defn_left": cnt["defn"] - formal["defn"], "n_after": now,
            "n_script_missing": len(missing), "errors": errors}
    rows = {f"class {c}": {"n": cnt[c], "formal": formal[c]} for c in KINDS}
    texts = {k: {"text": base[k], "k": labels.get(k, {}).get("k"), "to": labels.get(k, {}).get("to")} for k in base}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_comment_ban.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts, "unlabeled": unl,
                    "script_missing": sorted(missing)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
