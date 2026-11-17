"""実行器の、文の読み方と世界の対称性を確かめる。

文の読み方は3つ: 真である（真と述べてあれば真）、偽である（val: {truth: false}。偽と述べてあれば真）、
述べられていない（neg）。確かめること:
  1. 真と述べた文と偽と述べた文は、鏡の関係にある。どちらも、どの世界でも決められる。
  2. 述べていない文の真偽は、世界が与える。閉世界は偽を与え、世界（world）だけなら与えない（決められない）。
  3. 述べられていないかは、記録だけで決まるので、どの世界でも決められる。
  4. 作る動詞（pre が「述べられていない」）は、どちらの世界でも動ける。壊す動詞が述べたことを取り消すと、
     その文の真偽は、閉世界では偽、world だけなら決められない。

使い方: python cscl/bootstrap/runtime/test_worlds.py
"""
import contextlib
import io
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent / "type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import runtime as rt
    from type_checker import Ontology, load, merge_domain, register_domains, root_name

U = rt.UNSTATED
fails = []


def machine(world, facts):
    O = load(root_name())
    for _, name in register_domains(O):
        merge_domain(name, O)
    run = {"individuals": {"a": {"is": "continuant"}, "b": {"is": "continuant"}, "k": {"is": "realizable_entity"},
                           "t": {"is": "continuant"}, "f": {"is": "continuant"}, "u": {"is": "continuant"}},
           "facts": facts}
    return rt.Machine(Ontology(O), run, "test_worlds", world)


def want(m, x, reading, expected, what):
    got = m.holds(reading, "exists", (x,))
    if got != expected:
        fails.append(f"{m.world}: {what}: {rt.show_atom(reading, 'exists', (x,))} は {expected} のはずが {got}")


START = [{"is": "exists", "from": "a"}, {"is": "exists", "from": "b"},
         {"is": "exists", "from": "t"}, {"is": "exists", "from": "f", "val": {"truth": False}}]
for world, default in rt.WORLDS.items():
    m = machine(world, START)
    flip = None if default is None else not default
    # 1. 述べた文は鏡の関係。世界によらない
    want(m, "t", True, True, "真と述べた文")
    want(m, "t", False, False, "真と述べた文")
    want(m, "f", False, True, "偽と述べた文")
    want(m, "f", True, False, "偽と述べた文")
    # 2. 述べていない文の真偽は、世界が与える
    want(m, "u", True, default, "述べていない文")
    want(m, "u", False, flip, "述べていない文")
    # 3. 述べられていないかは、記録だけで決まる
    for x, e in (("t", False), ("f", False), ("u", True)):
        want(m, x, U, e, "述べられていないか")
    # 4. 作る・壊す
    m.step("std.v_learn", {"from": "a", "to": "b", "new": "k"}, "learn")
    want(m, "k", True, True, "作ったあと")
    m.step("std.v_freeze", {"from": "b", "to": "a", "new": "k"}, "freeze")
    want(m, "k", U, True, "壊したあと")
    want(m, "k", True, default, "壊したあと")
    m.step("std.v_learn", {"from": "a", "to": "b", "new": "k"}, "learn again")
    want(m, "k", True, True, "作り直したあと")
    fails += m.errors

if fails:
    print(f"世界の対称性の確認に失敗: {len(fails)} 件")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print(f"世界の対称性の確認に成功: 世界 {len(rt.WORLDS)}（{', '.join(rt.WORLDS)}）、述べた文の真偽は世界によらず、述べていない文の真偽だけが世界で決まる")
