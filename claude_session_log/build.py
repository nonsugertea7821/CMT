"""セッションの記録（Claude Code の transcript, JSONL）から、発言を例外なく取り出し、領域 claude_session_log の個体と事実に直す。

取り出す規則（個々に選ばない）:
  記録の行は uuid ごとに最初の1つだけを使う（再開のたびに同じ行が書き直されるため）。
  利用者の発言（user_utterance）:
    - type が user で、isMeta でも要約でもない行の文字列。<system-reminder> の部分は除く（システムが付けたもの）。
      除いて空になるもの、<task-notification> と <local-command-stdout> で始まるもの（システムの出力）は発言ではない。
      [Request interrupted ...]（中断）と <command-name>（利用者が打ったコマンド）は発言に入れる。画像は「[画像]」と書く。
    - ツールの結果のうち、質問への回答（AskUserQuestion の答え）と、ツールの使用を止めたこと（拒否）の文。
  Claude の発言（model_utterance）:
    - type が assistant の行の text の部分（1つの text が1つの発言）。
    - AskUserQuestion の呼び出し（質問と選択肢を文にしたもの）。
  要約（session_summary）: 文脈が尽きたときの要約（isCompactSummary の行）。Claude の発言として数える。
  思考（thinking）、ツールの呼び出しと出力は、発言ではないので入れない。

伏せる規則: メールアドレスは「[メールアドレスを伏せた]」、モデルの識別子（claude-<名>-<数>）とモデルの名（Opus 5.5 など）は
  「[モデル名を伏せた]」に置き換える（リポジトリに置くものにモデルの識別子を書かない取り決め）。それ以外は原文のまま。

個体: 発言ごとに1つ。名は ULID（時刻と、記録の行の uuid から決める）で、ファイル utterances/<ULID>.yaml に1つずつ置く。val の order（順番の軸）に記録の順、text（文字列の軸）に原文を持つ。時刻（UTC）は注釈に書く。
事実（規則で導く）:
  v_say               話し手 → 発言（exp.v_speak の終点を発言に限ったもの）
  exp.v_answer        発言 → 直前の、もう一方の話し手の発言（要約は除く）
  v_refer             発言 → 体系のノード。発言の中で `...` に囲まれた語か、_ か . を含む語のうち、
                      この領域から1つに解決できるノードの名（ノードの名と全く同じもの）

使い方:
  python claude_session_log/build.py <transcript.jsonl>
"""
import contextlib
import hashlib
from datetime import datetime
import io
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "claude_session_log/claude_session_log.yaml"
PARTS = ROOT / "claude_session_log/utterances"
DOMAIN = "claude_session_log"

MAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
MODEL = re.compile(r"claude-(opus|sonnet|haiku|fable)-[0-9][\w.\[\]-]*|\b(Opus|Sonnet|Haiku|Fable) [0-9](\.[0-9])?\b", re.I)
REMIND = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def clean(t):
    t = MAIL.sub("[メールアドレスを伏せた]", t)
    return MODEL.sub("[モデル名を伏せた]", t)


def ask_text(inp):
    out = []
    for q in inp.get("questions") or []:
        out.append(f"［質問］{q.get('question', '')}")
        for o in q.get("options") or []:
            out.append(f"  - {o.get('label', '')}: {o.get('description', '')}")
    return "\n".join(out)


def utterances(path):
    seen, out = set(), []
    for line in open(path, encoding="utf-8"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = e.get("uuid")
        if u is None or u in seen:
            continue
        seen.add(u)
        ts, t = e.get("timestamp"), e.get("type")
        n0 = len(out)   # 発言の名（ULID）の乱数部は、記録の行の uuid と行の中の順から決める（作り直しても同じ名）
        if t == "user" and e.get("isCompactSummary"):
            c = e["message"]["content"]
            c = c if isinstance(c, str) else "".join(x.get("text", "") for x in c if x.get("type") == "text")
            out.append((ts, "summary", c, f"{u}:{len(out) - n0}"))
            continue
        if t == "user" and not e.get("isMeta"):
            c = e["message"]["content"]
            for x in ([{"type": "text", "text": c}] if isinstance(c, str) else c):
                if x.get("type") == "text":
                    s = REMIND.sub("", x.get("text", "")).strip()
                    if s and not s.startswith(("<task-notification>", "<local-command-stdout>")):
                        out.append((ts, "user", s, f"{u}:{len(out) - n0}"))
                elif x.get("type") == "image":
                    out.append((ts, "user", "[画像]", f"{u}:{len(out) - n0}"))
                elif x.get("type") == "tool_result":
                    r = x.get("content")
                    r = r if isinstance(r, str) else "".join(y.get("text", "") for y in r or [] if isinstance(y, dict))
                    if r.startswith(("Your questions have been answered", "The user doesn't want to proceed")):
                        out.append((ts, "user", r.strip(), f"{u}:{len(out) - n0}"))
        elif t == "assistant":
            for x in e["message"].get("content") or []:
                if x.get("type") == "text" and x.get("text", "").strip():
                    out.append((ts, "model", x["text"].strip(), f"{u}:{len(out) - n0}"))
                elif x.get("type") == "tool_use" and x.get("name") == "AskUserQuestion":
                    out.append((ts, "model", ask_text(x.get("input") or {}), f"{u}:{len(out) - n0}"))
    return [(ts, k, clean(s), key) for ts, k, s, key in out]


B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid(ts, key):
    """ULID: 先頭 48 ビットが時刻（ミリ秒）、残り 80 ビットが key の SHA-256 の先頭。"""
    ms = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    n = (ms << 80) | int.from_bytes(hashlib.sha256(key.encode()).digest()[:10], "big")
    return "".join(B32[(n >> (5 * i)) & 31] for i in range(25, -1, -1))


class Block(str):
    pass


yaml.add_representer(Block, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))


