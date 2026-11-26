"""型検査器のコードに残る限定の検査 3 つ（位置 new の with・種類でない・動詞でない）を法則に置き換えても、検査の結果が変わらないか（h_spot_kind_checks_as_law）。

系列:
  #917・#920・#925 で端の検査（に来られない）を法則で書き、#926 でコードから法則に移した。
  残るコードの限定の検査は 3 つ（type_checker.py の check の mod の段）:
    K1「位置 new には with を付けられない」
    K2「<相手> は種類でない」（属する is の始点で限定するとき、相手は種類）
    K3「<相手> は動詞でない。…動詞を受け取る」（相手の端の種類が「動詞を指すもの」の下のとき、相手は動詞）
  仮説: h_spot_kind_checks_as_law: v_depend(type_check_result, [syntax.law_rule, syntax.mod])

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  before: 今の木そのまま。
  after: 写しの syntax.yaml に下の法則を足し、写しの type_checker.py で K1・K2・K3 の err(...) を pass に替える。
  法則（syntax_facts の mod・of・position・with・extends・form・holds・pre と、既にある r_end_from・r_end_to・r_below を読む）:
    mod_new_no_with: mod(var1,var2), position(var2,new), with(var2,var3) を前提に、with(var2,var3) でないことを求める（K1）。
    not_concept_by_of・_form・_holds・_pre: of・form・holds・pre を持つものは r_not_concept。
    concept_by_extends: extends を持ち r_not_concept でないものは r_concept（コードの is_concept と同じ形）。
    is_from_with_concept: mod(var1,var2), of(var2,is), position(var2,from), with(var2,var3) を前提に、r_concept(var3,var3) を求める（K2）。
    verb_by_ends: r_end_from と r_end_to を持つものは r_verb（コードの is_verb と同じ形）。
    verb_ref_with_verb_from・_to: 限定の相手の側の端の種類が ontology.verb_ref の下なら、相手に r_verb(var4,var4) を求める（K3）。

材料（モデルは走らせない）:
  A. 体系そのまま: CI と同じ 4 つの検査（type_checker.py、exp_check.py、runtime.py、test_worlds.py）を before と after で走らせる。
  B. 限定の書き換え: 体系の yaml（cscl.yaml、cscl/ 以下、exp/src/ 以下）の中の「of: [<動詞>, from|to], with: <名>」を、
     ファイル名の順・ファイルの中の位置の順に並べ、0 から数えて 10 で割り切れる番号のものだけを選ぶ。
     選んだ 1 つずつに、次の 4 つの書き換えを 1 つずつ当てた写しで type_checker.py を走らせる（ほかは元のまま）:
       new: 位置を new に替える（K1 を起こす見込み）。
       ind: with の名を個体 ontology.var1 に替える。
       kind: with の名を種類 ontology.kind に替える。
       verb: with の名を動詞 ontology.v_rely に替える。
     元の名と同じになる書き換えは除く。どれが誤りになるかは前もって決めない。

手順:
  1. before と after の写しを作る。after に patch を当てる（当てる場所が 1 つずつ見つからなければ止め、判定しない）。
  2. A を両方で走らせる。
  3. B の各書き換えを、両方の写しで走らせる。結果は「受け入れ」（終了コード 0）、「退け」（「検査に失敗」の行があり終了コード 1）、
     「壊れ」（それ以外）。
  4. 一致: 両方が受け入れか退けで、同じもの。不一致: 取りこぼし（before 退け・after 受け入れ）、余分な退け（before 受け入れ・after 退け）、
     壊れの違い（片方だけ壊れ）。両方壊れは「走らず」として別に数える。
  5. 覆い: before の誤りに K1・K2・K3 の文があるとき、after の同じ書き換えに、対応する法則（K1→mod_new_no_with、
     K2→is_from_with_concept、K3→verb_ref_with_verb_from か _to）の誤りがあれば、覆われたとする。C = 覆われた数 / K の文の数。

判定（事前登録）:
  前提: before の A の 4 つがすべて終了コード 0。B で両方が走った書き換えが 50 未満なら判定しない。
    before の B で K1・K2・K3 のそれぞれが 1 度も出なければ、出なかった検査について言えないので、判定しない。
  h_spot_kind_checks_as_law:
    after の A の 4 つがすべて 0、B の不一致が 0、C = 1 なら支持。
    after の A のどれかが 0 でない、または B の不一致が 1 以上なら反証。
    不一致が 0 で C < 1 なら決まらない。
  参考（判定に使わない）: K ごとの before の出た数、after の誤りの法則ごとの数、
    名前を付けた限定（mod に名で書いたもの）にだけ法則が当たった数（コードは式の中の限定だけを見ていた）、走る時間。

開示（結果を見る前に分かっていること）:
  - #917・#920・#925 の結果を読んでいる。#920 では、法則に移すと誤りの文の数が増えた（170 → 178）。
  - コードの K1〜K3 は式の中の限定（dict）だけを見る。法則の mod(var1,var2) は、名前を付けた限定にも当たる。
    名前を付けた限定に with の誤りがあれば、after だけが退ける（余分な退け）見込みがある。
  - コードの is_concept は「with が N にある」も求める。法則の r_concept は extends の文から出るので、個体（is の文だけ）と any は r_concept にならない。
    この 2 つは同じ線を引く見込みだが、確かめていない。
  - 書き換えの場所の数は、登録の前に grep で数えた（1006。選ぶのは約 101、書き換えは約 400）。選び方は番号だけで決め、中身を見て選ばない。
  - この登録の前に、検査器と体系を読んだだけで、type_checker.py は走らせていない。
  - 支持でも、言えるのは、この 4 つの書き換えと体系そのままで、受け入れ・退けが変わらないこと。誤りの文面は変わりうる。
  - 反証でも「規則で書けない」とまでは言えない。言えるのは、この法則と、この外し方では、どこかで線が変わること。

出力: results/sys_spot_kind_checks_as_law.json
使い方:
  python exp/experiments/sys_spot_kind_checks_as_law.py
"""
import json
import re
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_endpoint_law_whole_system as ws

