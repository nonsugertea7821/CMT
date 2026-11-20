"""main と衝突している PR に、コメントで知らせる。

PR を見張るセッションには、コメントは届くが、衝突は届かない。そこで main への push のたびに開いている PR を調べ、
衝突していれば印 MARK の付いたコメントを書く。同じ head と同じ main について書いたものがあれば、書き足さない。

GitHub が衝突の有無を計算し終えなかった PR は、番号を GITHUB_OUTPUT の undecided に書く。
ワークフローは、それがあれば 30 分待って、その PR だけをもう一度調べる。

使い方（ワークフローが呼ぶ）: python .github/scripts/conflict_notice.py MAIN_SHA [PR番号,PR番号...]
  PR 番号を渡せば、その PR だけを調べる。渡さなければ、開いている PR をすべて調べる。
  環境変数 GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_OUTPUT（なくてもよい）
"""
import json
import os
import sys
import time
import urllib.request

MARK = "<!-- merge-conflict -->"


def api(path, method="GET", body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def mergeable(n):
    """GitHub は mergeable を遅れて計算する（null の間は待つ）。"""
    for _ in range(10):
        pr = api(f"pulls/{n}")
        if pr["mergeable"] is not None:
            return pr
        time.sleep(6)
    return pr


def main():
    base = sys.argv[1]
    if len(sys.argv) > 2:
        numbers = [int(n) for n in sys.argv[2].split(",") if n]
    else:
        numbers = [p["number"] for p in api("pulls?state=open&base=main&per_page=100")]
    undecided = []
    for n in numbers:
        pr = mergeable(n)
        if pr["state"] != "open":
            continue
        if pr["mergeable"] is None:
            undecided.append(n)
            print(f"#{n}: 衝突の有無が決まらない。後でもう一度調べる")
            continue
        if pr["mergeable"] is not False:
            continue
        p = pr
        head = pr["head"]["sha"]
        key = f"head {head[:7]} / main {base[:7]}"
        old = [c for c in api(f"issues/{p['number']}/comments?per_page=100") if c["body"].startswith(MARK) and key in c["body"]]
        if old:
            continue
        api(f"issues/{p['number']}/comments", "POST",
            {"body": f"{MARK}\nmain と衝突しています。main を取り込んで衝突を解いてください。\n\n（{key}）"})
        print(f"#{p['number']}: 衝突を知らせた")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"undecided={','.join(map(str, undecided))}\n")


if __name__ == "__main__":
    main()
