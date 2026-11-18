"""体系のファイル（定義）に、新しいコメントを足させない検査。すべてのセッションにかかる（.claude/settings.json）。

コメントが定義に効くなら式で書くべきで、効かないなら定義のファイルに置く理由がない（会話の取り決め）。
今あるコメントは移し終えるまで残してよい。HEAD にないコメント（足したもの・書き換えたもの）があれば、終了コード 2 で止める。
対象: cscl.yaml、cscl/library/、cscl/design/、exp/src/ の yaml。コメントは yaml の字句の外にある # から行末まで。

使い方（フックが呼ぶ）:
  no_new_comments.py edit     PostToolUse（Edit, Write）。標準入力の tool_input.file_path を見る
  no_new_comments.py commit   PreToolUse（Bash）。git commit のとき、索引（staged）にあるファイルを見る（-a, --all のときは作業ツリーの変更も）
  no_new_comments.py all      作業ツリーの対象ファイルをすべて見る（手で確かめる）
"""
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or ".")
SCOPE = re.compile(r"^(cscl\.yaml|cscl/library/.*\.ya?ml|cscl/design/.*\.ya?ml|exp/src/.*\.ya?ml)$")


def comments(src):
    L = src.split("\n")
    spans = collections.defaultdict(list)
    try:
        toks = list(yaml.scan(src, Loader=yaml.SafeLoader))
    except yaml.YAMLError:
        toks = []
    for t in toks:
        s, e = t.start_mark, t.end_mark
        for ln in range(s.line, e.line + 1):
            a = s.column if ln == s.line else 0
            b = e.column if ln == e.line else 10 ** 9
            if (a, b) != (0, 0):
                spans[ln].append((a, b))
    out = collections.Counter()
    for i, l in enumerate(L):
        for j, ch in enumerate(l):
            if ch == "#" and not any(a <= j < b for a, b in spans[i]):
                out[l[j:].strip()] += 1
                break
    return out


def git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def new_comments(rel, src):
    old = git("show", f"HEAD:{rel}") or ""
    return list((comments(src) - comments(old)).elements())


def report(found):
    if not found:
        return 0
    lines = ["体系のファイルに新しいコメントがある（コメントは足さない取り決め。意味は式に、経緯と解釈は commit のメッセージと会話に書く）:"]
    for rel, cs in found:
        lines += [f"  {rel}: {c}" for c in cs[:10]] + ([f"  {rel}: ほか {len(cs) - 10} 個"] if len(cs) > 10 else [])
    print("\n".join(lines), file=sys.stderr)
    return 2


def main(mode):
    found = []
    if mode == "edit":
        p = (json.load(sys.stdin).get("tool_input") or {}).get("file_path") or ""
        try:
            rel = str(Path(p).resolve().relative_to(ROOT.resolve()))
        except ValueError:
            return 0
        if SCOPE.match(rel) and Path(p).exists():
            cs = new_comments(rel, Path(p).read_text(encoding="utf-8"))
            if cs:
                found.append((rel, cs))
    elif mode == "commit":
        cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command") or ""
        if not re.search(r"\bgit\b[^|;&]*\bcommit\b", cmd):
            return 0
        names = (git("diff", "--cached", "--name-only") or "").split()
        tree = set()
        if re.search(r"\bcommit\b[^|;&]*\s(-[A-Za-z]*a[A-Za-z]*|--all)\b", cmd):
            tree = set((git("diff", "--name-only") or "").split())
        for rel in sorted(set(names) | tree):
            if SCOPE.match(rel):
                src = git("show", f":{rel}") if rel not in tree else None
                if src is None and (ROOT / rel).exists():
                    src = (ROOT / rel).read_text(encoding="utf-8")
                cs = new_comments(rel, src or "")
                if cs:
                    found.append((rel, cs))
    else:
        for p in sorted(ROOT.glob("**/*.y*ml")):
            rel = str(p.relative_to(ROOT))
            if SCOPE.match(rel):
                cs = new_comments(rel, p.read_text(encoding="utf-8"))
                if cs:
                    found.append((rel, cs))
    return report(found)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "all"))
