"""端の法則を本物の体系に入れ、検査器のコードの端の検査を外しても、体系の全ファイルで検査の結果が変わらないか（h_endpoint_law_whole_system）。

系列:
  #917: 相手の名を「領域の事実を持つか any か」で求め、端の誤り 54 すべてを法則で名指した（支持）。
  #920: 法則を足し、コードの端の検査 2 つを外した写しで、subj.yaml の 59 行の材料のうち走った 50 行の受け入れ・退けが一致した（支持）。
  ただし #920 の材料は subj.yaml の行だけで、検査は build() だけだった。
  仮説: h_endpoint_law_whole_system: v_depend(type_check_result, [syntax.law_rule, syntax.domain])

手（一時の写しだけを替える。リポジトリの体系と検査器は替えない）:
  before: 今の木そのまま（git ls-files の全ファイルを写す）。
  after: 写しに #920 と同じ patch を当てる（syntax.yaml に法則を足し、type_checker.py の端の誤りの err 2 つを pass に替える）。

材料（モデルは走らせない）:
  A. 体系そのまま: CI と同じ 4 つの検査（type_checker.py、exp_check.py、runtime.py、test_worlds.py）を before と after で走らせる。
  B. 端の入れ替え: 体系の yaml（cscl.yaml、cscl/ 以下、exp/src/ 以下）の中の「of: [<動詞>, from]」「of: [<動詞>, to]」を、
     ファイル名の順・ファイルの中の位置の順に並べ、0 から数えて 4 で割り切れる番号のものだけを選ぶ。
     選んだ 1 つずつ、from と to を入れ替えた写しで type_checker.py を走らせる（1 つずつ。ほかは元のまま）。
     入れ替えは、ありがちな書き違い（端を取り違える）を作るため。どれが誤りになるかは前もって決めない。

手順:
  1. before と after の写しを作る。after に patch を当てる（当てる場所が 1 つずつ見つからなければ止め、判定しない）。
  2. A を両方で走らせる。
  3. B の各入れ替えを、両方の写しで走らせる。結果は「受け入れ」（終了コード 0）、「退け」（「検査に失敗」の行があり終了コード 1）、
     「壊れ」（それ以外）。
  4. 一致: 両方が受け入れか退けで、同じもの。不一致: 取りこぼし（before 退け・after 受け入れ）、余分な退け（before 受け入れ・after 退け）、
     壊れの違い（片方だけ壊れ）。両方壊れは「走らず」として別に数える。

判定（事前登録）:
  前提: before の A の 4 つがすべて終了コード 0。満たさなければ判定しない。B で両方が走った入れ替えが 50 未満なら判定しない。
  h_endpoint_law_whole_system:
    after の A の 4 つがすべて終了コード 0、かつ B の不一致が 0 なら支持。
    after の A のどれかが 0 でない、または B の不一致が 1 以上なら反証。
  参考（判定に使わない）: A の type_checker.py の出力の最後の行（ノードの数など）が前後で同じか、
    B で退けた入れ替えのうち、before が端の誤り（「に来られない」）だけで退けたものの数、after の誤りの法則ごとの数、走る時間。

開示（結果を見る前に分かっていること）:
  - #920 の結果を読んでいる（59 行で一致 50、不一致 0、走らず 9）。
  - 時間を見積もるため、この登録の前に、今の木で type_checker.py を 1 度走らせた（約 22 秒、成功）。手元で tc を走らせない取り決めに反する。
    出力は最後の行（領域ごとの数）だけを見た。
  - B は 4 つに 1 つだけ（登録の前に数えた: 全部で 1199 か所、選ぶのは 300。grep で数えたときは 1048 と読み違えた）。選び方は番号だけで決め、中身を見て選ばない。
  - exp.yaml と cscl/trial も B の対象に入る（体系の yaml だから）。
  - 支持でも、言えるのは、この入れ替え方の誤りと体系そのままで、受け入れ・退けが変わらないこと。誤りの文面は変わりうる（#920 で増えた）。
  - 反証でも「規則で書けない」とまでは言えない。言えるのは、この法則と、この外し方では、どこかで線が変わること。

出力: results/sys_endpoint_law_whole_system.json
使い方:
  python exp/experiments/sys_endpoint_law_whole_system.py
"""
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_endpoint_law_replaces_code as elrc

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_endpoint_law_whole_system.json"
TC = "cscl/bootstrap/type_checker/type_checker.py"
CI = (TC, "exp/src/exp_check.py", "cscl/bootstrap/runtime/runtime.py", "cscl/bootstrap/runtime/test_worlds.py")
PAT = re.compile(r"of: \[([A-Za-z_][A-Za-z0-9_.]*), (from|to)\]")
STEP = 4
WORKERS = 4


def copy_tree(dst):
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    tar = subprocess.run(["tar", "--null", "-T", "-", "-c"], cwd=ROOT, input=files, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar, check=True)


