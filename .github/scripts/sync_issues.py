"""仮説・決定を GitHub の issue に写す。定義の正本は体系（exp/src/exp.yaml と cscl/design/*.yaml）。

issue 1件 = 主張（仮説か決定）1つ。本文は3節:
  説明  Claude が書く自然言語の説明。このスクリプトは触らない
  定義  体系から生成する。このスクリプトが毎回書き換える。手で編集しない
  経緯  Claude が書く、議論の経緯。このスクリプトは触らない
定義が変わったとき（ハッシュが違うとき）、説明が書かれていれば、ラベル「説明が古い」を付ける。

使い方:
  python .github/scripts/sync_issues.py --out DIR        下書きを DIR に書く（GitHub に触らない）
  python .github/scripts/sync_issues.py --apply          GitHub の issue を作る・更新する（GITHUB_TOKEN, GITHUB_REPOSITORY）
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "cscl/bootstrap/display")]
import type_checker  # noqa: E402
import display  # noqa: E402

SIDE = {"exp": "exp", "lang": "cscl"}   # 領域 → 側のラベル
STATUS = {"hyp_supported": "支持", "hyp_refuted": "反証", "hyp_mixed": "混合", "hyp_untested": "未検証",
          "dec_adopted": "採用", "dec_tentative": "暫定", "dec_withdrawn": "取り下げ"}
CLOSED = {"支持", "反証", "採用", "取り下げ"}
COLORS = {"exp": "1d76db", "cscl": "5319e7", "仮説": "c5def5", "決定": "fef2c0", "支持": "0e8a16", "反証": "b60205",
          "混合": "fbca04", "未検証": "ededed", "採用": "0e8a16", "暫定": "fbca04", "取り下げ": "b60205",
          "説明が古い": "d93f0b", "主張": "000000"}
MARK = "<!-- cscl-claim: {} -->"
EMPTY = "（未記入）"


def individuals():
    """個体の表示語。領域のファイルから読む（体系の検査器は種類だけを持つ）。"""
    out = {}
    for name in type_checker.domain_files().values():
        y = type_checker.yload((ROOT / name).read_text(encoding="utf-8")) or {}
        out |= {k: v for k, v in (y.get("individuals") or {}).items() if isinstance(v, dict)}
    return out


def status_label(T, kind):
    for k, v in STATUS.items():
        if any(type_checker.short(a) == k for a in [kind, *T.ancestors(kind)]):
            return v
    return None


def claims():
    T, O, S, M, C = type_checker.build()
    if type_checker.errors:
        raise SystemExit("体系の検査に失敗: " + "; ".join(type_checker.errors[:3]))
    I = individuals()
    ja = lambda x: display.ja(T, x, I)
    out = []
    for sect, kind in (("hypotheses", "仮説"), ("decisions", "決定")):
        for cid, x in C[sect].items():
            side = SIDE[C["side"][cid]]
            ss, oo = ([v] if isinstance(v, str) else v for v in (x["s"], x["o"]))
            if x["p"] == "is_a":
                content = "、".join(f"{ja(a)} は {ja(b)} の一種である" for a in ss for b in oo)
            else:
                content = "、".join(display.fact(T, x["p"], a, b, I) for a in ss for b in oo)
            st = status_label(T, x["status"])
            lines = [f"- 種類: {kind}（{ja(x['status'])}）", f"- 中身: {content}",
                     f"- 識別子: `{cid}`（`{C['side'][cid]}` 領域）"]
            for k, name in (("scope", "適用範囲"), ("evidence", "支持する観察"), ("against", "反する観察"),
                            ("limitation", "留保"), ("basis", "根拠となる仮説"), ("supersedes", "置き換えたもの")):
                vs = x.get(k) or []
                vs = vs if isinstance(vs, list) else [vs]
                if vs:
                    lines.append(f"- {name}: " + "、".join(f"`{type_checker.short(v)}`" if ja(v) == v else f"{ja(v)}（`{type_checker.short(v)}`）" for v in vs))
            src = [l.strip() for f in ROOT.glob("**/*.yaml") if f.parts[len(ROOT.parts)] in ("exp", "cscl")
                   for l in f.read_text(encoding="utf-8").splitlines()
                   if re.search(rf"(from|to): {re.escape(cid)}[,}}]", l) or re.match(rf"\s+{re.escape(cid)}:", l)]
            body_def = "\n".join(lines) + "\n\n<details><summary>体系での記述</summary>\n\n```yaml\n" + "\n".join(src) + "\n```\n</details>"
            h = hashlib.sha256(body_def.encode()).hexdigest()[:12]
            out.append({"id": cid, "side": side, "kind": kind, "status": st,
                        "title": f"[{side}] {cid}: {content}"[:250], "def": body_def, "hash": h})
    return out


def section(name, text):
    return f"<!-- {name}:begin -->\n{text}\n<!-- {name}:end -->"


def new_body(c):
    return "\n\n".join([MARK.format(c["id"]), "## 説明", section("explain", EMPTY),
                        f"## 定義\n_体系から生成。手で編集しない（`.github/scripts/sync_issues.py`）。_ <!-- hash: {c['hash']} -->",
                        section("def", c["def"]), "## 経緯", section("history", EMPTY)])


def update_body(body, c):
    old = re.search(r"<!-- hash: (\w+) -->", body)
    body = re.sub(r"<!-- hash: \w+ -->", f"<!-- hash: {c['hash']} -->", body)
    body = re.sub(r"<!-- def:begin -->.*?<!-- def:end -->", lambda m: section("def", c["def"]), body, flags=re.S)
    explained = EMPTY not in re.search(r"<!-- explain:begin -->(.*?)<!-- explain:end -->", body, re.S).group(1)
    return body, bool(old and old.group(1) != c["hash"] and explained)


def labels_of(c):
    return ["主張", c["side"], c["kind"]] + ([c["status"]] if c["status"] else [])


class GitHub:
    def __init__(self):
        self.repo, self.token = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]

    def call(self, method, path, data=None):
        req = urllib.request.Request(f"https://api.github.com/repos/{self.repo}{path}", method=method,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or "null")

    def issues(self):
        out, page = [], 1
        while True:
            xs = self.call("GET", f"/issues?labels=主張&state=all&per_page=100&page={page}".replace("主張", "%E4%B8%BB%E5%BC%B5"))
            out += [x for x in xs if "pull_request" not in x]
            if len(xs) < 100:
                return out
            page += 1


def apply(cs):
    gh = GitHub()
    have = {x["name"] for x in gh.call("GET", "/labels?per_page=100")}
    for name, color in COLORS.items():
        if name not in have:
            gh.call("POST", "/labels", {"name": name, "color": color})
    known = {}
    for x in gh.issues():
        m = re.search(r"<!-- cscl-claim: (\S+) -->", x["body"] or "")
        if m:
            known[m.group(1)] = x
    for c in cs:
        state = "closed" if c["status"] in CLOSED else "open"
        x = known.get(c["id"])
        if x is None:
            x = gh.call("POST", "/issues", {"title": c["title"], "body": new_body(c), "labels": labels_of(c)})
            print("作成", x["number"], c["id"])
            if state == "closed":
                gh.call("PATCH", f"/issues/{x['number']}", {"state": "closed", "state_reason": "completed"})
            continue
        body, stale = update_body(x["body"], c)
        keep = [l["name"] for l in x["labels"] if l["name"] not in COLORS or l["name"] == "説明が古い"]
        labels = labels_of(c) + keep + (["説明が古い"] if stale and "説明が古い" not in keep else [])
        patch = {"title": c["title"], "body": body, "labels": labels, "state": state}
        if state == "closed":
            patch["state_reason"] = "completed"
        if (body, c["title"], x["state"], sorted(l["name"] for l in x["labels"])) != (x["body"], x["title"], state, sorted(labels)):
            gh.call("PATCH", f"/issues/{x['number']}", patch)
            print("更新", x["number"], c["id"], "（説明が古い）" if stale else "")
    for cid in known.keys() - {c["id"] for c in cs}:
        print("体系にない主張の issue:", known[cid]["number"], cid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    cs = claims()
    if args.out:
        d = Path(args.out)
        d.mkdir(parents=True, exist_ok=True)
        for c in cs:
            (d / f"{c['id']}.md").write_text(f"# {c['title']}\nラベル: {', '.join(labels_of(c))}\n\n" + new_body(c), encoding="utf-8")
    if args.apply:
        apply(cs)
    print(f"主張 {len(cs)}（" + "、".join(f"{s} {sum(c['side'] == s for c in cs)}" for s in ("exp", "cscl")) + "）")


if __name__ == "__main__":
    main()
