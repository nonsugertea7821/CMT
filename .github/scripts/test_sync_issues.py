"""sync_issues の apply を、GitHub の代わりの記憶の中の issue で確かめる。
定義を変えたとき、同じ issue が更新され、説明・経緯は残り、stale-explanation が付くこと。ラベルの日本語名は英語に変え、GitHub の既定のラベルは消すこと。"""
import copy
import urllib.parse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sync_issues as s  # noqa: E402


class Fake:
    def __init__(self):
        self.xs, self.labels = {}, set()

    def call(self, method, path, data=None):
        if path.startswith("/labels"):
            name = urllib.parse.unquote(path[len("/labels/"):]) if path.startswith("/labels/") else None
            if method == "POST":
                self.labels.add(data["name"])
            if method == "PATCH":
                self.labels.discard(name)
                self.labels.add(data["new_name"])
                for x in self.xs.values():
                    x["labels"] = [{"name": data["new_name"] if l["name"] == name else l["name"]} for l in x["labels"]]
            if method == "DELETE":
                self.labels.discard(name)
            return [{"name": n} for n in self.labels]
        if method == "POST":
            n = len(self.xs) + 1
            self.xs[n] = {"number": n, "title": data["title"], "body": data["body"], "state": "open",
                          "labels": [{"name": l} for l in data["labels"]]}
            return self.xs[n]
        n = int(path.rsplit("/", 1)[1])
        x = self.xs[n]
        for k in ("title", "body", "state"):
            if k in data:
                x[k] = data[k]
        if "labels" in data:
            x["labels"] = [{"name": l} for l in data["labels"]]
        return x

    def issues(self):
        return list(self.xs.values())


def main():
    fake = Fake()
    fake.labels = {"bug", "good first issue", "主張", "説明が古い"}
    s.GitHub = lambda: fake
    cs = s.claims()
    s.apply(cs)
    n = len(fake.xs)
    assert n == len(cs), (n, len(cs))
    c0 = cs[0]
    x = next(x for x in fake.xs.values() if f"cscl-claim: {c0['id']} " in x["body"])
    x["body"] = x["body"].replace("<!-- explain:begin -->\n（未記入）", "<!-- explain:begin -->\n書いた説明", 1)
    s.apply(cs)   # 変えていなければ、何も変わらない
    assert len(fake.xs) == n and s.STALE not in [l["name"] for l in x["labels"]]
    cs2 = copy.deepcopy(cs)
    cs2[0]["def"] += "\n- 変えた"
    cs2[0]["hash"] = "changed"
    s.apply(cs2)
    assert len(fake.xs) == n, "定義を変えたら、新しい issue ができた"
    assert "- 変えた" in x["body"] and "書いた説明" in x["body"], "同じ issue の定義が更新され、説明が残る"
    assert s.STALE in [l["name"] for l in x["labels"]]
    # 観察の値: 値が変わっても説明は古くならず、節は1つだけ。節のない古い本文には差し込む
    x["labels"] = [l for l in x["labels"] if l["name"] != s.STALE]
    cs3 = copy.deepcopy(cs2)
    cs3[0]["obs"] = "- 値を変えた"
    s.apply(cs3)
    assert "- 値を変えた" in x["body"] and x["body"].count("<!-- obs:begin -->") == 1
    assert s.STALE not in [l["name"] for l in x["labels"]], "値だけの変化で説明が古いとされた"
    x["body"] = re.sub(r"## 観察の値\n\n<!-- obs:begin -->.*?<!-- obs:end -->\n\n", "", x["body"], flags=re.S)
    s.apply(cs3)
    assert x["body"].count("<!-- obs:begin -->") == 1 and x["body"].index("## 観察の値") < x["body"].index("## 定義")
    assert not fake.labels & (set(s.DEFAULTS) | set(s.RENAME)), fake.labels
    print(f"同期の確認に成功: 主張 {n}、定義を変えた主張は同じ issue（#{x['number']}）が更新され、説明は残り「説明が古い」が付いた")


if __name__ == "__main__":
    main()
