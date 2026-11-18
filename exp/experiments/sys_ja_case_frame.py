"""仮説 h_ja_case_frame（依存する(式から訳した日本語の文章, 動詞の格の枠)）を確かめる: 体系の限定を日本語の文に
訳すとき、すべての動詞に一つの格の枠（「〜が〜を〈動詞〉」）を当てると、機械的に分かる文法の破れが出るか。
出るなら、日本語の文章は動詞ごとの格の枠に依存する。結果を見る前に、この説明と手順を登録した（issue #160）。

対象: 体系のノード（T.N）が自分で書いた限定の項 {of: [v, pos], with: w} のうち、pos が from か to のもの。
  単位は動詞 v（異なり）。出現数は項の数。
訳し方（二つ。自分の位置を「これ」、相手を with の表示語、with がなければ「何か」と書く）:
  U（一つの枠）: from なら「これが〈相手〉を〈動詞の表示語〉」、to なら「〈相手〉がこれを〈動詞の表示語〉」。
  F（動詞ごとの枠。表示語の形から決める。記述で、判定に使わない）:
    表示語が格助詞で始まる（P1 の表）なら、目的語に助詞を付けない:「これが〈相手〉で書かれる」。
    表示語の最初の格助詞の前が名詞の語（漢字かカタカナで始まる）なら、目的語に「の」を付ける:「これが〈相手〉の後ろに置かれる」。
    そのほかは U と同じ「を」。
  F の枠の種類（frame_classes）は、上の三つのうち実際に使われた数。
破れの規則（U の文について。文字列で決める。外の解析器は使わない）:
  R1 二重の格助詞: 表示語が格助詞で始まる（P1 = に, で, と, から, について, を, へ, より）。U は「を」の直後に別の格助詞を置く。
  R2 受け身に「を」: 表示語が受け身の形で終わる（「れる」の前の仮名があ段: か, さ, た, な, ま, ら, わ, が, ば, は）。
     （直接受け身は目的語の「を」を取らない。）
  R4 二重の「を」: 表示語の中に「を」がある。U の目的語の「を」と合わせて、一つの節に「を」が二つになる（二重ヲ格制約）。
  R1, R2, R4 は破れの下限で、「依存するを」（に を要る）のような語彙で決まる破れは数えない。
数える量（要約。行の鍵と重ならない名前にする）:
  n_verbs, n_occ   対象の動詞の異なり数と、項の数
  viol_verbs       R1, R2, R4 のどれかに当たる動詞の数。rate_verbs = viol_verbs / n_verbs
  viol_occ         その動詞の項の数。rate_occ = viol_occ / n_occ
  frame_classes    F で使った枠の種類の数（記述）
判定: tc と ec が通るもとで、rate_verbs ≥ 0.1 なら支持（v_support）。rate_verbs < 0.1 なら、規則が下限なので反証とせず、
  未検証のまま残す（規則を足すなら、訂正として手順に書き足して開示する）。
  この実験には反証の道がない。一つの枠で足りるという反対の主張は、規則が下限なので、この測り方では示せない。
下調べ（開示）: 手順を書く前に、動詞の表示語のうち約 30 個を見た（で書かれる、に関わらせる、後ろに置かれる、
  について閉じている、成り立つことを求める など）。なので支持の見込みは高く、この判定は強い確かめではない。
  この実験の主な産物は、F の枠の表（自然言語への変換の最初の部品）。
  外の形態素解析器（fugashi など）を入れることは、この環境では許されなかったので、文字列の規則にした。

行（sys_ja_case_frame.json）:
  "summary 要約": 上の数
  "verb <v>":  occ（項の数）, r1, r2, r4（0 か 1）, viol（どれかに当たれば 1）
  "texts": 動詞ごとの表示語と、U と F の例文（行ではなく、記述）

使い方:
  python exp/experiments/sys_ja_case_frame.py
"""
import collections
import contextlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
P1 = ("について", "から", "より", "に", "で", "と", "を", "へ")
A_ROW = set("かさたなまらわがばは")
NOUN_HEAD = re.compile(r"^[一-鿿゠-ヿ]")


def name(T, x):
    return T.N[x].get("display", x) if x in T.N else x


def rules(vd):
    r1 = int(vd.startswith(P1))
    r2 = int(vd.endswith("れる") and len(vd) >= 3 and vd[-3] in A_ROW)
    r4 = int("を" in vd)
    return r1, r2, r4


def frame(vd):
    if vd.startswith(P1):
        return "bare", ""
    i = min((vd.find(p) for p in P1 if vd.find(p) > 0), default=-1)
    if i > 0 and NOUN_HEAD.match(vd):
        return "no", "の"
    return "wo", "を"


def sentence(pos, other, vd, obj_mark):
    subj, obj = ("これ", other) if pos == "from" else (other, "これ")
    return f"{subj}が{obj}{obj_mark}{vd}"


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, _, _ = tc.build()
    errors = len(tc.errors)
    occ, example = collections.Counter(), {}
    for nid, n in T.N.items():
        for m in n.get("mod") or []:
            if not isinstance(m, dict) or "of" not in m:
                continue
            v, pos = m["of"]
            if pos not in ("from", "to"):
                continue
            occ[v] += 1
            example.setdefault(v, (pos, name(T, m["with"]) if "with" in m else "何か"))
    rows, texts, viol_verbs, viol_occ, classes = {}, {}, 0, 0, set()
    for v in sorted(occ):
        vd = name(T, v)
        r1, r2, r4 = rules(vd)
        viol = int(r1 or r2 or r4)
        cls, mark = frame(vd)
        classes.add(cls)
        pos, other = example[v]
        rows[f"verb {v}"] = {"occ": occ[v], "r1": r1, "r2": r2, "r4": r4, "viol": viol}
        texts[v] = {"display": vd, "U": sentence(pos, other, vd, "を"), "F": sentence(pos, other, vd, mark), "frame": cls}
        viol_verbs += viol
        viol_occ += occ[v] * viol
    n_verbs, n_occ = len(occ), sum(occ.values())
    summ = {"errors": errors, "n_verbs": n_verbs, "n_occ": n_occ, "viol_verbs": viol_verbs,
            "rate_verbs": round(viol_verbs / n_verbs, 4), "viol_occ": viol_occ, "rate_occ": round(viol_occ / n_occ, 4),
            "frame_classes": len(classes)}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_ja_case_frame.json").write_text(
        json.dumps({"rev": rev, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for v, t in texts.items():
        print(v, t["U"], "|", t["F"])


if __name__ == "__main__":
    main()