def run(tree, script):
    t = time.time()
    out = subprocess.run([sys.executable, script], cwd=tree, capture_output=True, text=True)
    lines = out.stdout.strip().splitlines()
    return {"code": out.returncode, "last": lines[-1] if lines else "", "secs": round(time.time() - t, 1),
            "errors": [ln[3:] for ln in lines if ln.startswith(" - ")] if script == TC else None,
            "failed_line": any(ln.startswith("検査に失敗") for ln in lines),
            "stderr": out.stderr[-300:] if out.returncode not in (0, 1) else ""}


def verdict(r):
    if r["code"] == 0:
        return "accept"
    if r["code"] == 1 and r["failed_line"]:
        return "reject"
    return "broke"


def sites(tree):
    files = sorted(p.relative_to(tree).as_posix() for base in ("cscl.yaml", "cscl", "exp/src")
                   for p in ([tree / base] if (tree / base).is_file() else (tree / base).rglob("*.yaml")))
    out = []
    for f in files:
        s = (tree / f).read_text(encoding="utf-8")
        for m in PAT.finditer(s):
            out.append((f, m.start(), m.group(0), m.group(1), m.group(2)))
    return out


_W = {}
_BASE = []


def init(base):
    _BASE.append(base)


def worker(task):
    i, f, pos, text, verb, end = task
    if not _W:
        d = Path(tempfile.mkdtemp(prefix="elws_", dir=_BASE[0]))
        for side in ("before", "after"):
            (d / side).mkdir()
            copy_tree(d / side)
        elrc.patch(d / "after")
        _W.update(before=d / "before", after=d / "after", dir=d)
    new = text.replace(f", {end}]", ", " + ("to" if end == "from" else "from") + "]")
    res = {"i": i, "file": f, "pos": pos, "text": text, "new": new}
    for side in ("before", "after"):
        p = _W[side] / f
        orig = p.read_text(encoding="utf-8")
        assert orig[pos:pos + len(text)] == text
        p.write_text(orig[:pos] + new + orig[pos + len(text):], encoding="utf-8")
        try:
            r = run(_W[side], TC)
        finally:
            p.write_text(orig, encoding="utf-8")
        res[side] = {"verdict": verdict(r), "errors": r["errors"], "secs": r["secs"], "stderr": r["stderr"]}
    return res


def main():
    with tempfile.TemporaryDirectory() as td:
        before, after = Path(td) / "before", Path(td) / "after"
        before.mkdir()
        after.mkdir()
        copy_tree(before)
        copy_tree(after)
        try:
            elrc.patch(after)
        except AssertionError as e:
            OUT.write_text(json.dumps({"patch_failed": str(e)}, ensure_ascii=False, indent=1), encoding="utf-8")
            sys.exit("patch failed")
        A = {side: {s: run(tree, s) for s in CI} for side, tree in (("before", before), ("after", after))}
        for side in A:
            for s, r in A[side].items():
                print("A", side, s, r["code"], r["last"][:80], flush=True)
        all_sites = sites(before)
    chosen = [(i, *s) for i, s in enumerate(all_sites) if i % STEP == 0]
    print("sites", len(all_sites), "chosen", len(chosen), flush=True)
    rows = []
    with tempfile.TemporaryDirectory() as base, ProcessPoolExecutor(WORKERS, initializer=init, initargs=(base,)) as ex:
        for r in ex.map(worker, chosen):
            rows.append(r)
            print("B", r["i"], r["file"], r["before"]["verdict"], r["after"]["verdict"], flush=True)

    status = Counter()
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
    n_ran = len(rows) - status["not_run"]
    n_disagree = status["missed"] + status["over"] + status["broke"]
    before_ok = all(r["code"] == 0 for r in A["before"].values())
    after_ok = all(r["code"] == 0 for r in A["after"].values())
    endpoint_only = sum(1 for r in rows if r["before"]["verdict"] == "reject" and r["before"]["errors"]
                        and all("に来られない" in e for e in r["before"]["errors"]))
    law_counts = Counter(m.group(1) for r in rows if r["after"]["errors"] for e in r["after"]["errors"]
                         if (m := re.match(r"法則 (\S+?)（", e)))
    summary = {
        "n_sites": len(all_sites), "n_chosen": len(rows), "n_ran": n_ran,
        "n_agree": status["agree"], "n_missed": status["missed"], "n_over": status["over"],
        "n_broke": status["broke"], "n_not_run": status["not_run"], "n_disagree": n_disagree,
        "n_rejected_before": sum(1 for r in rows if r["before"]["verdict"] == "reject"),
        "n_endpoint_only_before": endpoint_only,
        "A_before_ok": before_ok, "A_after_ok": after_ok,
        "A_before_failures": sum(1 for r in A["before"].values() if r["code"] != 0),
        "A_after_failures": sum(1 for r in A["after"].values() if r["code"] != 0),
        "A_tc_last_same": A["before"][TC]["last"] == A["after"][TC]["last"],
        "after_law_counts": dict(law_counts.most_common()),
    }
    if not before_ok or n_ran < 50:
        judgment = "not_judged"
    elif after_ok and n_disagree == 0:
        judgment = "support"
    else:
        judgment = "refute"
    OUT.write_text(json.dumps({"summary": summary, "judgment": {"h_endpoint_law_whole_system": judgment},
                               "A": A, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps({"h_endpoint_law_whole_system": judgment}))


if __name__ == "__main__":
    main()