def main():
    us = utterances(sys.argv[1])
    sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker")]
    with contextlib.redirect_stdout(io.StringIO()):
        import type_checker as tc
        T, O, _ = tc.build()
    names = {}
    for n in T.N:
        for w in (n, tc.short(n)):
            names.setdefault(w, set()).add(n)
    tok = re.compile(r"`([A-Za-z_][\w.]*)`|\b([A-Za-z_]\w*[_.][\w.]*\w)\b")

    def mentions(s):
        got = []
        for a, b in tok.findall(s):
            w = a or b
            ids = names.get(w, set())
            if len(ids) == 1 and next(iter(ids)) not in got:
                got.append(next(iter(ids)))
        return got

    kind = {"user": "user_utterance", "model": "model_utterance", "summary": "session_summary"}
    speaker = {"user": "session_user", "model": "session_model", "summary": "session_model"}
    ind = {"claude_session_log": {"is": "domain", "display": "Claude Code のセッションの記録"},
           "session_user": {"is": "subj.person", "display": "利用者"},
           "session_model": {"is": "std.model", "display": "Claude"}}
    facts = [{"is": "syntax.v_use", "from": DOMAIN, "to": d} for d in ("exp", "subj", "std", "runtime")]
    last, body, ids = {}, [], set()
    for i, (ts, k, s, key) in enumerate(us, 1):
        uid = ulid(ts, key)
        assert uid not in ids, uid
        ids.add(uid)
        fs = [{"is": "v_say", "from": speaker[k], "to": uid}]
        if k != "summary":
            other = last.get("model" if k == "user" else "user")
            if other:
                fs.append({"is": "exp.v_answer", "from": uid, "to": other})
            last[k] = uid
        fs += [{"is": "v_refer", "from": uid, "to": n} for n in mentions(s)]
        body.append((uid, ts, {"is": kind[k], "display": f"発言 {i}", "val": {"order": i, "text": Block(s + "\n") if "\n" in s else s}}, fs))
    dump = lambda x: yaml.dump(x, allow_unicode=True, sort_keys=False, width=10**9, default_flow_style=None)
    count = (f"発言 {len(us)}（利用者 {sum(k == 'user' for _, k, _, _ in us)}、Claude {sum(k == 'model' for _, k, _, _ in us)}、"
             f"要約 {sum(k == 'summary' for _, k, _, _ in us)}）")
    head = ("# 領域 claude_session_log（Claude Code のセッションの記録）。発言を例外なく、原文と事実で持つ。\n"
            "# 発言は1つずつ utterances/<ULID>.yaml に置く（parts）。作り方と規則は claude_session_log/build.py。手で書き換えない（作り直す）。\n"
            f"# {count}。\n")
    OUT.write_text(head + dump({"domain": DOMAIN, "parts": "claude_session_log/utterances/*.yaml", "nodes": NODES,
                                "individuals": ind, "facts": facts}), encoding="utf-8")
    PARTS.mkdir(exist_ok=True)
    for old in PARTS.glob("*.yaml"):
        old.unlink()
    for uid, ts, v, fs in body:
        (PARTS / f"{uid}.yaml").write_text(f"# 領域 claude_session_log の部分。記録の時刻 {ts}（UTC）\n" + dump({"individuals": {uid: v}, "facts": fs}), encoding="utf-8")
    print(head)


NODES = {
    "utterance": {"display": "発言", "extends": "syntax.passage_express_from_natural_language", "mod": {"of": ["exp.v_speak", "to"]}, "many": True},
    "user_utterance": {"display": "利用者の発言", "extends": "utterance", "mod": {"of": ["exp.v_speak", "to"], "with": "subj.person"}},
    "model_utterance": {"display": "Claude の発言", "extends": "utterance", "mod": {"of": ["exp.v_speak", "to"], "with": "std.model"}},
    "session_summary": {"display": "文脈が尽きたときの要約", "extends": "model_utterance", "mod": {"of": ["v_refer", "from"], "with": "utterance"}},
    "v_say": {"display": "発言する", "extends": "exp.v_speak", "to": "utterance"},
}

if __name__ == "__main__":
    main()
