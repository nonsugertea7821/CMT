"""体系そのものを数える: 体系のファイルのコメントを、決まった規則で種類に分けて数える（棚卸し。予測はしない）。
結果を見る前に、この説明と手順を登録した。

背景（会話）: コメントが定義に効くなら式で書くべきで、効かないなら定義のファイルに置く理由がない。どちらでもコメントの居場所はなく、
  禁止してよいのではないか。禁止する前に、今あるコメントが何を述べているかを数える。
  money の「円」（表示名）と verb_ref の「動詞そのもの」（注釈）は、式の外にあった区別で、式に移すと過大拡張が止まった。

対象: cscl.yaml、cscl/library/*/*.yaml、cscl/design/*.yaml、exp/src/*.yaml。コメントは yaml の字句の外にある # から行末まで
  （文字列の中の # は数えない）。
分け方（上から順に、最初に当てはまるもの）:
  header   見出し: 「=====」か「---」を含むもの、またはファイルの最初のキーより前の行のもの
  history  経緯・観察・根拠: 次の語のどれかを含む: 以前 これまで 消した 替えた 直した 足した 観察 訂正 登録 結果 会話 判定 見込み
           実行の後 sys_ 、または 7 桁以上の 16 進の並び（commit）
  code     コードについて: 型検査 実行器 コード 検査が 検査は .py 翻訳 読む
  meaning  それ以外（意味の説明）
  置き方: inline（値の後ろ）か line（行がコメントだけ）。
数える値: 種類ごと・ファイルごとの数と、置き方ごとの数。

行（sys_comments.json）:
  "summary 要約": total, header, history, code, meaning, inline, line
  "file f":       total, header, history, code, meaning

使い方:
  python exp/experiments/sys_comments.py
"""
import collections
import glob
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
HIST = re.compile(r"以前|これまで|消した|替えた|直した|足した|観察|訂正|登録|結果|会話|判定|見込み|実行の後|sys_|\b[0-9a-f]{7,}\b")
CODE = re.compile(r"型検査|実行器|コード|検査が|検査は|\.py|翻訳|読む")


def comments(p):
    src = Path(p).read_text(encoding="utf-8")
    L = src.split("\n")
    spans = collections.defaultdict(list)
    first_key = None
    for t in yaml.scan(src, Loader=yaml.SafeLoader):
        s, e = t.start_mark, t.end_mark
        if isinstance(t, yaml.KeyToken) and first_key is None:
            first_key = s.line
        for ln in range(s.line, e.line + 1):
            a = s.column if ln == s.line else 0
            b = e.column if ln == e.line else 10 ** 9
            if (a, b) != (0, 0):
                spans[ln].append((a, b))
    out = []
    for i, l in enumerate(L):
        for j, ch in enumerate(l):
            if ch == "#" and not any(a <= j < b for a, b in spans[i]):
                out.append((i, l[j:], "line" if not l[:j].strip() else "inline", first_key))
                break
    return out


def kind(i, text, first_key):
    if "=====" in text or "---" in text or (first_key is not None and i < first_key):
        return "header"
    if HIST.search(text):
        return "history"
    if CODE.search(text):
        return "code"
    return "meaning"


def main():
    files = sorted(["cscl.yaml"] + glob.glob("cscl/library/*/*.yaml") + glob.glob("cscl/design/*.yaml") + glob.glob("exp/src/*.yaml"))
    rows, tot = {}, collections.Counter()
    for f in files:
        c = collections.Counter()
        for i, text, place, fk in comments(ROOT / f):
            k = kind(i, text, fk)
            c[k] += 1
            c["total"] += 1
            tot[k] += 1
            tot[place] += 1
            tot["total"] += 1
        if c:
            rows[f"file {f}"] = {k: c[k] for k in ("total", "header", "history", "code", "meaning")}
    summ = {k: tot[k] for k in ("total", "header", "history", "code", "meaning", "inline", "line")}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_comments.json").write_text(json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for k, v in rows.items():
        print(k, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