ROOT = ws.ROOT
OUT = ROOT / "exp/experiments/results/sys_spot_kind_checks_as_law.json"
TC = ws.TC
CI = ws.CI
SYN = "cscl/library/syntax/syntax.yaml"
PAT = re.compile(r"of: \[([A-Za-z_][A-Za-z0-9_.]*), (from|to)\], with: ([A-Za-z_][A-Za-z0-9_.]*)")
STEP = 10
WORKERS = 4
PROBES = (("new", None), ("ind", "ontology.var1"), ("kind", "ontology.kind"), ("verb", "ontology.v_rely"))

NODES = """  mod_new_no_with: {is: law_rule, display: 位置 new で限定するものは、相手を持たない}
  r_not_concept: {is: law_relation, display: 種類でない形を持つ}
  not_concept_by_of: {is: law_rule, display: 位置を持つものは種類でない形を持つ}
  not_concept_by_form: {is: law_rule, display: 形を持つものは種類でない形を持つ}
  not_concept_by_holds: {is: law_rule, display: 状態の関係を持つものは種類でない形を持つ}
  not_concept_by_pre: {is: law_rule, display: 前の状態の指定を持つものは種類でない形を持つ}
  r_concept: {is: law_relation, display: 種類である}
  concept_by_extends: {is: law_rule, display: 上位を持ち、種類でない形を持たないものは種類}
  is_from_with_concept: {is: law_rule, display: 属するの始点で限定する相手は、種類}
  r_verb: {is: law_relation, display: 動詞である}
  verb_by_ends: {is: law_rule, display: 始点と終点の種類を持つものは動詞}
  verb_ref_with_verb_from: {is: law_rule, display: 始点で限定する相手の位置が動詞を受け取るなら、相手は動詞}
  verb_ref_with_verb_to: {is: law_rule, display: 終点で限定する相手の位置が動詞を受け取るなら、相手は動詞}
"""

