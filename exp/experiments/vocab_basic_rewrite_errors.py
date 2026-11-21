"""h_basic_vocab_fits の途中記録: 日本語の領域を型検査器に通すまでの書き直しごとの誤りの傾向。

利用者の求め（書き直しの誤りの傾向も記録する。書き手の特徴量として）による。判定には使わない。
入力: results/vocab_basic_ja_draft_tc.txt（下書き。vocab_basic_draft_errors.py で記録済み。走らせ直さない）と、
  results/vocab_basic_ja_rw<n>.yaml（書き直しの各版）。
開示: rw1〜rw3 は、走らせたときにファイルに残していなかったので、手で加えた置き換えを逆にたどって復元した
  （rw3 は書き直し 3 のあとの作業ファイルそのもの）。rw4 からは書いた時点で残す。rw1〜rw3 の型検査器の出力は、
  書いた時点に画面で見た件数（10・2・1）と、このスクリプトが出す件数を行に並べる。
操作: 各版を cscl/library/ja_basic/ja_basic.yaml に置いて型検査器を走らせ、出力を results/vocab_basic_ja_rw<n>_tc.txt に残し、
  誤りを種類に分けて数える（種類の分け方は vocab_basic_draft_errors.py と同じ）。終わったら置く前のファイルに戻す。
  各版について、ja_basic のノードの数と、前の版から書き換わった・消えた・足されたノード。
行: 版ごとの件数、種類ごとの件数、変わったノード。
使い方:
  python exp/experiments/vocab_basic_rewrite_errors.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SEEN = {"rw1": 10, "rw2": 2, "rw3": 1}


def tally(text):
    items = re.split(r"\n - ", "\n" + text.split("\n", 1)[1])[1:] if text.startswith("検査に失敗") else []
    rows = {}
    for it in items:
        it = it.strip()
        m = re.match(r"法則 (\w+)", it)
        if m:
            k = f"law {m.group(1)} ({'ja_basic' if 'ja_basic.' in it else 'other'})"
        else:
            k = "node: " + it.split(": ", 1)[1].split("（")[0] if ": " in it else it
            k = re.sub(r"ja_basic\.\w+", "<ja>", k)
        rows[k] = rows.get(k, 0) + 1
    return len(items), dict(sorted(rows.items(), key=lambda kv: -kv[1]))


def nodes(y):
    return dict(re.findall(r"^  (j_\w+): (.*(?:\n {9,}.*)*)", y, re.M))


def main():
    root = HERE.parents[2]
    R = HERE.parent / "results"
    lib = root / "cscl/library/ja_basic/ja_basic.yaml"
    keep = lib.read_bytes()
    steps = [("draft", R / "vocab_basic_ja_draft.yaml", (R / "vocab_basic_ja_draft_tc.txt").read_text(encoding="utf-8"))]
    vers = sorted(R.glob("vocab_basic_ja_rw*.yaml"), key=lambda p: int(re.search(r"rw(\d+)", p.name).group(1)))
    try:
        for p in vers:
            name = re.search(r"(rw\d+)", p.name).group(1)
            lib.write_bytes(p.read_bytes())
            r = subprocess.run([sys.executable, str(root / "cscl/bootstrap/type_checker/type_checker.py")],
                               cwd=root, capture_output=True, text=True)
            text = r.stdout + r.stderr
            (R / f"vocab_basic_ja_{name}_tc.txt").write_text(text, encoding="utf-8")
            steps.append((name, p, text))
    finally:
        lib.write_bytes(keep)
    rows = {}
    prev = None
    for name, p, text in steps:
        n, kinds = tally(text)
        cur = nodes(p.read_text(encoding="utf-8"))
        row = {"n_errors": n, "n_nodes": len(cur), "kinds": kinds}
        if name in SEEN:
            row["n_errors_seen_when_written"] = SEEN[name]
        if prev is not None:
            row["changed"] = sorted(k for k in cur if k in prev and cur[k] != prev[k])
            row["removed"] = sorted(k for k in prev if k not in cur)
            row["added"] = sorted(k for k in cur if k not in prev)
        rows[name] = row
        prev = cur
    s = {"n_steps": len(steps), "errors_by_step": [rows[k]["n_errors"] for k, _, _ in steps]}
    (R / "vocab_basic_rewrite_errors.json").write_text(
        json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
