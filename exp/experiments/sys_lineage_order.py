"""h_lineage_is_genus と h_lineage_is_history を、git の履歴から同じ数え方で確かめる。

仮説（exp.yaml）:
  h_lineage_is_genus:   v_refer(h, v_depend(syntax.extends, supersedes, neg))。登録 #578（issue #579）。
  h_lineage_is_history: v_refer(h, v_depend(syntax.extends, supersedes))。    登録 #580（issue #581）。
  出どころ: 利用者「相反する2つの性質は反する象限で互いに成り立つ」。D(x) = D(親) + 差異 を、
  名詞は演繹の向き（中身から親）、動詞は構成の向き（親と差異から中身）で解く、という見方。
  予想: 名詞は欄が先に変わり親が後を追う（系譜 = いまの類）。動詞は親が先に決まり、付け替えが少ない（系譜 = 記録）。

操作: 体系を読むだけ（写しも書き換えもしない）。
  main の first-parent の commit のうち yaml を触るものを古い順にたどり、各 commit の木から、
  domain と nodes を持つ yaml（cscl/trial・cscl/notes・exp/experiments を除く）を読む。節の名は「domain.id」。
  各節 x の各時点の状態: 書いた extends（各要素の最後の「.」より後ろの名、並べた集合）と、
  自分の欄 = display と extends を除く欄の値。
  いまの main の tc.build で、動詞（#582 と同じ集まり）と名詞（N のうち動詞でないもの）に分ける。
  いまの N にない節は数えない。
  付け替え: x がある時点で、前に x があった時点から extends が変わったこと（初めて現れた時点は数えない）。
  欄が先: 付け替えの commit を c、その前に x の extends が決まった commit を p としたとき、
    x の自分の欄が (p, c] のどこかで変わっていれば「欄が先」、そうでなければ「親が単独」。
行（sys_lineage_order.json）: 付け替えごとに、節・種類・commit・前後の extends・欄が先か。
  s: n_commits, n_noun, n_verb, n_ev_noun, n_ev_verb, n_led_noun, n_led_verb,
     rate_noun = n_ev_noun / n_noun, rate_verb = n_ev_verb / n_verb, led_share_noun = n_led_noun / n_ev_noun。

判定（事前に決める）:
  tc.build が通らないか、どの commit も読めなければ外れ（状態を変えない）。
  h_lineage_is_genus: n_ev_noun >= 1 かつ led_share_noun >= 0.5 なら支持。それ以外は反証。
  h_lineage_is_history: rate_verb < rate_noun なら支持。それ以外は反証。
開示: 法則の変更（例: acda4d3 の単調な限定）に合わせて親を動かした付け替えは、欄が変わらないので「親が単独」に数える。
  親の名の付け替え（改名）も extends の変化に数えうる（domain の前置きは落とすが、名そのものの改名は落とさない）。
  走らせる前に数は計算していない。
訂正（実行の後に書き足す）:
  de07f15 は、類の鍵の名を is から extends に改めた commit。それより前の節は extends を持たず is を持つので、
  この commit で extends が [] から変わり、is が消えて「欄が先」に数わる。これは付け替えではなく鍵の改名で、
  開示に書いた「名そのものの改名」の鍵の側の例。数えた付け替え 64 のうち 25（名詞 11、動詞 14）がこれにあたる。
  記録した結果のファイルは変えず、sys_lineage_order_fix.py がそれを読み、de07f15 の行を除いて同じ量を数え直す。
  判定は同じ式を、数え直した量に当てる。元の量の判定と食い違う仮説は mixed とする。
使い方:
  python exp/experiments/sys_lineage_order.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve()
KEYS = ("holds", "pre", "post")
SKIP = ("cscl/trial/", "cscl/notes", "exp/experiments/")
Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout


def canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)


def ext_norm(e):
    e = e if isinstance(e, list) else [e] if e else []
    return canon(sorted(str(w).rsplit(".", 1)[-1] for w in e))


def snapshot(c):
    out = {}
    files = [f for f in git("ls-tree", "-r", "--name-only", c).split("\n")
             if f.endswith(".yaml") and not f.startswith(SKIP)]
    for f in files:
        try:
            d = yaml.load(git("show", f"{c}:{f}"), Loader=Loader)
        except Exception:
            continue
        if not isinstance(d, dict) or not isinstance(d.get("nodes"), dict):
            continue
        dom = d.get("domain") or Path(f).stem
        for i, v in d["nodes"].items():
            if not isinstance(v, dict):
                continue
            own = {k: w for k, w in v.items() if k not in ("display", "extends")}
            out[f"{dom}.{i}"] = (ext_norm(v.get("extends")), canon(own))
    return out


def main():
    root = HERE.parents[2]
    os.chdir(root)
    out = root / "exp/experiments/results/sys_lineage_order.json"
    sys.path[:0] = [str(root / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, Dm = tc.build()
    N = T.N
    top_o = T.top_o
    verbs = {x for x in N if x != top_o and T.is_a(x, top_o)
             and any(N.get(y, {}).get(k) for y in [x] + T.ancestors(x) for k in KEYS)}
    kind = {x: ("verb" if x in verbs else "noun") for x in N}
    commits = git("log", "--first-parent", "--reverse", "--format=%h", "main", "--", "*.yaml").split()
    last = {}
    set_at = {}
    own_changes = {}
    rows = {}
    n_read = 0
    for c in commits:
        S = snapshot(c)
        n_read += bool(S)
        for x, (e, o) in S.items():
            if x not in kind:
                continue
            if x in last:
                pe, po = last[x]
                if o != po:
                    own_changes.setdefault(x, []).append(c)
                if e != pe:
                    p = set_at[x]
                    idx = {h: i for i, h in enumerate(commits)}
                    led = any(idx[p] < idx[h] <= idx[c] for h in own_changes.get(x, []))
                    rows[f"ev {len(rows)}"] = {"node": x, "kind": kind[x], "commit": c,
                                               "before": json.loads(pe), "after": json.loads(e), "own_led": led}
                    set_at[x] = c
            else:
                set_at[x] = c
            last[x] = (e, o)
    if not n_read:
        raise SystemExit("どの commit も読めなかった")
    n_noun = sum(1 for x in kind if kind[x] == "noun")
    n_verb = len(verbs)
    ev = list(rows.values())
    n_ev_noun = sum(r["kind"] == "noun" for r in ev)
    n_ev_verb = sum(r["kind"] == "verb" for r in ev)
    n_led_noun = sum(r["kind"] == "noun" and r["own_led"] for r in ev)
    n_led_verb = sum(r["kind"] == "verb" and r["own_led"] for r in ev)
    s = {"n_commits": len(commits), "n_read": n_read, "n_noun": n_noun, "n_verb": n_verb,
         "n_ev_noun": n_ev_noun, "n_ev_verb": n_ev_verb, "n_led_noun": n_led_noun, "n_led_verb": n_led_verb,
         "rate_noun": n_ev_noun / n_noun, "rate_verb": n_ev_verb / n_verb,
         "led_share_noun": (n_led_noun / n_ev_noun) if n_ev_noun else 0.0}
    out.write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
