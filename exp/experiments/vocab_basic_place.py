"""h_basic_vocab_fits と h_vocab_domain_invariant を確かめる: 基礎語彙を、出典ごとの領域に、新しい根や法則なしで置けるか。

仮説（claims.yaml）:
  h_basic_vocab_fits: v_refer(h, v_depend(syntax.extends, [syntax.mod, syntax.holds, syntax.from, syntax.to]))。登録 #589。
  h_vocab_domain_invariant: v_refer(h, v_depend(syntax.extends, syntax.domain, neg))。登録 #591。
出典（本文はリポジトリに入れない。手元の写しを引数で渡す）:
  英: Basic English 850（Wiktionary の付録の表。節 Operations / 400 general words / Things - 200 picturable words）。
  日: 日本語 WordNet（wnjpn.db。Princeton WordNet 3.0 の synset に日本語の見出しを結んだもの）。

二つの段に分ける。
段 1（sample）: 語を選ぶ。走らせる前に決める。
  動詞: Basic English の operator 18 語 come get give go keep let make put seem take be do have say see send may will
        のうち、Operations の節にあるもの。品詞 v。
  名詞: 400 general words から 30 語、200 picturable words から 10 語を、random.Random(593) の sample で選ぶ（表の順に並べてから）。品詞 n。
  各語の synset: wnjpn.db の英語の sense のうち、見出しが語に一致し品詞が合うもので、freq が最大のもの（同じなら synset の識別子が小さいもの）。
  日本語の見出し: その synset に結ばれた日本語の word のうち、wordid が最小のもの。synset か日本語の見出しがなければ、その語は除き、数える。
  出力: results/vocab_basic_sample.json（行: 語ごとの en, pos, list, synset, ja。s: n_verb, n_noun, n_drop）。
段 2（judge）: 置いた結果を数える。置くのは段 1 のあと、手で（Claude が）行う。
  英の語は領域 en_basic のノード <en>（空白は _）、日の語は領域 ja_basic のノード j_<en> に置く。display は日本語。
  en_basic と ja_basic は std と syntax だけを使う（互いを使わない）。
  置けた: そのノードが体系にある（tc.build が通る）。
  新しい根: 置いたノードから extends を語彙の領域の中でたどり、語彙の領域の外のノードに届かないもの。
  新しい法則: 語彙の領域の個体のうち is が law_rule のもの。
  収まった: 置けて、新しい根でない。新しい法則が一つでもあれば、どの語も収まらないと数える。
  錨: 書いた extends を解決し、語彙の領域の中のものは、その錨に置き換えた集まり（外のノードの集まり）。
  食い違い: 英と日の両方が収まった組で、錨が違うもの。
  出力: results/vocab_basic_judge.json（行: 組ごとの placed, fits, anchor。s: n_pair, fit_en, fit_ja, share_fit_en, share_fit_ja,
        n_new_root, n_new_law, n_both_fit, n_mismatch）。

判定（事前に決める）:
  tc.build が通らなければ外れ（状態を変えない）。
  h_basic_vocab_fits: share_fit_en >= 0.9 かつ share_fit_ja >= 0.9 なら支持、どちらかが < 0.9 なら反証。
  h_vocab_domain_invariant: n_both_fit >= 1 で、n_mismatch = 0 なら支持、>= 1 なら反証。
開示:
  置くのは同じ書き手（Claude）なので、英と日の置き方は独立ではない。日本語の領域を先に、日本語の見出しと
  synset の日本語の定義だけを見て置き、そのあと英語の領域を置く。それでも食い違い 0 は弱い証拠にとどまる。
  置けなかった語は、理由を commit に書く。置けなかった語は収まらないと数える（分母から除かない）。
  三つの確かめ直し（b_*_vocab）は、この実験では数えない。置いた結果の上で、別に事前登録する。
  走らせる前に数は計算していない。
追記（段 1 のあと、置く前。判定は変えない）:
  ontology には物質的な持続体の層がなく、continuant の下に直接置けば、どの名詞も「収まる」。
  そのため判定の基準は弱い。記述として次を足す。
    n_inter_en / n_inter_ja: 語彙の領域に足した、選んだ語でないノードの数（中間の種類）。
    n_dup_en / n_dup_ja: 同じ領域で、extends と mod と from・to・holds が同じになった、置いた語の組の数（式で区別できていない）。
使い方:
  python -I exp/experiments/vocab_basic_place.py sample <be.html> <wnjpn.db>
  python -I exp/experiments/vocab_basic_place.py judge
"""
import contextlib
import html
import io
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
RES = ROOT / "exp/experiments/results"
OPS = "come get give go keep let make put seem take be do have say see send may will".split()
SECTIONS = {"Operations": "ops", "400 general words": "general", "Things - 200 picturable words": "picturable"}
VOCAB = ("en_basic", "ja_basic")


