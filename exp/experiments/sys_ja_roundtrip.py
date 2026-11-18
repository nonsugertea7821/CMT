"""仮説 h_ja_roundtrip（に依存しない(日本語の文章から読み戻した式, 日本語の係りの多義)）を確かめる: 体系の事実を
日本語の文に訳し、その文を体系の語彙で読み戻すと、元の式が一つに決まるか。結果を見る前に、この説明と手順と判定を
登録した（issue #161）。

対象: 仮説と決定の中身（exp_check.build() の C["hypotheses"] と C["decisions"]）。始点と終点が並びなら、対ごとに一つ。
  始点か終点が体系のノードでないもの（測定値の道、数）は除く（n_excluded に数える）。
訳し方（変換器。h_ja_case_frame の F の枠を使う）:
  動詞の事実 v(A, B):  「〈A〉が〈B〉〈印〉〈v〉」。印は v の表示語から決める（sys_ja_case_frame.py の frame と同じ規則）:
    表示語が格助詞で始まるなら印なし、最初の格助詞の前が名詞の語なら「の」、そのほかは「を」。
  種類の事実 is_a(A, B): 「〈A〉は〈B〉の一種である」。
  〈X〉はノード X の表示語（display）。
読み戻し（閉じた語彙。外の解析器は使わない）:
  語彙は体系のすべてのノードの表示語。動詞はシグネチャに from と to を持つノード。
  文を、上の二つの形のどれかに、語彙の語で切り分けるすべての仕方を数える（parses）。読みは (動詞, A, B) の組。
  ok      読みがちょうど一つで、それが元の式と同じ
  lex     読みが二つ以上で、どの読みも同じ文字列の切り分け（同じ表示語を持つ別のノードがある。同音の語）
  struct  切り分けの仕方が二つ以上ある（係りの多義。語の境目か、どの語がどこに掛かるかが一つに決まらない）
  miss    読みがない（変換器か読み戻しの誤り。0 でなければ手順の誤りとして開示する）
数える量（要約。行の鍵と重ならない名前にする）:
  n_facts, n_excluded, n_ok, n_lex, n_struct, n_miss, rate_ok = n_ok / n_facts
  n_homonym_words  語彙のうち、ほかのノードと表示語が同じ語の数（記述）
  errors           体系の型検査の誤りの数
判定（ec が通るもとで）:
  n_struct = 0 かつ n_lex = 0 かつ n_miss = 0 なら支持（v_support）。
  n_struct ≥ 1 なら反証（v_contradict）: 読み戻した式が係りの多義に依存する。
  そのほか（struct はないが lex か miss がある）は mixed。
見込み（開示）:
  語彙を閉じているので、名詞句の中の係り（「AのBのC」をどう切るか）は、表示語をまるごと一語として読むことで
  消える。この測り方が見るのは、文の骨組み（が・を・の・は）と語の境目が、語彙の偶然の重なりで二通りに切れるかだけ。
  なので支持の見込みが高く、強い確かめではない。開いた読み戻し（表示語を限定の式に戻す）は、この実験の外。
  登録の前に見たのは、対象の数（仮説 95、決定 52）と、シグネチャを持つノードの数（97）だけ。訳した文も読み戻しも、
  まだ走らせていない。

行（sys_ja_roundtrip.json）:
  "summary 要約": 上の数
  "fact <i>": parses（読みの数）, splits（切り分けの数）, ok, lex, struct, miss（0 か 1）
  "texts": 事実ごとの識別子、元の式、訳した文、読み（記述）

使い方:
  python exp/experiments/sys_ja_roundtrip.py
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "exp/src"), str(ROOT / "exp/experiments")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker  # noqa: E402
    import exp_check  # noqa: E402
from sys_ja_case_frame import frame  # noqa: E402

OUT = ROOT / "exp/experiments/results"
ISA = ("は", "の一種である")


def facts(C, T):
    out, excluded = [], 0
    for sect in ("hypotheses", "decisions"):
        for cid, x in C[sect].items():
            ss, oo = ([v] if isinstance(v, str) else v for v in (x["s"], x["o"]))
            for a in ss:
                for b in oo:
                    if isinstance(a, str) and isinstance(b, str) and a in T.N and b in T.N and (x["p"] == "is_a" or x["p"] in T.N):
                        out.append((cid, x["p"], a, b))
                    else:
                        excluded += 1
    return out, excluded


def render(T, p, a, b):
    d = lambda x: T.N[x].get("display", x)
    if p == "is_a":
        return f"{d(a)}{ISA[0]}{d(b)}{ISA[1]}"
    _, mark = frame(d(p))
    return f"{d(a)}が{d(b)}{mark}{d(p)}"


def readback(s, words, verbs):
    reads, splits = set(), set()
    if s.endswith(ISA[1]):
        core = s[:-len(ISA[1])]
        for i in range(1, len(core)):
            if core[i] == ISA[0][0] and core[:i] in words and core[i + 1:] in words:
                splits.add(("is_a", core[:i], core[i + 1:]))
    for vd in verbs:
        if not s.endswith(vd):
            continue
        _, mark = frame(vd)
        head = s[:-len(vd)]
        if mark and not head.endswith(mark):
            continue
        head = head[:-len(mark)] if mark else head
        for i in range(1, len(head)):
            if head[i] == "が" and head[:i] in words and head[i + 1:] in words:
                splits.add((vd, head[:i], head[i + 1:]))
    for vd, da, db in splits:
        for p in (["is_a"] if vd == "is_a" else verbs[vd]):
            for a in words[da]:
                for b in words[db]:
                    reads.add((p, a, b))
    return reads, splits


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, S, M, C = exp_check.build()
    errors = len(type_checker.errors)
    words, verbs = collections.defaultdict(list), collections.defaultdict(list)
    for nid, n in T.N.items():
        dd = n.get("display", nid)
        words[dd].append(nid)
        if "from" in n and "to" in n:
            verbs[dd].append(nid)
    fs, excluded = facts(C, T)
    rows, texts = {}, {}
    c = dict(n_ok=0, n_lex=0, n_struct=0, n_miss=0)
    for i, (cid, p, a, b) in enumerate(fs):
        s = render(T, p, a, b)
        reads, splits = readback(s, words, verbs)
        miss = int(not reads)
        struct = int(len(splits) > 1)
        ok = int(reads == {(p, a, b)})
        lex = int(not ok and not struct and not miss)
        for k, v in (("n_ok", ok), ("n_lex", lex), ("n_struct", struct), ("n_miss", miss)):
            c[k] += v
        rows[f"fact {i}"] = {"parses": len(reads), "splits": len(splits), "ok": ok, "lex": lex, "struct": struct, "miss": miss}
        texts[i] = {"id": cid, "fact": [p, a, b], "ja": s, "reads": sorted(map(list, reads)), "splits": sorted(map(list, splits))}
    n = len(fs)
    summ = {"n_facts": n, "n_excluded": excluded, **c, "rate_ok": round(c["n_ok"] / n, 4) if n else 0,
            "n_homonym_words": sum(len(v) for v in words.values() if len(v) > 1), "errors": errors}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_ja_roundtrip.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for i, t in texts.items():
        r = rows[f"fact {i}"]
        if not r["ok"]:
            print(i, t["id"], t["ja"], r, t["splits"])


if __name__ == "__main__":
    main()
