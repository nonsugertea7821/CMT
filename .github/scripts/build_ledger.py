"""仮説台帳のページを、体系から作る。ロードマップ（決定とそのつながり）を軸に、仮説を決定ごとに並べる。

文は表示の変換器（display.sentence）で式から訳す。測定値は exp_check の展開から読む。名前を固定で持たない。
ロードマップの形は、決定どうしの事実（v_depend・v_raise・v_supersede）と、決定から仮説への v_ground から作る。
issue の番号は、GITHUB_TOKEN と GITHUB_REPOSITORY があれば issue の印（cscl-claim）から引く。
印を信じるのは、sync が立てた issue（github-actions が作ったもの）だけ。誰でも issue を立てられるので。なければ検索へのリンクにする。

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
import sys
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
WORD = {"<": "より小さい", ">": "より大きい", "≈": "とほぼ同じ", "=": "と同じ", "≥": "以上", "≤": "以下"}
BOT = {"github-actions[bot]", "github-actions"}
EDGE = {"v_depend": "depend", "v_raise": "raise", "v_supersede": "supersede"}


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


def issue_numbers():
    if not (os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY")):
        return {}
    out = {}
    for x in sync_issues.GitHub().issues():
        if (x.get("user") or {}).get("login") not in BOT:
            continue
        m = re.search(r"<!-- cscl-claim: (\S+) -->", x["body"] or "")
        if m and isinstance(x["number"], int):
            out[m.group(1)] = x["number"]
    return out


def build():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, S, M, C = exp_check.build()
    if type_checker.errors:
        raise SystemExit("体系の検査に失敗: " + "; ".join(type_checker.errors[:3]))
    I = sync_issues.individuals()
    short = type_checker.short
    ja = lambda x: display.ja(T, x, I)
    values, _ = exp_check.expand(M, T)

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

    def side_of(v):
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    def obs(oid):
        o = C["observations"].get(oid)
        if not o:
            return {"id": oid, "text": oid}
        sym = sync_issues.SYM.get(T.N[o["p"]]["display"], T.N[o["p"]]["display"])

        def term(x):
            if isinstance(x, str) and x in values:
                return {"key": x, "v": side_of(values[x][0])}
            return {"v": side_of(x)}
        return {"id": oid, "a": term(o["s"]), "rel": WORD.get(sym, sym), "b": term(o["o"])}

    status = lambda x: sync_issues.status_label(T, x["status"])
    nums = issue_numbers()
    grounded = {}
    decisions = {}
    for cid, x in C["decisions"].items():
        edges = []
        for k, v in x.items():
            m = re.match(r"\w+\.(v_\w+)$", k)
            if m and m.group(1) in EDGE and not k.startswith("basis."):
                edges += [{"kind": EDGE[m.group(1)], "to": short(t)} for t in as_list(v)]
        for h in as_list(x.get("basis")):
            grounded.setdefault(short(h), []).append(cid)
        decisions[cid] = {"side": C["side"][cid], "status": status(x), "text": sentences(x), "edges": edges,
                          "issue": nums.get(cid)}
    hyps = {}
    for cid, x in C["hypotheses"].items():
        hyps[cid] = {"side": C["side"][cid], "status": status(x), "text": sentences(x),
                     "subject": ja(as_list(x["s"])[0]),
                     "scope": [ja(v) for v in as_list(x.get("scope"))],
                     "evidence": [obs(short(o)) for o in as_list(x.get("evidence"))],
                     "against": [obs(short(o)) for o in as_list(x.get("against"))],
                     "decisions": grounded.get(cid, []), "issue": nums.get(cid)}
    return {"repo": os.environ.get("GITHUB_REPOSITORY", "nonsugertea7821/CMT"), "legend": sync_issues.LEGEND,
            "decisions": decisions, "hypotheses": hyps}


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
    for c in "<>&\u2028\u2029":
        data = data.replace(c, f"\\u{ord(c):04x}")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*LEDGER_DATA*/null", data)
    html = html.replace("/*LEDGER_CSP*/", csp(html))
    (out / "index.html").write_text(html, encoding="utf-8")
    print("書いた", out / "index.html")


if __name__ == "__main__":
    main()
