"""main と衝突している PR に、コメントで知らせる。

PR を見張るセッションには、コメントは届くが、衝突は届かない。そこで main への push のたびに開いている PR を調べ、
衝突していれば印 MARK の付いたコメントを書く。同じ head と同じ main について書いたものがあれば、書き足さない。

使い方（ワークフローが呼ぶ）: python .github/scripts/conflict_notice.py MAIN_SHA
  環境変数 GITHUB_TOKEN, GITHUB_REPOSITORY
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
    for p in api("pulls?state=open&base=main&per_page=100"):
        pr = mergeable(p["number"])
        if pr["mergeable"] is not False:
            continue
        head = pr["head"]["sha"]
        key = f"head {head[:7]} / main {base[:7]}"
        old = [c for c in api(f"issues/{p['number']}/comments?per_page=100") if c["body"].startswith(MARK) and key in c["body"]]
        if old:
            continue
        api(f"issues/{p['number']}/comments", "POST",
            {"body": f"{MARK}\nmain と衝突しています。main を取り込んで衝突を解いてください。\n\n（{key}）"})
        print(f"#{p['number']}: 衝突を知らせた")


if __name__ == "__main__":
    main()
