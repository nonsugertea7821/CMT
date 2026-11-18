# CMT

## セッションの記録（規定では無効）

`.claude/settings.json` は、Claude Code の Stop フック `.claude/hooks/session_log.sh` を登録している。
このフックは、セッションの発言を取り出してブランチ `claude/session-log-<ユーザー名>` に足し、push する。

**規定では何もしない。** clone した人のセッションは、何も設定しなければ記録されない。
記録するのは、次の両方が成り立つときだけ:

1. 持ち主が自分で有効にしている:
   - 環境変数 `CMT_SESSION_LOG_OWNER=<GitHub のユーザー名>`、または
   - `git config cmt.sessionLogOwner <GitHub のユーザー名>`（`.git/config` に書く。commit されず、clone にも渡らない）
2. そのユーザー名が、`origin` の持ち主と同じ。

記録の前に、メールアドレス・電話番号・鍵らしい文字列などは伏せる。個人の情報を指すかもしれない利用者の発言は、書かずに保留する。
規則は記録のブランチの `claude_session_log/build.py` にある。

フックを使いたくない人は、`.claude/settings.local.json` で無効にするか、フックの設定を消してよい。
