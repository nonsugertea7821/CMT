"""体系の外の事実（このリポジトリの git の履歴）で、std.v_compute と exp.v_speak を見分ける。結果を見る前に、この説明と手順を登録した。
仮説の確かめではない（判定の基準を置かない）。観察として記録する。方法は sys_confusion と同じ（履歴の出来事を個体と歩みにして、読みごとに歩む）。

背景: v_compute の to を continuant にし post に depend(to, from) を足すと、式が v_speak と同じになった（会話）。
  今の2つの式の違いは、v_speak の post の depend(to, from)（作られたものは作ったものに依存する）だけ。
  この違いが見えるのは法則 depend_end_exists（依存する始点が在れば終点も在る）を通してだけ。他の動詞の pre が読む depend は、
  始点が役割・実現体・性質のときだけで、作られた情報には当たらない（会話で確かめた）。
  だから、作ったものが在らなくなった後も、作られたものが在り続ける出来事があれば、v_speak の読みでだけ法則が破れる。

データ（規則で決める）:
  HEAD の履歴（git log --reverse -M --name-status、古い順）。
  作られたもの: パスに "results/" を含む .json。A でファイルの個体を作る。R は引き継ぐ。D でその exists を取り除く。M は扱わない
    （同じファイルの計算し直しは sys_confusion で扱った混同で、ここでは作る出来事だけを見る）。
  作ったもの: そのファイルが A で足された版の内容の _source（パス）。_source のない版は数えない。
    .py のパスとして履歴にあれば、A（R で入ったものを含む）の時点で個体を作り exists を述べる。R は引き継ぐ。D で exists を取り除く。
    _source が、その時点で在る .py のパスでなければ、そのファイルの A の時点で個体を作る（source_in_git を 0 にする）。
  種類: 作られたものは exp.result_file、作ったものは exp.code。
  歩み: ファイルの A ごとに、読み C は std.v_compute(from: 作ったもの, to: ファイル)、読み S は exp.v_speak(同じ束縛)。
  実行器は open_runtime.OpenMachine（在るようにする位置で名前を宣言する）。D のたびに法則を確かめる（check_laws）。

行（sys_outlive.json）。値はどれも 0 か 1。
  "delete パス 番号":   c_ok, s_ok        その D の後に、法則の誤りが増えなかった（読み C、読み S）
  "file 番号 パス":     outlives_source   そのファイルが在る間に、作ったものが D で在らなくなったことがある
                        source_in_git     作ったものが、その時点で履歴にある .py だった
  "step 番号 パス":     c_step_ok, s_step_ok  作る歩みがエラーなく歩めた

登録の前に分かっていること: sys_confusion の数（結果ファイルの A は 99）。スクリプトの D の数や、作られたものが作ったものより長く残るかは数えていない。
見込み: 作ったものが消えてもファイルが残る出来事があれば、読み S の delete 行で s_ok が 0 になる。読み C では破れない。

使い方:
  python exp/experiments/sys_outlive.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/runtime"), str(Path(__file__).parent)]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
    import open_runtime  # noqa: E402

OUT = ROOT / "exp/experiments/results"
FILE, SRC = "exp.result_file", "exp.code"
READINGS = {"c": "std.v_compute", "s": "exp.v_speak"}


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def is_result(p):
    return "results/" in p and p.endswith(".json")


def source(commit, path):
    try:
        s = json.loads(git("show", f"{commit}:{path}")).get("_source")
    except (json.JSONDecodeError, AttributeError):
        return None
    return s if isinstance(s, str) else None


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit_head = git("rev-parse", "HEAD").strip()
    M = {k: open_runtime.OpenMachine(T, {"individuals": {}, "facts": []}, k) for k in READINGS}
    py, res = {}, {}            # パス → 個体の名前
    made_by, gone_src = {}, set()
    rows, n, j, commit = {}, 0, 0, None

    def declare(name, kind):
        for m in M.values():
            m.ind[name] = kind
            m.facts[("exists", (name,))] = True

    def remove(name, where):
        nonlocal j
        j += 1
        errs = {k: len(m.errors) for k, m in M.items()}
        for m in M.values():
            m.facts.pop(("exists", (name,)), None)
            m.check_laws(where)
        return {f"{k}_ok": int(len(m.errors) == errs[k]) for k, m in M.items()}

    for line in git("log", "--reverse", "-M", "--format=C %H", "--name-status").splitlines():
        if line.startswith("C "):
            commit = line[2:]
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        st, paths = parts[0], parts[1:]
        if st.startswith("R"):
            old, new = paths
            for table in (py, res):
                if old in table:
                    table[new] = table.pop(old)
            if new.endswith(".py") and new not in py:
                n += 1
                py[new] = f"src{n}"
                declare(py[new], SRC)
            if is_result(new) and new not in res:
                st, paths = "A", [new]   # 結果の外から入ったファイルは、ここで作られたとみなす
            else:
                continue
        p = paths[0]
        if p.endswith(".py"):
            if st == "A":
                n += 1
                py[p] = f"src{n}"
                declare(py[p], SRC)
            elif st == "D" and p in py:
                name = py.pop(p)
                gone_src.add(name)
                for f, s in made_by.items():
                    if s == name and ("exists", (f,)) in M["c"].facts:
                        rows[f"file {f}"]["outlives_source"] = 1
                rows[f"delete {p} {j}"] = remove(name, f"{commit[:7]} D {p}")
        elif is_result(p):
            if st == "A":
                s = source(commit, p)
                if s is None:
                    continue
                n += 1
                f = f"res{n}"
                res[p] = f
                in_git = s in py
                if not in_git:
                    n += 1
                    py.setdefault(f"(外){s}#{n}", f"src{n}")
                    sname = f"src{n}"
                    declare(sname, SRC)
                else:
                    sname = py[s]
                made_by[f] = sname
                rows[f"file {f}"] = {"outlives_source": 0, "source_in_git": int(in_git), "_path": p}
                ok = {}
                for k, m in M.items():
                    e = len(m.errors)
                    m.step(READINGS[k], {"from": sname, "to": f}, f"{commit[:7]} A {p}")
                    ok[f"{k}_step_ok"] = int(len(m.errors) == e)
                rows[f"step {n} {p}"] = ok
            elif st == "D" and p in res:
                f = res.pop(p)
                for m in M.values():
                    m.facts.pop(("exists", (f,)), None)
    for r in rows.values():
        r.pop("_path", None)
    for c in ("c_ok", "s_ok", "outlives_source", "source_in_git", "c_step_ok", "s_step_ok"):
        v = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(v)}/{len(v)}")
    for k, m in M.items():
        print(k, "誤りの例:", m.errors[:2])
    (OUT / "sys_outlive.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_outlive.py", "_commit": commit_head, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
