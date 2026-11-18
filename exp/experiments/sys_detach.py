"""土台のコードを、定義を変える変異で確かめる: 語の下位を1つ外したとき、型検査と実行器の振る舞いが変わるか。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 名前の付け替え（sys_mutation）で変わらなかった kind・laws・type_checker は、偶然の一致ではなく、
  コードが体系と同じものを、体系から読まずに自分で持っている重複だった（例: コードは law_rule と law_given を名で挙げて法則を集めるが、
  体系では2つは syntax.laws の下位）。重複は名前を変えても見えない。定義を変えて、コードが体系に従うかを見る。
  ここで変える定義は分類（extends）だけ。kind（属するの終点）と type_checker（体系が述べる型検査器そのもの）は、この変異の形では確かめない。

手順（規則で決める）:
  HEAD の作業木を一時の場所に作り（git worktree）、語 w ごとに次をする。
  外す子: w を extends に直に書いたノードのうち、名前の順で最初のもの c（w に子がなければ、その語は行を作らない）。
  変異: c を定義した行（「  c名: {」で始まる1行）の extends の値を、w の上位（Ontology.up、領域を書いた識別子）に替える。
    w に上位がなければ（最上位・any）行を作らない。c の定義が1行でなければ skipped = 1 として走らせない。
  振る舞い: sys_mutation と同じ（型検査と実行器の標準出力と終了コード）。変異の前と比べ、違えば changed = 1。
  語の組（登録の前に決める）:
    test  sys_special.json で outside が 1、short が 0 の語のうち、ノードであるもの。
    neg   sys_mutation の neg と同じ規則で選んだ語（コードのソースに名の出ない、言語の層のノード）。ただし子を持つものだけが行になる。
  読み方: changed = 0 は、その子が w の下にあることが、型検査にも実行器にも効いていないということ。
    コードが名で挙げる語（test）で 0 なら、コードが分類を自分で持っている（体系から読まない）候補。neg の 0 の割合と比べる。
    changed = 1 は、体系（法則）かコードのどちらかが、その分類を読んでいる。どちらが読んだかは、出力の違いで見る。

行（sys_detach.json）。値はどれも 0 か 1。
  "detach 組 語 子":  test_changed / neg_changed、skipped
登録の前に分かっていること（会話）: syntax.laws の子は law_rule と law_given。コードは法則を名で集める。
  見込み: laws の子 law_given を外しても、コードの法則の集め方は変わらない。ただし法則（規則）が分類を読んで誤りを出すかは見ていない。

使い方:
  python exp/experiments/sys_detach.py [作業木の場所]
"""
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import sys_mutation as sm  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def main():
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    wt = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "cmt_detach_wt"
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), commit], cwd=ROOT, check=True)
    try:
        files = {p: p.read_text(encoding="utf-8") for g in sm.GLOBS for p in wt.glob(g)}
        groups = [(g, w) for g, w in sm.words(wt) if g in ("test", "neg")]
        base = sm.behave(wt)
        rows = {}
        for group, w in groups:
            ids = [n for n in T.N if n == w or tc.short(n) == w]
            if len(ids) != 1:
                continue
            nid = ids[0]
            kids = sorted(n for n in T.N if T.N[n].get("extends") == nid)
            up = T.up(nid)
            if not kids or not up:
                continue
            c = kids[0]
            key = f"detach {group} {w} {tc.short(c)}"
            pat = re.compile(r"^  " + re.escape(tc.short(c)) + r": \{.*\bextends: [\w.]+", re.M)
            hit = [(p, s) for p, s in files.items() if pat.search(s)
                   and re.search(r"^domain: " + re.escape(T.domain(c)) + r"\s*$", s, re.M)]
            if len(hit) != 1:
                rows[key] = {"skipped": 1}
                print(group, w, tc.short(c), "skipped")
                continue
            p, s = hit[0]
            line = pat.search(s).group(0)
            new_line = re.sub(r"\bextends: [\w.]+", f"extends: {up}", line)
            p.write_text(s.replace(line, new_line, 1), encoding="utf-8")
            got = sm.behave(wt)
            p.write_text(s, encoding="utf-8")
            ch = int(got != base)
            rows[key] = {f"{group}_changed": ch, "skipped": 0}
            diff = [x for x in got.splitlines() if x not in base.splitlines()][:2]
            print(group, w, "子", tc.short(c), "→", up, "変わった:" if ch else "同じ", diff if ch else "")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT)
    for col in ("test_changed", "neg_changed", "skipped"):
        x = [r[col] for r in rows.values() if col in r]
        print(col, f"{sum(x)}/{len(x)}")
    (OUT / "sys_detach.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_detach.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