def sections(text):
    parts = re.split(r"<h[23][^>]*>(.*?)</h[23]>", text, flags=re.S)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        title = re.sub(r"<[^>]*>", "", parts[i]).strip()
        for k, v in SECTIONS.items():
            if title.startswith(k):
                words = re.findall(r'<a href="/wiki/[^"#]+"[^>]*>([^<]+)</a>', parts[i + 1])
                seen = []
                for w in words:
                    w = html.unescape(w).strip()
                    if w and w not in seen:
                        seen.append(w)
                out[v] = seen
    return out


def sample(be, db):
    S = sections(Path(be).read_text(encoding="utf-8"))
    rng = random.Random(593)
    chosen = [(w, "v", "ops") for w in OPS if w in S.get("ops", [])]
    chosen += [(w, "n", "general") for w in rng.sample(S["general"], 30)]
    chosen += [(w, "n", "picturable") for w in rng.sample(S["picturable"], 10)]
    c = sqlite3.connect(db)
    rows, drop = {}, 0
    for w, pos, lst in chosen:
        r = c.execute("select s.synset, s.freq from word w join sense s on w.wordid=s.wordid "
                      "where w.lang='eng' and s.lang='eng' and w.lemma=? and w.pos=? "
                      "order by s.freq desc, s.synset asc limit 1", (w, pos)).fetchone()
        ja = None
        if r:
            j = c.execute("select w.lemma from sense s join word w on s.wordid=w.wordid "
                          "where s.synset=? and s.lang='jpn' order by w.wordid asc limit 1", (r[0],)).fetchone()
            ja = j[0] if j else None
        if not r or not ja:
            drop += 1
        rows[w] = {"en": w, "pos": pos, "list": lst, "synset": r[0] if r else None, "ja": ja}
    s = {"n_verb": sum(1 for x in rows.values() if x["pos"] == "v"), "n_noun": sum(1 for x in rows.values() if x["pos"] == "n"),
         "n_drop": drop, "n_sections": {k: len(v) for k, v in S.items()}}
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "vocab_basic_sample.json").write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(s, ensure_ascii=False))


def judge():
    import os
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    os.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    smp = json.loads((RES / "vocab_basic_sample.json").read_text())["rows"]
    invocab = lambda x: isinstance(x, str) and x.split(".", 1)[0] in VOCAB

    def ext(x):
        e = N[x].get("extends")
        e = e if isinstance(e, list) else [e] if e else []
        dom = x.split(".", 1)[0]
        return [w if w in N else (T.resolve(w, dom) or w) for w in e]

    def anchor(x, seen=()):
        out = set()
        for p in ext(x):
            if invocab(p) and p in N and p not in seen:
                out |= anchor(p, seen + (x,))
            elif not invocab(p):
                out.add(p)
        return out

    n_new_law = 0
    for d in VOCAB:
        if d in Dm:
            for iid, v in (Dm[d][1].get("individuals") or {}).items():
                if str(v.get("is")).split(".")[-1] == "law_rule":
                    n_new_law += 1
    rows = {}
    n_new_root = 0
    for w, r in smp.items():
        if not r["synset"] or not r["ja"]:
            continue
        nid = w.replace(" ", "_")
        row = {}
        for d, key in (("en_basic", nid), ("ja_basic", "j_" + nid)):
            x = f"{d}.{key}"
            placed = x in N
            a = sorted(anchor(x)) if placed else []
            root = placed and not a
            n_new_root += root
            row[d] = {"placed": placed, "fits": placed and not root and n_new_law == 0, "anchor": a}
        rows[w] = row
    n = len(rows)
    fe = sum(r["en_basic"]["fits"] for r in rows.values())
    fj = sum(r["ja_basic"]["fits"] for r in rows.values())
    both = [r for r in rows.values() if r["en_basic"]["fits"] and r["ja_basic"]["fits"]]
    s = {"n_pair": n, "fit_en": fe, "fit_ja": fj, "share_fit_en": fe / n, "share_fit_ja": fj / n,
         "n_new_root": n_new_root, "n_new_law": n_new_law, "n_both_fit": len(both),
         "n_mismatch": sum(r["en_basic"]["anchor"] != r["ja_basic"]["anchor"] for r in both)}
    keys = {"en_basic": {w.replace(" ", "_") for w in rows}, "ja_basic": {"j_" + w.replace(" ", "_") for w in rows}}
    for d, tag in (("en_basic", "en"), ("ja_basic", "ja")):
        mine = [x for x in N if x.split(".", 1)[0] == d]
        s[f"n_inter_{tag}"] = sum(1 for x in mine if x.split(".", 1)[1] not in keys[d])
        sig = {}
        for x in mine:
            if x.split(".", 1)[1] in keys[d]:
                k = json.dumps({f: N[x].get(f) for f in ("extends", "mod", "from", "to", "holds")}, sort_keys=True, default=str)
                sig[k] = sig.get(k, 0) + 1
        s[f"n_dup_{tag}"] = sum(c * (c - 1) // 2 for c in sig.values())
    (RES / "vocab_basic_judge.json").write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        sample(sys.argv[2], sys.argv[3])
    else:
        judge()
