"""仮説台帳のページを、体系から作る。ロードマップ（決定とそのつながり）を左に木で置き、仮説を決定ごとに並べる。

文は体系の式から訳す。名前を固定で持たない。
仮説は登録の順に並べ、いつ支持・反証されたかを main の履歴（git log）から出す。履歴の全体が要る（checkout は fetch-depth: 0）。
ロードマップの形は、決定どうしの事実（v_depend・v_raise・v_supersede）と、決定から仮説への v_ground から作る。

仮説ごとの説明は、その仮説を名指ししたマージ済みの PR の本文から取る（確かめたときの手順・結果・読みが書いてある）。
取るのは、持ち主・メンバー・協力者が立てて、マージされた PR だけ。本文の Markdown は、ここで HTML に変える。
すべての文字をまず逃がし、そのあとで決まった形（見出し・箇条・表・コード・強調・https のリンク・#番号）だけを組む。
生の HTML は文字として出す。

issue の番号は、issue の印（cscl-claim）から引く。GITHUB_TOKEN があれば使う（公開のリポジトリなので、なくても読める）。
印を信じるのは、sync が立てた issue（github-actions が作ったもの）だけ。誰でも issue を立てられるので。

出力はリポジトリに入れない（入れると、仮説を登録するたびに作り直しが要り、登録の PR が自動マージの範囲から外れる）。
ワークフロー ledger が main への push で作り、GitHub Pages に出す。

使い方:
  python .github/scripts/build_ledger.py [出力先のディレクトリ（既定 _site）]
"""
import ast
import base64
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / "cscl/bootstrap/display")]
with contextlib.redirect_stdout(io.StringIO()):
    import sync_issues  # noqa: E402
    import display  # noqa: E402
    from sync_issues import exp_check, type_checker  # noqa: E402

TEMPLATE = Path(__file__).with_name("ledger_template.html")
CASE_TABLE = ROOT / "exp/experiments/sys_case_frame_formula.py"
PARTICLES = ("について", "から", "より", "に", "で", "と", "を", "へ", "の")
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
BOT = {"github-actions[bot]", "github-actions"}
EDGE = {"v_depend": "depend", "v_raise": "raise", "v_supersede": "supersede"}
REPO = os.environ.get("GITHUB_REPOSITORY", "nonsugertea7821/CMT")


def as_list(v):
    return [] if v is None else v if isinstance(v, list) else [v]


def case_table():
    """動詞ごとの助詞の表（sys_case_frame_formula.GOLD）。人が表示語から付けた判断で、式から導いたものではない。
    格の枠を式から導く仮説（h_case_frame_*）はまだ通っていないので、台帳の文はこの表で補う。"""
    tree = ast.parse(CASE_TABLE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "GOLD" for t in node.targets):
            return ast.literal_eval(node.value)
    return {}


def api(path):
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or "null")


def pages(path, keep):
    out, page = [], 1
    while True:
        xs = api(f"{path}&per_page=100&page={page}")
        out += [x for x in xs if keep(x)]
        if len(xs) < 100:
            return out
        page += 1


def issue_numbers():
    out = {}
    for x in pages("/issues?state=all", lambda x: "pull_request" not in x and (x.get("user") or {}).get("login") in BOT):
        m = re.search(r"<!-- cscl-claim: (\S+) -->", x.get("body") or "")
        if m and isinstance(x["number"], int):
            out[m.group(1)] = x["number"]
    return out


