"""auto_merge.decide の確かめ（git と GitHub に触らない）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_merge import decide, decide_registration  # noqa: E402

S = "exp/experiments/sys_x.py"
R = "exp/experiments/results/sys_x_after.json"
C = "cscl/design/claims.yaml"
OK = dict(ref="claude/h_x", draft=False, files=[S, R, C],
          commits=[("a", [S]), ("b", [R]), ("c", [C])],
          status_base="hyp_untested", status_head="hyp_supported", scripts={S: (None, '"""手順\n判定\n"""\n')})


def case(**kw):
    return decide(**(OK | kw))


G = ["  h_x: {is: exp.hyp_untested}", "  b_x: {is: exp.item_queued}",
     "  - {is: v_refer, from: h_x, to: {is: v_depend, from: a, to: b}}", "  - {is: exp.v_check, from: b_x, to: h_x}"]


def reg(**kw):
    return decide_registration(**(dict(draft=False, files=[C], added=G, removed=[]) | kw))


def main():
    checks = {
        "すべて満たす": case() == [],
        "反証でもよい": case(status_head="hyp_refuted") == [],
        "ブランチ名": bool(case(ref="claude/cross")),
        "Draft": bool(case(draft=True)),
        "範囲の外": bool(case(files=[S, R, C, "cscl/bootstrap/type_checker/type_checker.py"])),
        "base にない": bool(case(status_base=None)),
        "base が未検証でない": bool(case(status_base="hyp_supported")),
        "mixed": bool(case(status_head="hyp_mixed")),
        "未検証のまま": bool(case(status_head="hyp_untested")),
        "スクリプトがない": bool(case(files=[R, C], scripts={})),
        "結果がない": bool(case(files=[S, C], commits=[("a", [S]), ("c", [C])])),
        "スクリプトを2回触る": bool(case(commits=[("a", [S]), ("b", [R]), ("c", [S, C])])),
        "結果と同じ commit": bool(case(commits=[("a", [S, R]), ("c", [C])])),
        "結果の後に登録": bool(case(commits=[("b", [R]), ("a", [S]), ("c", [C])])),
        "訂正がある": bool(case(scripts={S: (None, '"""手順\n訂正（after の後）: 直した\n"""\n')})),
        "既存の訂正は数えない": case(scripts={S: ("訂正（前）: x\n", "訂正（前）: x\n追記\n")}) == [],
        "登録: すべて満たす": reg() == [],
        "登録: exp.yaml でもよい": reg(files=["exp/src/exp.yaml"], added=[l.replace("exp.", "") for l in G]) == [],
        "登録: Draft": bool(reg(draft=True)),
        "登録: 範囲の外": bool(reg(files=[C, ".github/scripts/auto_merge.py"])),
        "登録: 消す行": bool(reg(removed=["  h_y: {is: exp.hyp_untested}"])),
        "登録: 状態を変える": bool(reg(added=G + ["  h_y: {is: exp.hyp_supported}"])),
        "登録: 概念を足す": bool(reg(added=G + ["  a: {display: x, extends: quality}"])),
        "登録: 観察を足す": bool(reg(added=G + ["  - {is: exp.v_support, from: o_x, to: h_x}"])),
        "登録: v_check がない": bool(reg(added=G[:3])),
        "登録: v_refer がない": bool(reg(added=G[:2] + G[3:])),
        "登録: v_refer が2つ": bool(reg(added=G + [G[2]])),
        "登録: 既存の仮説に v_refer": bool(reg(added=G + ["  - {is: v_refer, from: h_y, to: {is: v_depend, from: a, to: b}}"])),
        "登録: 仮説がない": bool(reg(added=[])),
    }
    bad = [k for k, v in checks.items() if not v]
    print("自動マージの判定の確かめ:", "成功" if not bad else "失敗 " + ", ".join(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
