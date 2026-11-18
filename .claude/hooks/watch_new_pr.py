"""PR を立てた直後に、その PR を見張り、利用者を assignee にするよう Claude に伝える（PostToolUse, mcp__github__create_pull_request）。

フックは MCP の道具を呼べないので、subscribe_pr_activity を呼ぶ指示を additionalContext で返す。
Claude がそれを読んで呼ぶ（フックの連鎖）。PR の番号は道具の結果の url から取る。
"""
import json
import re
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    resp = data.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    m = re.search(r"github\.com/([^/\s\"]+)/([^/\s\"]+)/pull/(\d+)", text or "")
    if not m:
        return
    owner, repo, n = m.group(1), m.group(2), int(m.group(3))
    msg = (f"PR #{n} を立てた。このリポジトリでは、立てた PR は見張る。"
           f"今すぐ subscribe_pr_activity(owner={owner}, repo={repo}, pullNumber={n}) を呼ぶこと。"
           f"あわせて issue_write(method=update, issue_number={n}, assignees=[{owner}]) で利用者を assignee にすること"
           f"（仮説の PR に限らず、立てた PR はすべて）。")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