def history():
    """仮説の登録と状態の移りを、main の履歴（体系の yaml）から読む。
    仮説の行 `h_名前: {is: hyp_状態}` が初めて足された commit を登録とし、状態が変わった commit をその日の出来事とする。
    返すのは {名前: {"seq": 登録の順番, "events": [{"at": 日時, "commit": 短い hash, "status": 状態}]}}。"""
    try:
        log = subprocess.run(["git", "log", "--reverse", "--format=@@%h %cI", "-U0", "-p", "--",
                              "cscl.yaml", "cscl", "exp/src"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as e:
        print("履歴を読めなかった:", e, file=sys.stderr)
        return {}
    out, commit, at = {}, None, None
    line = re.compile(r"^\+\s+(h_\w+): \{is: (?:exp\.)?hyp_(\w+)\}")
    for l in log.splitlines():
        if l.startswith("@@") and not l.startswith("@@ "):
            commit, at = l[2:].split(" ", 1)
            continue
        m = line.match(l)
        if not m:
            continue
        name, st = m.groups()
        x = out.setdefault(name, {"seq": len(out), "events": []})
        if not x["events"] or x["events"][-1]["status"] != st:
            x["events"].append({"at": at, "commit": commit, "status": st})
    return out


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def inline(t):
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    t = re.sub(r"`([^`]+)`", keep, esc(t))
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https://[^\s()]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', t)
    t = re.sub(r"(?<![\w;/])#(\d+)\b", rf'<a href="https://github.com/{REPO}/issues/\1" target="_blank" rel="noopener noreferrer">#\1</a>', t)
    return re.sub("\x00(\\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)


def markdown(text):
    """決まった形だけを組む Markdown の変換。入力の文字はすべて逃がしてから組む。"""
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    text = re.sub(r"</?details>|</?summary>", "", text)
    lines = [l for l in text.replace("\r", "").split("\n")
             if not re.search(r"claude\.ai/code/session_|Generated (with|by) \[Claude Code\]", l)]
    out, para, stack = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para.clear()

    def close(level=0):
        while len(stack) > level:
            out.append(f"</li></{stack.pop()}>")
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith("```"):
            flush(), close()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            out.append("<pre><code>" + esc("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
            continue
        if l.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            flush(), close()
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            rows = ["<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells(l)) + "</tr>"]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells(lines[i])) + "</tr>")
                i += 1
            out.append('<div class="tbl"><table>' + "".join(rows) + "</table></div>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", l)
        h = re.match(r"^#{1,6}\s+(.*)$", l)
        if m and not re.match(r"^\s*([-*])(\s*\1){2,}\s*$", l):
            flush()
            level = len(m.group(1).expandtabs(2)) // 2 + 1
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            if len(stack) >= level:
                close(level)
                out.append("</li><li>")
            while len(stack) < level:
                stack.append(tag)
                out.append(f"<{tag}><li>")
            out.append(inline(m.group(3)))
        elif h:
            flush(), close()
            out.append(f"<h5>{inline(h.group(1))}</h5>")
        elif not l.strip() or re.match(r"^\s*(-{3,}|\*{3,})\s*$", l):
            flush(), close()
        elif stack:
            out.append(" " + inline(l.strip()))
        else:
            para.append(l.strip())
        i += 1
    flush(), close()
    return "".join(out)


def pulls_by_claim(ids, nums):
    """仮説・決定の識別子（と、その issue の番号）を名指ししたマージ済みの PR。
    確かめのブランチ claude/<名前> のものか、題に名前があるものを先に、あとは新しい順に置く。"""
    by_num = {n: cid for cid, n in nums.items()}
    word = re.compile(r"(?<![\w.])([hd]_\w+)")
    try:
        pulls = pages("/pulls?state=closed", lambda x: x.get("merged_at") and x.get("author_association") in TRUSTED)
    except Exception as e:
        print("PR を読めなかった:", e, file=sys.stderr)
        return {}, {}
    found, prs = {}, {}
    for x in sorted(pulls, key=lambda x: x["merged_at"], reverse=True):
        title = x.get("title") or ""
        text = title + "\n" + (x.get("body") or "")
        hit = {m for m in word.findall(text) if m in ids}
        hit |= {by_num[int(n)] for n in re.findall(r"#(\d+)", text) if int(n) in by_num}
        if not hit:
            continue
        branch = (x.get("head") or {}).get("ref") or ""
        prs[x["number"]] = {"title": title, "date": x["merged_at"][:10], "html": markdown(x.get("body"))}
        for cid in hit:
            n = nums.get(cid)
            own = (branch == f"claude/{cid}" or re.search(rf"(?<![\w.]){re.escape(cid)}(?!\w)", title)
                   or (n and re.search(rf"#{n}(?!\d)", title)))
            found.setdefault(cid, []).append((0 if own else 1, x["number"]))
    return {cid: [{"n": n, "own": r == 0} for r, n in sorted(v, key=lambda t: t[0])] for cid, v in found.items()}, prs


def build():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, S, M, C = exp_check.build()
    if type_checker.errors:
        raise SystemExit("体系の検査に失敗: " + "; ".join(type_checker.errors[:3]))
    I = sync_issues.individuals()
    short = type_checker.short
    ja = lambda x: display.ja(T, x, I)

    gold = case_table()
    by_display = {}
    for v, mark in gold.items():
        if v in T.N:
            by_display.setdefault(ja(v), mark)

    def mark_of(verb):
        vd = ja(verb)
        if vd.startswith(PARTICLES):
            return ""
        return gold.get(verb) or by_display.get(vd) or display.case_mark(vd)

    def sentences(x):
        if x["p"] == "is_a":
            return [f"{ja(a)}は{ja(b)}の一種である" for a in as_list(x["s"]) for b in as_list(x["o"])]
        return [f"{ja(a)}が{ja(b)}{mark_of(x['p'])}{ja(x['p'])}" for a in as_list(x["s"]) for b in as_list(x["o"])]

    status = lambda x: sync_issues.status_label(T, x["status"])
    try:
        nums = issue_numbers()
    except Exception as e:
        print("issue を読めなかった:", e, file=sys.stderr)
        nums = {}
    linked, prs = pulls_by_claim(set(C["hypotheses"]) | set(C["decisions"]), nums)
    past = history()
    grounded, decisions, hyps = {}, {}, {}
    for cid, x in C["decisions"].items():
        edges = []
        for k, v in x.items():
            m = re.match(r"\w+\.(v_\w+)$", k)
            if m and m.group(1) in EDGE and not k.startswith("basis."):
                edges += [{"kind": EDGE[m.group(1)], "to": short(t)} for t in as_list(v)]
        for h in as_list(x.get("basis")):
            grounded.setdefault(short(h), []).append(cid)
        decisions[cid] = {"side": C["side"][cid], "status": status(x), "text": sentences(x), "edges": edges,
                          "issue": nums.get(cid), "prs": linked.get(cid, [])}
    for cid, x in C["hypotheses"].items():
        hyps[cid] = {"side": C["side"][cid], "status": status(x), "text": sentences(x),
                     "subject": ja(as_list(x["s"])[0]),
                     "scope": [ja(v) for v in as_list(x.get("scope"))],
                     "decisions": grounded.get(cid, []), "issue": nums.get(cid), "prs": linked.get(cid, []),
                     "seq": (past.get(cid) or {}).get("seq", 10 ** 6), "events": (past.get(cid) or {}).get("events", [])}
    used = {p["n"] for x in [*decisions.values(), *hyps.values()] for p in x["prs"]}
    return {"repo": REPO, "decisions": decisions, "hypotheses": hyps,
            "prs": {n: v for n, v in prs.items() if n in used}}


def csp(html):
    """ページの中の script と style だけを、中身のハッシュで許す。外へは何も読みに行かない。"""
    h = lambda t: "'sha256-" + base64.b64encode(hashlib.sha256(t.encode("utf-8")).digest()).decode() + "'"
    scripts = " ".join(h(t) for t in re.findall(r"<script>(.*?)</script>", html, re.S))
    styles = " ".join(h(t) for t in re.findall(r"<style>(.*?)</style>", html, re.S))
    return (f"default-src 'none'; script-src {scripts}; style-src {styles}; img-src 'none'; connect-src 'none'; "
            "font-src 'none'; base-uri 'none'; form-action 'none'")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    out.mkdir(parents=True, exist_ok=True)
    data = json.dumps(build(), ensure_ascii=False)
    for c in "<>&  ":
        data = data.replace(c, f"\\u{ord(c):04x}")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*LEDGER_DATA*/null", data)
    html = html.replace("/*LEDGER_CSP*/", csp(html))
    (out / "index.html").write_text(html, encoding="utf-8")
    print("書いた", out / "index.html")


if __name__ == "__main__":
    main()
