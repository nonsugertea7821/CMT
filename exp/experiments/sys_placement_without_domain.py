"""h_placement_without_domain を確かめる: syntax の文 axis を二つの文に分ければ、上位で決まる置き場の法則は domain に依存しないか。

仮説（claims.yaml）: v_refer(h, v_not_depend(placement_by_above, syntax.domain))。登録 2a28412。issue #413。
  出どころ: sys_placement_in_laws（元の手順）で、法則 place_axis の前提 exists(x), axis(x, a) が、ノードの軸（sai, cm, yen など）
  にも当たり、law_Q0 = 6 になった。訂正（sys_placement_in_laws_fix）で前提を domain(x, d) に替えると agree = 7 になった。
  文 axis が「ノードが持つ数の軸」と「軸の上位」の二つに使われているのが原因、という読み。

操作: sys_placement_in_laws と同じく一時の写しで行う（体系のファイルと検査器は書き換えない）。版・数える量は訂正（_fix）と同じ。
  違いは二つだけ:
  1. 法則 place_verb・place_mod・place_axis の前提は、元の手順の exists(x) のまま（domain を使わない）。
  2. 写しの中で、文 axis を二つに分ける:
     検査器の syntax_facts で、軸の上下（AX の extends）を書く行 add("axis", aid, a["extends"]) を、新しい文 axis_up にする。
     ノードの axis と、限定の at の軸は、文 axis のまま。
     syntax.yaml の写しで、軸の上下を読む前提を axis_up にする:
       entail_by_axis の axis(var1, var2)（上位の軸を含意する側）と、entail_by_axis_step の axis(var2, var3)。
       entail_by_axis の axis(var3, var1)（ノードが軸を持つ側）、own_by_axis、at_axis は axis のまま。
  版: Q0〜Q6（Q1・Q2 は訂正と同じ from・to を持つ形）。
数える量（版ごと）: py_<v>、law_<v>、other_<v>、agree（訂正と同じ定め方）。
行（sys_placement_without_domain.json）: "summary 要約" と "texts"（訂正と同じ形）。

判定（事前に決める）:
  other_Q0 > 0（分けたこと自体が誤りを出す。たとえば文 axis_up を検査器が知らない）か、どれかの版が例外で止まれば外れ（状態を変えない）。
  支持: agree = 7 かつ law_Q0 = 0（domain なしで、検査器と同じに見分ける）。
  反証: agree < 7 か law_Q0 > 0。
開示:
  - 元の手順で、exists が軸（sai など）にも当たったことは見ている。軸が exists を持つのは、AX の軸がノードとしても
    置かれているからかもしれず、そうなら axis を分けても exists(sai) と axis(sai, amount) が残り、law_Q0 > 0 になりうる。
    その場合は反証になり、原因は「文の二重の使い方」ではなく「軸がノードでもある」ことだと読む。
  - entail_by_axis の二つの前提のどちらが軸の上下かは、変数の並び（var3 が var1 を持ち、var1 が var2 の下）から読んだ。
  - 走らせる前に、写しの build は試していない。
使い方:
  python exp/experiments/sys_placement_without_domain.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_placement_in_laws as base

base.OUT = base.ROOT / "exp/experiments/results/sys_placement_without_domain.json"
base.CASES["Q1"] = "  zz_v: {display: 試しV, extends: quality, from: continuant, to: any, holds: [{is: refer, from: from, to: to}]}\n"
base.CASES["Q2"] = "  zz_v: {display: 試しV, extends: occurrent, from: continuant, to: any, holds: [{is: refer, from: from, to: to}]}\n"
TC = "cscl/bootstrap/type_checker/type_checker.py"
SPLIT_TC = ('add("axis", aid, a["extends"])', 'add("axis_up", aid, a["extends"])')
SPLIT_SYN = [
    ("  - {is: v_assume, from: entail_by_axis, to: {is: axis, from: var1, to: var2}}\n",
     "  - {is: v_assume, from: entail_by_axis, to: {is: axis_up, from: var1, to: var2}}\n"),
    ("  - {is: v_assume, from: entail_by_axis_step, to: {is: axis, from: var2, to: var3}}\n",
     "  - {is: v_assume, from: entail_by_axis_step, to: {is: axis_up, from: var2, to: var3}}\n"),
]


def swap(s, old, new):
    assert s.count(old) == 1, old
    return s.replace(old, new)


def run(case):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(base.ROOT / "cscl.yaml", d / "cscl.yaml")
        shutil.copytree(base.ROOT / "cscl", d / "cscl")
        shutil.copytree(base.ROOT / "exp/src", d / "exp/src")
        p = d / base.SYN
        s = base.put(base.put(p.read_text(), base.LAW_IND_ANCHOR, base.LAW_INDS), base.LAW_FACT_ANCHOR, base.LAW_FACTS)
        for old, new in SPLIT_SYN:
            s = swap(s, old, new)
        p.write_text(s)
        p = d / TC
        p.write_text(swap(p.read_text(), *SPLIT_TC))
        if base.CASES[case]:
            p = d / base.CLAIMS
            p.write_text(base.put(p.read_text(), base.NODE_ANCHOR, base.CASES[case]))
        r = subprocess.run([sys.executable, "-c", base.PROBE], cwd=d, capture_output=True, text=True)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return {"py": -1, "law": -1, "other": -1, "texts": [(r.stderr or r.stdout)[-500:]]}


base.run = run

if __name__ == "__main__":
    base.main()
