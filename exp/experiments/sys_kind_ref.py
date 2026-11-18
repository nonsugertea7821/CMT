"""体系そのものを数える: 「動詞そのもの（種類）を指す」ことを式で書くと、種類と成員の未分化による過大拡張が規則だけで止まるか。
結果を見る前に、この説明と手順を登録した。

背景（会話）: sys_meet で、残る違反 6 組のうち 3 組（run, attendance, plan → verb_ref）は、verb_ref の定義が
  「生起体へ述べる」（refer_from_occurrent）だけで、起こったこと（成員）を指すものと、動詞そのもの（種類）を指すものを区別しない
  ことによる。区別は verb_ref の注釈（この位置には動詞そのものが来る）と、型検査が名前で verb_ref を読むところにだけある。
  基礎の動詞 is（属する）は、始点が成員、終点が種類（kind）。「起こったことが属する種類」は、動詞そのもの。
操作（この手順の登録のあと、測る前に行う。cscl/library/syntax/syntax.yaml だけを変える）:
  1. verb_ref を {extends: kind, mod: {of: [is, to], with: occurrent}} にする（起こったことが属する種類）。display と注釈は変えない。
  2. information_entity_refer_from_p の上位を verb_ref から information_entity に替える。この概念が verb_ref の下にあったのは、
     自分の式 refer_from_p（関係づけるへ述べる）が verb_ref の古い式を含意したからで、その含意は 1 でなくなる。
  ほかは変えない。

数え方（引数 before / after。sys_unit_axis と同じ V の数え方）:
  errors      型検査の誤りの数
  V           違反の組の数
  v_verb_ref  verb_ref が上の違反の組の数
  new_V       before にない違反の組の数
判定: after で errors 0、v_verb_ref 0、new_V 0 の3つを満たせば「種類を指すことを式で書くと、この過大拡張は規則だけで止まる」。
  満たさないものは、その内容を書いて外れとする。
登録の前に分かっていること: sys_meet（V 6、そのうち verb_ref が 3 組）。
見込み: 3つとも満たし、V は 3（position→opposite, backlog_item→hypothesis, control_preservation→context_following が残る）。
  opposite も動詞そのものを指すが、この操作では変えない（position も種類の側を指すので、opposite だけ変えても組の意味が定まらない）。
訂正（after を測ったあと）: after は errors 1 で外れた（V 3、v_verb_ref 0、new_V 0）。誤りは「syntax.verb_ref.mod[0]:
  ontology.occurrent は種類でない」。型検査が is（属する）の限定を名前で読むところ（「属する」の終点は種類そのもの）が、
  with が終点の側にあるとき（of: [is, from]）だけでなく、始点の側にあるとき（of: [is, to]。with は成員の種類）にも当てはまっていた。
  型検査を、with が終点の側にあるときだけに直す（今の体系の導いた文は変わらないことを確かめた）。同じ操作をして、同じ判定で
  測り直す（引数 after2）。after の結果はそのまま記録する。

行（sys_kind_ref_<引数>.json）:
  "summary 要約": errors, V, v_verb_ref, new_V
  "V x→y":        1

使い方:
  python exp/experiments/sys_kind_ref.py before|after|after2
"""
import collections
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"


def main(label):
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    F = tc.Facts(T.syntax_facts())
    tc.evaluate(tc.law_rules(O), F, tc.variables(O))
    rel = lambda r: F.by.get(r, set())

    def two(r):
        d = collections.defaultdict(set)
        for t in rel(r):
            if len(t) == 2:
                d[t[0]].add(t[1])
        return d
    acc, has = two("r_acc"), two("r_has")
    V = sorted((x, y) for x, y in rel("r_candidate") if acc[y] <= has[x] and not acc[y] <= acc[x])
    before = set()
    if label != "before":
        rows = json.loads((OUT / "sys_kind_ref_before.json").read_text(encoding="utf-8"))["rows"]
        before = {tuple(k[2:].split("→")) for k in rows if k.startswith("V ")}
    summ = {"errors": len(tc.errors), "V": len(V), "v_verb_ref": sum(1 for _, b in V if b == "syntax.verb_ref"),
            "new_V": sum(1 for p in V if p not in before) if label != "before" else 0}
    rows = {"summary 要約": summ} | {f"V {a}→{b}": {"v": 1} for a, b in V}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / f"sys_kind_ref_{label}.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print([f"{a}→{b}" for a, b in V])
    for e in tc.errors:
        print(e)


if __name__ == "__main__":
    assert sys.argv[1:] in (["before"], ["after"], ["after2"])
    main(sys.argv[1])
