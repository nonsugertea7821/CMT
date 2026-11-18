#!/usr/bin/env bash
# Stop フック: このセッションの発言を、ブランチ claude/session-log の claude_session_log/ に足して push する。
# 作業中のブランチには触れない（.git の中に別の worktree を置き、そこで作る）。作り方は claude_session_log/build.py（増分）。
# 失敗しても作業は止めない（いつも 0 で終わる。次の Stop で足りない分が足される）。
set -u
in=$(cat)
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
common=$(cd "$(git rev-parse --git-common-dir)" && pwd) || exit 0
wt="$common/session-log-worktree"
branch=claude/session-log
py=/home/user/venv/bin/python; [ -x "$py" ] || py=python3
exec 9>"$common/session-log.lock"
flock -w 300 9 || exit 0
git fetch -q origin "$branch" 2>/dev/null || exit 0
if [ ! -e "$wt/.git" ]; then
  git worktree prune
  git worktree add -q -B "$branch" "$wt" "origin/$branch" 2>/dev/null || exit 0
fi
sid=${CLAUDE_CODE_REMOTE_SESSION_ID:-}
msg="claude_session_log: セッションの発言を足す（フック）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
[ -n "$sid" ] && msg="$msg
Claude-Session: https://claude.ai/code/session_${sid#cse_}"
for _ in 1 2 3; do
  git -C "$wt" fetch -q origin "$branch" && git -C "$wt" reset -q --hard "origin/$branch" || exit 0
  printf '%s' "$in" | (cd "$wt" && "$py" claude_session_log/build.py - >/dev/null) || exit 0
  git -C "$wt" add claude_session_log
  git -C "$wt" diff --cached --quiet && exit 0
  git -C "$wt" commit -q -m "$msg" || exit 0
  git -C "$wt" push -q origin "HEAD:$branch" 2>/dev/null && exit 0
done
exit 0
