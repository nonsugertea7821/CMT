"""仮説の PR を、条件を満たすときだけ自動でマージする。前提は仮説 h_auto_merge_uncorrected（exp/src/exp.yaml）。

条件（すべて満たすとき、マージする。1つでも外れたら何もしない。外れた理由をジョブの要約に書く）:
  1. ブランチが claude/h_<名前>。仮説 h_<名前> が base（main）にある
  2. Draft でない
  3. 触るファイルが、cscl/design/claims.yaml、exp/src/*.yaml、exp/experiments/*.py、exp/experiments/results/* だけ
     （評価器・文法・ワークフローを変える PR は手で見る）
  4. 仮説の状態が、base で未検証（hyp_untested）、head で支持（hyp_supported）か反証（hyp_refuted）。mixed は手で見る
  5. 事前登録: 実験スクリプトを1つ以上、結果ファイルを1つ以上含む。各スクリプトを触る commit はちょうど1つで、
     結果ファイルを触らず、結果ファイルを触るどの commit よりも前にある
  6. 訂正がない: 各スクリプトの「訂正」で始まる行の数が、base と head で同じ
型検査（tc）と exp の検査（ec）は、ワークフローの前の段で走らせる（通らなければここまで来ない）。
GITHUB_TOKEN でマージした push では他のワークフローが起きないので、issue の同期はワークフローの後の段で走らせる。

使い方（ワークフローが呼ぶ）:
  python .github/scripts/auto_merge.py BASE_SHA HEAD_SHA            判定だけ（GITHUB_OUTPUT に merge=true|false）
  python .github/scripts/auto_merge.py BASE_SHA HEAD_SHA --merge    判定して、満たせばマージする（GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER）
  環境変数 HEAD_REF（ブランチ名）、DRAFT（true|false）
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

import yaml

BRANCH = re.compile(r"^claude/(h_[a-z0-9_]+)$")
ALLOWED = re.compile(r"^(cscl/design/claims\.yaml|exp/src/[^/]+\.yaml|exp/experiments/[^/]+\.py|exp/experiments/results/[^/]+)$")
SCRIPT = re.compile(r"^exp/experiments/[^/]+\.py$")
RESULT = re.compile(r"^exp/experiments/results/[^/]+$")
CORRECTION = re.compile(r"^\s*訂正", re.M)
STATUS_FILES = ("cscl/design/claims.yaml", "exp/src/exp.yaml")


def decide(ref, draft, files, commits, status_base, status_head, scripts):
    """外れた条件の理由の一覧（空ならマージしてよい）。
    commits: [(sha, [触ったファイル])] を古い順。scripts: {スクリプト: (base の中身か None, head の中身)}。"""
    why = []
    m = BRANCH.match(ref or "")
    if not m:
        return [f"ブランチ {ref} が claude/h_<名前> でない"]
    h = m.group(1)
    if draft:
        why.append("Draft である")
    bad = [f for f in files if not ALLOWED.match(f)]
    if bad:
        why.append("範囲の外のファイルを触る: " + ", ".join(bad[:5]))
    if status_base is None:
        why.append(f"{h} が base にない")
    elif status_base != "hyp_untested":
        why.append(f"{h} の base の状態が {status_base}（未検証でない）")
    if status_head not in ("hyp_supported", "hyp_refuted"):
        why.append(f"{h} の head の状態が {status_head}（支持・反証でない）")
    ss = [f for f in files if SCRIPT.match(f)]
    rs = [f for f in files if RESULT.match(f)]
    if not ss:
        why.append("実験スクリプトがない")
    if not rs:
        why.append("結果ファイルがない")
    first_result = min((i for i, (_, fs) in enumerate(commits) if any(RESULT.match(f) for f in fs)), default=None)
    for s in ss:
        ix = [i for i, (_, fs) in enumerate(commits) if s in fs]
        if len(ix) != 1:
            why.append(f"{s} を触る commit が {len(ix)} 個（1つでない）")
            continue
        if any(RESULT.match(f) for f in commits[ix[0]][1]):
            why.append(f"{s} を、結果ファイルと同じ commit で触る")
        if first_result is not None and ix[0] > first_result:
            why.append(f"{s} が、結果ファイルより後の commit にある")
        old, new = scripts.get(s, (None, ""))
        if len(CORRECTION.findall(new or "")) != len(CORRECTION.findall(old or "")):
            why.append(f"{s} に訂正がある")
    return why


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout


def show(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def status(rev, h):
    for p in STATUS_FILES:
        y = yaml.safe_load(show(rev, p) or "") or {}
        x = (y.get("individuals") or {}).get(h)
        if isinstance(x, dict):
            return str(x.get("is", "")).split(".")[-1]
    return None


def gather(base, head):
    ref = os.environ.get("HEAD_REF", "")
    m = BRANCH.match(ref)
    h = m.group(1) if m else None
    files = [f for f in git("diff", "--name-only", f"{base}...{head}").split() if f]
    commits = [(c, [f for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c).split() if f])
               for c in git("rev-list", "--reverse", f"{base}..{head}").split()]
    scripts = {f: (show(base, f), show(head, f)) for f in files if SCRIPT.match(f)}
    return dict(ref=ref, draft=os.environ.get("DRAFT") == "true", files=files, commits=commits,
                status_base=status(base, h) if h else None, status_head=status(head, h) if h else None, scripts=scripts)


def merge(head):
    repo, n = os.environ["GITHUB_REPOSITORY"], os.environ["PR_NUMBER"]
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/pulls/{n}/merge", method="PUT",
                                 data=json.dumps({"sha": head, "merge_method": "merge"}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main(base, head, do_merge):
    why = decide(**gather(base, head))
    lines = ["## 自動マージの判定", ""] + (["条件をすべて満たす。マージする。"] if not why else
                                         ["手で見る（外れた条件）:"] + [f"- {w}" for w in why])
    print("\n".join(lines))
    for k, v in (("GITHUB_STEP_SUMMARY", "\n".join(lines) + "\n"), ("GITHUB_OUTPUT", f"merge={'false' if why else 'true'}\n")):
        if os.environ.get(k):
            with open(os.environ[k], "a", encoding="utf-8") as f:
                f.write(v)
    if do_merge and not why:
        print(merge(head).get("message", ""))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--merge" in sys.argv[3:])