FACTS = """  - {is: v_assume, from: mod_new_no_with, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: mod_new_no_with, to: {is: position, from: var2, to: new}}
  - {is: v_assume, from: mod_new_no_with, to: {is: with, from: var2, to: var3}}
  - {is: v_require, from: mod_new_no_with, to: {is: with, from: var2, to: var3, neg: true}}
  - {is: v_assume, from: not_concept_by_of, to: {is: of, from: var1, to: var2}}
  - {is: v_derive, from: not_concept_by_of, to: {is: r_not_concept, from: var1, to: var1}}
  - {is: v_assume, from: not_concept_by_form, to: {is: form, from: var1, to: var2}}
  - {is: v_derive, from: not_concept_by_form, to: {is: r_not_concept, from: var1, to: var1}}
  - {is: v_assume, from: not_concept_by_holds, to: {is: holds, from: var1, to: var2}}
  - {is: v_derive, from: not_concept_by_holds, to: {is: r_not_concept, from: var1, to: var1}}
  - {is: v_assume, from: not_concept_by_pre, to: {is: pre, from: var1, to: var2}}
  - {is: v_derive, from: not_concept_by_pre, to: {is: r_not_concept, from: var1, to: var1}}
  - {is: v_assume, from: concept_by_extends, to: {is: extends, from: var1, to: var2}}
  - {is: v_assume, from: concept_by_extends, to: {is: r_not_concept, from: var1, to: var1, neg: true}}
  - {is: v_derive, from: concept_by_extends, to: {is: r_concept, from: var1, to: var1}}
  - {is: v_assume, from: is_from_with_concept, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: is_from_with_concept, to: {is: of, from: var2, to: is}}
  - {is: v_assume, from: is_from_with_concept, to: {is: position, from: var2, to: from}}
  - {is: v_assume, from: is_from_with_concept, to: {is: with, from: var2, to: var3}}
  - {is: v_require, from: is_from_with_concept, to: {is: r_concept, from: var3, to: var3}}
  - {is: v_assume, from: verb_by_ends, to: {is: r_end_from, from: var1, to: var2}}
  - {is: v_assume, from: verb_by_ends, to: {is: r_end_to, from: var1, to: var3}}
  - {is: v_derive, from: verb_by_ends, to: {is: r_verb, from: var1, to: var1}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: of, from: var2, to: var3}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: position, from: var2, to: from}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: with, from: var2, to: var4}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: r_end_to, from: var3, to: var5}}
  - {is: v_assume, from: verb_ref_with_verb_from, to: {is: r_below, from: var5, to: ontology.verb_ref}}
  - {is: v_require, from: verb_ref_with_verb_from, to: {is: r_verb, from: var4, to: var4}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: mod, from: var1, to: var2}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: of, from: var2, to: var3}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: position, from: var2, to: to}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: with, from: var2, to: var4}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: r_end_from, from: var3, to: var5}}
  - {is: v_assume, from: verb_ref_with_verb_to, to: {is: r_below, from: var5, to: ontology.verb_ref}}
  - {is: v_require, from: verb_ref_with_verb_to, to: {is: r_verb, from: var4, to: var4}}
"""

CODE_ERRS = (
    """err(f"{where}: 位置 new には with を付けられない")""",
    """err(f"{where}: {m['with']} は種類でない")""",
    """err(f"{where}: {m['with']} は動詞でない。{verb} の {other} は動詞を受け取る")""",
)
K_TEXT = {"K1": "位置 new には with を付けられない", "K2": "は種類でない", "K3": "は動詞でない。"}
K_LAWS = {"K1": ("mod_new_no_with",), "K2": ("is_from_with_concept",), "K3": ("verb_ref_with_verb_from", "verb_ref_with_verb_to")}


def patch(tree):
    f = tree / SYN
    s = f.read_text(encoding="utf-8")
    node_anchor = next(ln for ln in s.split("\n") if ln.startswith("  below_any:"))
    fact_anchor = next(ln for ln in s.split("\n") if "from: below_any, to: {is: r_below" in ln)
    assert s.count(node_anchor + "\n") == 1 and s.count(fact_anchor + "\n") == 1
    s = s.replace(node_anchor + "\n", node_anchor + "\n" + NODES)
    s = s.replace(fact_anchor + "\n", fact_anchor + "\n" + FACTS)
    f.write_text(s, encoding="utf-8")
    t = tree / TC
    c = t.read_text(encoding="utf-8")
    for e in CODE_ERRS:
        assert c.count(e) == 1, e
        c = c.replace(e, "pass")
    t.write_text(c, encoding="utf-8")


def sites(tree):
    files = sorted(p.relative_to(tree).as_posix() for base in ("cscl.yaml", "cscl", "exp/src")
                   for p in ([tree / base] if (tree / base).is_file() else (tree / base).rglob("*.yaml")))
    out = []
    for f in files:
        s = (tree / f).read_text(encoding="utf-8")
        for m in PAT.finditer(s):
            out.append((f, m.start(), m.group(0), m.group(1), m.group(2), m.group(3)))
    return out


def mutate(text, end, name, probe, value):
    if probe == "new":
        return text.replace(f", {end}], with:", ", new], with:")
    if value == name:
        return None
    return text[: text.rindex(name)] + value


_W = {}
_BASE = []


def init(base):
    _BASE.append(base)


def worker(task):
    i, probe, f, pos, text, new = task
    if not _W:
        d = Path(tempfile.mkdtemp(prefix="skl_", dir=_BASE[0]))
        for side in ("before", "after"):
            (d / side).mkdir()
            ws.copy_tree(d / side)
        patch(d / "after")
        _W.update(before=d / "before", after=d / "after", dir=d)
    res = {"i": i, "probe": probe, "file": f, "pos": pos, "text": text, "new": new}
    for side in ("before", "after"):
        p = _W[side] / f
        orig = p.read_text(encoding="utf-8")
        assert orig[pos:pos + len(text)] == text
        p.write_text(orig[:pos] + new + orig[pos + len(text):], encoding="utf-8")
        try:
            r = ws.run(_W[side], TC)
        finally:
            p.write_text(orig, encoding="utf-8")
        res[side] = {"verdict": ws.verdict(r), "errors": r["errors"], "secs": r["secs"], "stderr": r["stderr"]}
    return res


