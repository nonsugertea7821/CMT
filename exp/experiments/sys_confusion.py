"""体系の外の事実（このリポジトリの git の履歴）で、動詞の位置の混同を観察する。結果を見る前に、この説明と手順を登録した。
仮説の確かめではない（判定の基準を置かない）。観察として記録する。

背景（会話で立てた定義の候補）:
  動詞 v の定義 F（位置についての pre・post の文）が、位置 p に置かれた b について成り立たない。
  ところが F が成り立つ c があり、基礎の関係 R で R(c, b) が成り立つ。このとき、その使い方は v でなく v∘R（p を R に沿ってずらした動詞）で、
  混同とは v∘R を v の名前で書くこと。F が成り立つかは個体の水準でしか決まらず、在るかどうかは体系の外の事実が要る。
  体系の在るようにする位置に置かれる個体は this_design の1つだけだった（会話で数えた）ので、個体を外の事実から作る。

データ（規則で決める。個々に選ばない）:
  このリポジトリの HEAD の履歴（git log --reverse -M --name-status、コミットの古い順）で、パスに "results/" を含む .json のファイル。
  A（足す）でファイルの個体を1つ作る。R（名前の変更）は同じ個体を引き継ぐ。D（消す）はパスを個体から外す（歩みは作らない）。
  M（書き換える）とA は「計算の出来事」1つ。
  体系の語彙がこのファイルに与える種類: exp.result_file（extends passage_compute_to、つまり v_compute の終点）。
  計算するもの: その版の内容の _source（なければ unknown_source）。種類は exp.code。最初から在る（exists を述べる）。
  版の個体（読み S だけ）: 種類は exp.row_collection（information_entity_compose_from_result_file、つまり結果ファイルの部分）。
    R は、体系の語彙が版の種類とファイルの種類を結ぶ関係から取る: compose_from result_file なので part。

2つの読み（実行器は open_runtime.OpenMachine。開世界で、在るようにする位置で名前を宣言する）:
  V（今の語彙のまま）: 計算の出来事ごとに、歩み std.v_compute(from: 計算するもの, to: ファイル)。
  S（終点を part に沿ってずらす）: A のとき、ファイルを在るものとして宣言する（exists を述べる。ファイルを何が作るかは S は述べない）。
     計算の出来事ごとに、新しい版の個体 c を作る歩み std.v_compute(from: 計算するもの, to: c)、そのあと part(c, ファイル) を述べる。

行（sys_confusion.json）。値はどれも 0 か 1。
  "v パス 番号 種別": v_a_ok（A の出来事）か v_m_ok（M の出来事）。V で、その歩みがエラーなく歩めた。
  "s パス 番号 種別": s_a_ok か s_m_ok。S で、その歩みがエラーなく歩めた。
  "file 番号 パス":   recomputed（M の出来事が1つ以上ある）

登録の前に分かっていること（会話で数えた）: 履歴に A 76、M 41、R100 74 がある。
  V では、M の出来事でファイルがすでに在るので pre の ¬exists(to) が破れ、S では版が毎回新しいので破れない、と作りから見込まれる。
  登録の前の確かめ: 構文と、events() の数だけを見た（A 99、M 39、ファイル 99）。A が 76 より多いのは、results の外から名前を変えて入ったファイルを A として数えるため。
  経験的な中身は、計算の出来事のうち M（同じファイルを計算し直す）がどれだけあるか（recomputed）と、実行器が見込みどおりに動くか。

使い方:
  python exp/experiments/sys_confusion.py
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
FILE, VER, SRC = "exp.result_file", "exp.row_collection", "exp.code"


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def events():
    """(コミット, 種別 A|M, ファイルの番号, パス) を古い順に。"""
    out, path_id, n, commit = [], {}, 0, None
    for line in git("log", "--reverse", "-M", "--format=C %H", "--name-status").splitlines():
        if line.startswith("C "):
            commit = line[2:]
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        st, paths = parts[0], parts[1:]
        if not any("results/" in p and p.endswith(".json") for p in paths):
            continue
        if st.startswith("R"):
            old, new = paths
            if old in path_id:
                path_id[new] = path_id.pop(old)
            elif "results/" in new and new.endswith(".json"):
                n += 1
                path_id[new] = n
                out.append((commit, "A", n, new))
            if st != "R100":
                out.append((commit, "M", path_id[new], new))
        elif st == "A":
            n += 1
            path_id[paths[0]] = n
            out.append((commit, "A", n, paths[0]))
        elif st == "M" and paths[0] in path_id:
            out.append((commit, "M", path_id[paths[0]], paths[0]))
        elif st == "D":
            path_id.pop(paths[0], None)
    return out


def source(commit, path):
    try:
        s = json.loads(git("show", f"{commit}:{path}")).get("_source")
    except (json.JSONDecodeError, AttributeError):
        s = None
    return f"src:{s}" if isinstance(s, str) else "unknown_source"


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        O = tc.load(tc.root_name())
        for _, name in tc.register_domains(O):
            tc.merge_domain(name, O)
        T = tc.Ontology(O)
    commit = git("rev-parse", "HEAD").strip()
    ev = [(c, k, i, p, source(c, p)) for c, k, i, p in events()]
    srcs = sorted({e[4] for e in ev})
    run = {"individuals": {s: {"is": SRC} for s in srcs}, "facts": [{"is": "exists", "from": s} for s in srcs]}
    V, S = open_runtime.OpenMachine(T, run, "V"), open_runtime.OpenMachine(T, run, "S")
    rows, files = {}, {}
    for j, (c, k, i, p, s) in enumerate(ev):
        f = f"file{i}"
        files.setdefault(i, {"path": p, "M": 0})
        files[i]["M"] += k == "M"
        n = len(V.errors)
        V.step("std.v_compute", {"from": s, "to": f}, f"{c[:7]} {k} {p}")
        rows[f"v {p} {j} {k}"] = {f"v_{k.lower()}_ok": int(len(V.errors) == n)}
        n = len(S.errors)
        if k == "A":
            S.ind[f] = FILE
            S.facts[("exists", (f,))] = True
        ver = f"ver{j}"
        S.step("std.v_compute", {"from": s, "to": ver}, f"{c[:7]} {k} {p}")
        if ver in S.ind:
            S.facts[("part", (ver, f))] = True
            S.fact_ok("part", (ver, f), f"part({ver}, {f})")
        rows[f"s {p} {j} {k}"] = {f"s_{k.lower()}_ok": int(len(S.errors) == n)}
    for i, x in files.items():
        rows[f"file {i} {x['path']}"] = {"recomputed": int(x["M"] > 0)}
    for c in ("v_a_ok", "v_m_ok", "s_a_ok", "s_m_ok", "recomputed"):
        v = [r[c] for r in rows.values() if c in r]
        print(c, f"{sum(v)}/{len(v)}")
    for m in (V, S):
        print(m.name, "エラーの例:", m.errors[:2])
    (OUT / "sys_confusion.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_confusion.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
