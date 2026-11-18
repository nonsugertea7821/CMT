"""土台のコードを変異で確かめる: 語の名前を一貫して付け替えたとき、型検査と実行器の振る舞いが変わるか。
結果を見る前に、この説明と手順を登録した。仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話）: 文法は syntax が定義し、コード（.py）は機械語に翻訳しているに過ぎない、という見方。翻訳なら、体系の語の名前を
  どこでも一貫して付け替えても（α変換）、振る舞いは名前を戻せば同じになるはず。変わるなら、コードがその名前で分岐している
  （定義を読まず、名前に意味を持たせている）。sys_special は文字列を拾っただけで、組み立てた名前（f"..."）を拾えなかった。変異はそれも見える。
  片側の確かめ: 変わる ⇒ 名前に依存している。変わらない ⇏ 依存していない（今の体系の入力で表に出ないだけかもしれない）。

手順（規則で決める）:
  HEAD の作業木を一時の場所に作り（git worktree）、語ごとに次をする。
  付け替え: 範囲のファイル（cscl.yaml が読む YAML: cscl/library/**/*.yaml、cscl/design/*.yaml、exp/src/*.yaml、exp/tests/*.yaml）で、
    語（領域を除いた名前）を、前後が英数字・_ でない所すべてで mut_<語> に替える（コメントも替わる。害はない）。
  振る舞い: 型検査（type_checker.py）と実行器（runtime.py）を走らせ、標準出力と終了コードを取る。出力の mut_<語> を <語> に戻し、
    付け替えない場合の出力と比べる。違えば changed = 1。
  語の組（どれも登録の前に決める）:
    test  sys_special.json で outside が 1、short が 0 の語（一字の語を除く、シグネチャでも文法でもない語）。
    pos   文法の語のうちコードが名を挙げたもの: holds, extends, verbatim, many（陽性の対照。変わると見込む）。
    neg   言語の層（ontology, syntax, runtime, std）のノードの名のうち、型検査・実行器・exp_check.py のソースに、
          前後が英数字・_ でない形で一度も出てこないもの。名前の順に並べ、20 個おきに取る（陰性の対照。変わらないと見込む）。
  exp の結果ファイル（JSON）は付け替えない。結果ファイルの名や条件の綴りと重なる語は、付け替えで exp の検査が落ちうる。
    test と neg は言語の層の語が多く、重なりは少ないと見込むが、重なったものは changed になる（偽の陽性）。出力の違いで見分けられる。

行（sys_mutation.json）。値はどれも 0 か 1。
  "word 組 語":  test_changed / pos_changed / neg_changed   付け替えで振る舞いが変わった
登録の前に分かっていること（会話）: sys_special の一覧。付け替えた体系を走らせたことはない。1回の型検査は約4秒。

使い方:
  python exp/experiments/sys_mutation.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
PY = sys.executable
GLOBS = ["cscl/library/**/*.yaml", "cscl/design/*.yaml", "exp/src/*.yaml", "exp/tests/*.yaml"]
POS = ["holds", "extends", "verbatim", "many"]
SOURCES = ["cscl/bootstrap/type_checker/type_checker.py", "cscl/bootstrap/runtime/runtime.py", "exp/src/exp_check.py"]


def tok(w):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(w) + r"(?![A-Za-z0-9_])")


def behave(wt):
    out = []
    for f in ("cscl/bootstrap/type_checker/type_checker.py", "cscl/bootstrap/runtime/runtime.py"):
        r = subprocess.run([PY, f], cwd=wt, capture_output=True, text=True)
        out.append(f"{f} {r.returncode}\n{r.stdout}")
    return "\n".join(out)


def words(wt):
    sp = json.loads((ROOT / "exp/experiments/results/sys_special.json").read_text(encoding="utf-8"))["rows"]
    test = sorted(k.split(" ", 1)[1].split(".")[-1] for k, r in sp.items() if r["outside"] and not r["short"])
    test = sorted(set(test))
    src = "\n".join((ROOT / s).read_text(encoding="utf-8") for s in SOURCES)
    lib = set()
    for g in ["cscl/library/**/*.yaml"]:
        for p in sorted(wt.glob(g)):
            for line in p.read_text(encoding="utf-8").splitlines():
                m = re.match(r"  ([A-Za-z_]\w*): \{", line)
                if m:
                    lib.add(m.group(1))
    cand = sorted(w for w in lib if not tok(w).search(src) and w not in POS and w not in test)
    neg = cand[::20]
    return [("test", w) for w in test] + [("pos", w) for w in POS] + [("neg", w) for w in neg]


def main():
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    wt = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "cmt_mutation_wt"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), commit], cwd=ROOT, check=True)
    try:
        files = {p: p.read_text(encoding="utf-8") for g in GLOBS for p in wt.glob(g)}
        base = behave(wt)
        rows = {}
        for group, w in words(wt):
            t, new = tok(w), f"mut_{w}"
            for p, s in files.items():
                p.write_text(t.sub(new, s), encoding="utf-8")
            got = tok(new).sub(w, behave(wt))
            for p, s in files.items():
                p.write_text(s, encoding="utf-8")
            ch = int(got != base)
            rows[f"word {group} {w}"] = {f"{group}_changed": ch}
            if ch:
                diff = [x for x in got.splitlines() if x not in base.splitlines()][:2]
                print(group, w, "変わった:", diff)
            else:
                print(group, w, "同じ")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT)
    for c in ("test_changed", "pos_changed", "neg_changed"):
        x = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(x)}/{len(x)}")
    (OUT / "sys_mutation.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_mutation.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