def ks(errors):
    return {k for k, t in K_TEXT.items() for e in errors or [] if t in e and not e.startswith("法則 ")}


def laws(errors):
    return {m.group(1) for e in errors or [] if (m := re.match(r"法則 (\S+?)（", e))}


def main():
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        before, after = Path(td) / "before", Path(td) / "after"
        before.mkdir()
        after.mkdir()
        ws.copy_tree(before)
        ws.copy_tree(after)
        try:
            patch(after)
        except AssertionError as e:
            OUT.write_text(json.dumps({"patch_failed": str(e)}, ensure_ascii=False, indent=1), encoding="utf-8")
            sys.exit("patch failed")
        A = {side: {s: ws.run(tree, s) for s in CI} for side, tree in (("before", before), ("after", after))}
        for side in A:
            for s, r in A[side].items():
                print("A", side, s, r["code"], r["last"][:80], flush=True)
        all_sites = sites(before)
    chosen = [(i, *s) for i, s in enumerate(all_sites) if i % STEP == 0]
    tasks = []
    for i, f, pos, text, verb, end, name in chosen:
        for probe, value in PROBES:
            new = mutate(text, end, name, probe, value)
            if new is not None and new != text:
                tasks.append((i, probe, f, pos, text, new))
    print("sites", len(all_sites), "chosen", len(chosen), "tasks", len(tasks), flush=True)
    rows = []
    with tempfile.TemporaryDirectory() as base, ProcessPoolExecutor(WORKERS, initializer=init, initargs=(base,)) as ex:
        for r in ex.map(worker, tasks):
            rows.append(r)
            print("B", r["i"], r["probe"], r["file"], r["before"]["verdict"], r["after"]["verdict"], flush=True)

    status = Counter()
    k_before, k_covered = Counter(), Counter()
    for r in rows:
        b, a = r["before"]["verdict"], r["after"]["verdict"]
        if b == "broke" and a == "broke":
            r["status"] = "not_run"
        elif b == a:
            r["status"] = "agree"
        elif b == "reject" and a == "accept":
            r["status"] = "missed"
        elif b == "accept" and a == "reject":
            r["status"] = "over"
        else:
            r["status"] = "broke"
        status[r["status"]] += 1
        la = laws(r["after"]["errors"])
        for k in ks(r["before"]["errors"]):
            k_before[k] += 1
            if la & set(K_LAWS[k]):
                k_covered[k] += 1
    n_ran = len(rows) - status["not_run"]
    n_disagree = status["missed"] + status["over"] + status["broke"]
    before_ok = all(r["code"] == 0 for r in A["before"].values())
    after_ok = all(r["code"] == 0 for r in A["after"].values())
    n_k = sum(k_before.values())
    C = (sum(k_covered.values()) / n_k) if n_k else None
    law_counts = Counter(l for r in rows for e in r["after"]["errors"] or [] for l in laws([e]))
    new_law_only = sum(1 for r in rows if r["status"] == "over"
                       and laws(r["after"]["errors"]) & {x for v in K_LAWS.values() for x in v})
    summary = {
        "n_sites": len(all_sites), "n_chosen": len(chosen), "n_tasks": len(rows), "n_ran": n_ran,
        "n_agree": status["agree"], "n_missed": status["missed"], "n_over": status["over"],
        "n_broke": status["broke"], "n_not_run": status["not_run"], "n_disagree": n_disagree,
        "k_before": dict(k_before), "k_covered": dict(k_covered), "C": C,
        "over_with_new_laws": new_law_only,
        "by_probe": {p: dict(Counter(r["status"] for r in rows if r["probe"] == p)) for p, _ in PROBES},
        "A_before_ok": before_ok, "A_after_ok": after_ok,
        "A_tc_last_same": A["before"][TC]["last"] == A["after"][TC]["last"],
        "after_law_counts": dict(law_counts.most_common()),
        "secs": round(time.time() - t0, 1),
    }
    if not before_ok or n_ran < 50 or any(k_before[k] == 0 for k in K_TEXT):
        judgment = "not_judged"
    elif not after_ok or n_disagree > 0:
        judgment = "refute"
    elif C == 1:
        judgment = "support"
    else:
        judgment = "undecided"
    OUT.write_text(json.dumps({"summary": summary, "judgment": {"h_spot_kind_checks_as_law": judgment},
                               "A": A, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps({"h_spot_kind_checks_as_law": judgment}))


if __name__ == "__main__":
    main()
