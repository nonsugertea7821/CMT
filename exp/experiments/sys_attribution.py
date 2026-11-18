"""仮説 h_attribution_logged（一致する(運用者へ帰する文, 運用者の発言)）を確かめる: Claude が利用者の言葉として
書いた引用は、セッションの記録にある利用者の発言と一致するか。結果を見る前に、この説明と手順と判定を登録した。

材料:
  引用: main の履歴（版 dfbc41c まで）で足された行（git log -p の + の行）と commit のメッセージのうち、
    「利用者」の後 15 字以内に 指摘・問い・提案・気づき・直観・直感・見立て・案・見方・言葉・発言・選んだ のどれかがあり、
    その後に「…」が続くもの。その行の、その語より後の「…」をすべて引用とする。同じ文字列は1つに数える。
    鉤括弧のない帰属（「利用者の見立てから立てた仮説」の中身など）は、機械で照らせないので数えない（開示）。
  記録: ブランチ claude/session-log-nonsugertea7821（版 f8519cc）の利用者の発言（is: user_utterance）の val.text。
    記録の最初の発言より前の commit で足された引用は、照らせないので除く（n_before に数える）。
照らし方: 引用と発言の両方から、空白と記号（、。，．？?！!・…「」『』（）() と英字の大小）を除いて比べる。
  exact   正規化した引用が、ある発言の部分文字列
  near    exact でなく、引用の文字の2字組のうち、ある1つの発言に含まれる割合の最大が 0.6 以上（言い換え）
  absent  どちらでもない（記録にない）
数える量（要約。行の鍵と重ならない名前にする）:
  n_quotes, n_before, n_checked（= n_quotes − n_before）, n_exact, n_near, n_absent
  rate_exact = n_exact / n_checked, rate_absent = n_absent / n_checked
判定（ec が通るもとで）:
  n_absent = 0 かつ rate_exact ≥ 0.8 なら支持（v_support）。
  n_absent ≥ 1 なら反証（v_contradict）。一つでも記録にない引用があれば、帰属は発言と一致しない。
  そのほか（absent はないが exact が 0.8 に届かない）は mixed。
見込み（開示）: 登録の前に、引用の候補の一覧（14 個前後）を見た。発言の側はまだ照らしていない。
  きっかけになった h_open_declaration のずれ（中身の後半）は鉤括弧の引用ではないので、この測り方では数えない。
  記録は伏せる規則と保留で一部が置き換わっている（build.py）。そのせいで absent になる引用があれば、表に書いて開示する。

行（sys_attribution.json）:
  "summary 要約": 上の数
  "quote <i>": exact, near, absent（0 か 1）, before（0 か 1）, best（2字組の割合の最大）
  "texts": 引用ごとの原文、足した commit、最もよく合う発言の ULID と原文（記述）

使い方:
  python exp/experiments/sys_attribution.py
"""
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
MAIN = "dfbc41c"
LOG = "f8519cc"
LOGDIR = "claude_session_log/utterances"
MARK = re.compile(r"利用者.{0,15}?(指摘|問い|提案|気づき|直観|直感|見立て|案|見方|言葉|発言|選んだ)")
QUOTE = re.compile(r"「([^「」]*)」")
NOISE = re.compile(r"[\s、。，．？?！!・…「」『』（）()]")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def norm(s):
    return NOISE.sub("", s).lower()


def bigrams(s):
    return [s[i:i + 2] for i in range(len(s) - 1)] or [s]


def quotes_in(line):
    m = MARK.search(line)
    return [q for q in QUOTE.findall(line[m.end():])] if m else []


def harvest():
    out = {}
    log = git("log", "--reverse", "-p", "--format=COMMIT %h %cI%n%B%nENDMSG", MAIN)
    sha = when = None
    in_msg = False
    for l in log.split("\n"):
        if l.startswith("COMMIT "):
            _, sha, when = l.split(" ", 2)
            in_msg = True
            continue
        if l == "ENDMSG":
            in_msg = False
            continue
        if in_msg or (l.startswith("+") and not l.startswith("+++")):
            for q in quotes_in(l):
                if norm(q):
                    out.setdefault(q, (sha, when))
    return out


def utterances():
    names = git("ls-tree", "--name-only", f"{LOG}:{LOGDIR}").split()
    us = []
    for n in names:
        d = yaml.safe_load(git("show", f"{LOG}:{LOGDIR}/{n}"))
        src = git("show", f"{LOG}:{LOGDIR}/{n}").split("\n")[0]
        t = re.search(r"(\d{4}-\d\d-\d\dT[\d:.]+Z)", src)
        for k, v in (d.get("individuals") or {}).items():
            if v.get("is") == "user_utterance":
                us.append((k, str((v.get("val") or {}).get("text", "")), t.group(1) if t else ""))
    return us


def main():
    qs = harvest()
    us = utterances()
    start = min(t for _, _, t in us if t)
    nus = [(k, norm(t), t) for k, t, _ in us]
    rows, texts = {}, {}
    c = dict(n_quotes=len(qs), n_before=0, n_exact=0, n_near=0, n_absent=0)
    for i, (q, (sha, when)) in enumerate(sorted(qs.items(), key=lambda x: x[1][1])):
        nq = norm(q)
        before = int(when.replace("+00:00", "Z") < start) if when else 0
        bq = bigrams(nq)
        best, bk, bt = 0.0, None, None
        exact = 0
        for k, nu, raw in nus:
            if nq in nu:
                exact, best, bk, bt = 1, 1.0, k, raw
                break
            r = sum(1 for b in bq if b in nu) / len(bq)
            if r > best:
                best, bk, bt = r, k, raw
        near = int(not exact and best >= 0.6)
        absent = int(not exact and not near)
        if before:
            c["n_before"] += 1
        else:
            c["n_exact"] += exact
            c["n_near"] += near
            c["n_absent"] += absent
        rows[f"quote {i}"] = {"exact": exact, "near": near, "absent": absent, "before": before, "best": round(best, 3)}
        texts[i] = {"quote": q, "commit": sha, "when": when, "best_ulid": bk, "best_text": bt}
    n = c["n_quotes"] - c["n_before"]
    summ = {**c, "n_checked": n, "rate_exact": round(c["n_exact"] / n, 4) if n else 0,
            "rate_absent": round(c["n_absent"] / n, 4) if n else 0}
    rev = git("rev-parse", "--short", "HEAD").strip()
    (OUT / "sys_attribution.json").write_text(
        json.dumps({"rev": rev, "log_start": start, "rows": {"summary 要約": summ} | rows, "texts": texts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    for i, t in texts.items():
        r = rows[f"quote {i}"]
        print(i, r, t["quote"], "|", (t["best_text"] or "")[:80])


if __name__ == "__main__":
    main()
