#!/usr/bin/env bash
# Stop フック: このセッションの発言を、ブランチ claude/session-log の claude_session_log/ に足して push する。
# 作業中のブランチには触れない（.git の中に別の worktree を置き、そこで作る）。作り方と伏せる・保留する規則は claude_session_log/build.py。
# 個人の情報を指すかもしれない発言は書かずに保留し、終了コード 2 で Claude を起こす（asyncRewake）。Claude が決める:
#   bash .claude/hooks/session_log.sh --decide <ULID> keep|withhold <理由>
#   bash .claude/hooks/session_log.sh --pending          このセッションでまだ記録していない発言（withhold は push の前に）
# それ以外の失敗では作業を止めない（0 で終わる。次の Stop で足りない分が足される）。
set -u
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" || exit 0
common=$(cd "$(git rev-parse --git-common-dir)" && pwd) || exit 0
wt="$common/session-log-worktree"
branch=claude/session-log
py=/home/user/venv/bin/python; [ -x "$py" ] || py=python3
mode=${1:-stop}
if [ "$mode" = stop ]; then in=$(cat); else
  t=$(ls -t "$HOME"/.claude/projects/*/"${CLAUDE_CODE_SESSION_ID:-none}".jsonl 2>/dev/null | head -1)
  in="{\"transcript_path\": \"$t\"}"
fi
exec 9>"$common/session-log.lock"
flock -w 300 9 || exit 0
git fetch -q origin "$branch" 2>/dev/null || exit 0
if [ ! -e "$wt/.git" ]; then
  git worktree prune
  git worktree add -q -B "$branch" "$wt" "origin/$branch" 2>/dev/null || exit 0
fi
git -C "$wt" reset -q --hard "origin/$branch" || exit 0
if [ "$mode" = --pending ]; then
  (cd "$wt" && "$py" claude_session_log/build.py --pending "${t:?transcript not found}"); exit 0
fi
sid=${CLAUDE_CODE_REMOTE_SESSION_ID:-}
trailer="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
[ -n "$sid" ] && trailer="$trailer
Claude-Session: https://claude.ai/code/session_${sid#cse_}"
held=0
for _ in 1 2 3; do
  git -C "$wt" fetch -q origin "$branch" && git -C "$wt" reset -q --hard "origin/$branch" || exit 0
  if [ "$mode" = --decide ]; then
    (cd "$wt" && "$py" claude_session_log/build.py --decide "$2" "$3" "${*:4}") || exit 1
    msg="claude_session_log: $2 を $3 と決める"
  else
    err=$(printf '%s' "$in" | (cd "$wt" && "$py" claude_session_log/build.py - 2>&1 >/dev/null)); rc=$?
    [ $rc -eq 0 ] || [ $rc -eq 2 ] || exit 0
    held=$rc
    msg="claude_session_log: セッションの発言を足す（フック）"
  fi
  git -C "$wt" add -A claude_session_log
  git -C "$wt" diff --cached --quiet && break
  git -C "$wt" commit -q -m "$msg

$trailer" || exit 0
  git -C "$wt" push -q origin "HEAD:$branch" 2>/dev/null && break
done
if [ "$held" = 2 ]; then printf '%s\n' "$err" >&2; exit 2; fi
exit 0
