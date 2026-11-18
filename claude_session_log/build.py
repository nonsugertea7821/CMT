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

伏せる規則（いつも置き換える）: メールアドレス、電話番号、カード番号らしい数字の並び、秘密の鍵らしい文字列（API キー、
  GitHub などのトークン、Bearer の後ろ、秘密鍵の塊）は「[…を伏せた]」に置き換える。モデルの識別子（claude-<名>-<数>）と
  モデルの名（Opus 5.5 など）は「[モデル名を伏せた]」（リポジトリに置くものにモデルの識別子を書かない取り決め）。それ以外は原文のまま。
保留の規則（Claude が決める）: 個人の情報を指す語（住所、本名、生年月日、パスワード、口座、郵便番号らしい数字 など）を含む発言は、
  書かずに保留し、終了コード 2 で知らせる（フックが Claude を起こす）。Claude が decisions.yaml に keep（そのまま記録）か
  withhold（記録しない）を書くまで保留のまま。decisions.yaml は ULID と決定と理由だけを持ち、発言の中身は持たない。
  Claude は保留でない発言も withhold にできる（まだ push されていなければ、記録されない）。
  python claude_session_log/build.py --decide <ULID> keep|withhold <理由>
  python claude_session_log/build.py --pending <transcript.jsonl>   まだ記録していない発言の ULID と書き出し

個体: 発言ごとに1つ。名は ULID（時刻と、記録の行の uuid から決める）で、ファイル utterances/<ULID>.yaml に1つずつ置く。val の order（順番の軸）に記録の順、text（文字列の軸）に原文を持つ。時刻（UTC）は注釈に書く。
事実（規則で導く）:
  v_say               話し手 → 発言（exp.v_speak の終点を発言に限ったもの）
  exp.v_answer        発言 → 直前の、もう一方の話し手の発言（要約は除く）
  v_refer             発言 → 体系のノード。発言の中で `...` に囲まれた語か、_ か . を含む語のうち、
                      この領域から1つに解決できるノードの名（ノードの名と全く同じもの）

足し方（増分）: 既にあるファイル（同じ ULID）は書き直さず、ないものだけを足す。消さない（別のセッションの発言も同じ所に置く）。
  新しい発言の order は、今ある発言の order の最大の続き。claude_session_log.yaml は数を数え直して書き直す。

使い方:
  python claude_session_log/build.py <transcript.jsonl>
  python claude_session_log/build.py -        フックの入力（JSON, transcript_path を持つ）を標準入力から読む
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
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"
                    r"|\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|xox[abprs]-[\w-]{10,}|AKIA[0-9A-Z]{16}|AIza[\w-]{30,})"
                    r"|(?<=Bearer )[\w.~+/=-]{16,}"
                    r"|(?i:(?<=token=)|(?<=token: )|(?<=password=)|(?<=password: )|(?<=secret=)|(?<=api_key=))[^\s\"']{8,}", re.S)
PHONE = re.compile(r"(?<![\w.-])(\+?81[- ]?|0)\d{1,4}[- ]\d{1,4}[- ]\d{3,4}(?![\w.-])|(?<![\w.-])0[789]0\d{8}(?![\w.-])")
CARD = re.compile(r"(?<!\d)(\d{4}[- ]){3}\d{4}(?!\d)")
SUSPECT = re.compile(r"住所|本名|氏名|生年月日|誕生日|電話番号|携帯番号|パスワード|暗証番号|口座|マイナンバー|保険証|免許証|旅券|パスポート"
                     r"|クレジットカード|〒|(?<![\d-])\d{3}-\d{4}(?![\d-])|password|passwd|address|phone", re.I)
DECISIONS = ROOT / "claude_session_log/decisions.yaml"
MODEL = re.compile(r"claude-(opus|sonnet|haiku|fable)-[0-9][\w.\[\]-]*|\b(Opus|Sonnet|Haiku|Fable) [0-9](\.[0-9])?\b", re.I)
REMIND = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def clean(t):
    t = SECRET.sub("[秘密の文字列を伏せた]", t)
    t = MAIL.sub("[メールアドレスを伏せた]", t)
    t = CARD.sub("[カード番号らしい数字を伏せた]", t)
    t = PHONE.sub("[電話番号を伏せた]", t)
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


ORDER = re.compile(r"^(?:    val: \{|      )order: (\d+)", re.M)


def decisions():
    return (yaml.safe_load(DECISIONS.read_text(encoding="utf-8")) or {}) if DECISIONS.exists() else {}


def decide(uid, what, why):
    assert what in ("keep", "withhold"), what
    d = decisions()
    d[uid] = {"decision": what, "reason": why}
    DECISIONS.write_text("# 保留した発言と差し控えた発言の決定（Claude が決める）。発言の中身は持たない。規則は build.py。\n"
                         + yaml.dump(d, allow_unicode=True, sort_keys=True), encoding="utf-8")
    if what == "withhold":
        (PARTS / f"{uid}.yaml").unlink(missing_ok=True)


def main():
    if sys.argv[1] == "--decide":
        decide(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))
        return
    pending = sys.argv[1] == "--pending"
    src = sys.argv[2] if pending else sys.argv[1]
    if src == "-":
        src = json.load(sys.stdin)["transcript_path"]
    us = utterances(src)
    PARTS.mkdir(exist_ok=True)
    dec = decisions()
    if pending:
        for ts, k, s, key in us:
            uid = ulid(ts, key)
            if not (PARTS / f"{uid}.yaml").exists() and uid not in dec:
                print(uid, k, s[:80].replace("\n", " "))
        return
    have = {f.stem for f in PARTS.glob("*.yaml")}
    base = max((int(m) for f in PARTS.glob("*.yaml") for m in ORDER.findall(f.read_text(encoding="utf-8"))), default=0)
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
    last, body, ids, held = {}, [], set(), []
    new = 0
    for ts, k, s, key in us:
        uid = ulid(ts, key)
        assert uid not in ids, uid
        ids.add(uid)
        what = dec.get(uid, {}).get("decision")
        hit = sorted(set(m.group(0) for m in SUSPECT.finditer(re.sub(r"\[[^\]]*を伏せた\]", "", s))))
        if what == "withhold" or (uid not in have and hit and what != "keep"):
            if what != "withhold":
                held.append((uid, k, hit, s))
            continue   # 記録しない発言は、応答の事実の終点にもしない
        fs = [{"is": "v_say", "from": speaker[k], "to": uid}]
        if k != "summary":
            other = last.get("model" if k == "user" else "user")
            if other:
                fs.append({"is": "exp.v_answer", "from": uid, "to": other})
            last[k] = uid
        if uid in have:
            continue
        new += 1
        i = base + new
        fs += [{"is": "v_refer", "from": uid, "to": n} for n in mentions(s)]
        body.append((uid, ts, {"is": kind[k], "display": f"発言 {i}", "val": {"order": i, "text": Block(s + "\n") if "\n" in s else s}}, fs))
    dump = lambda x: yaml.dump(x, allow_unicode=True, sort_keys=False, width=10**9, default_flow_style=None)
    for uid, ts, v, fs in body:
        (PARTS / f"{uid}.yaml").write_text(f"# 領域 claude_session_log の部分。記録の時刻 {ts}（UTC）\n" + dump({"individuals": {uid: v}, "facts": fs}), encoding="utf-8")
    kinds = [re.search(r"is: (\w+)", f.read_text(encoding="utf-8").split("individuals:", 1)[1]).group(1) for f in PARTS.glob("*.yaml")]
    count = (f"発言 {len(kinds)}（利用者 {kinds.count('user_utterance')}、Claude {kinds.count('model_utterance')}、"
             f"要約 {kinds.count('session_summary')}）")
    head = ("# 領域 claude_session_log（Claude Code のセッションの記録）。発言を、原文と事実で持つ（伏せた所と、差し控えた発言を除く）。\n"
            "# 発言は1つずつ utterances/<ULID>.yaml に置く（parts）。作り方と規則は claude_session_log/build.py。手で書き換えない（作り直す）。\n"
            f"# {count}。\n")
    OUT.write_text(head + dump({"domain": DOMAIN, "parts": "claude_session_log/utterances/*.yaml", "nodes": NODES,
                                "individuals": ind, "facts": facts}), encoding="utf-8")
    print(f"新しい発言 {new}。" + head)
    if held:
        print(f"記録を保留した発言が {len(held)} あります（個人の情報を指すかもしれない語を含む）。中身を見て決めてください:\n"
              "  記録する:   bash .claude/hooks/session_log.sh --decide <ULID> keep <理由>\n"
              "  記録しない: bash .claude/hooks/session_log.sh --decide <ULID> withhold <理由>", file=sys.stderr)
        for uid, k, hit, s in held:
            print(f"- {uid}（{k}、語: {', '.join(hit)}）: {s[:120]!r}", file=sys.stderr)
        sys.exit(2)


NODES = {
    "utterance": {"display": "発言", "extends": "syntax.passage_express_from_natural_language", "mod": {"of": ["exp.v_speak", "to"]}, "many": True},
    "user_utterance": {"display": "利用者の発言", "extends": "utterance", "mod": {"of": ["exp.v_speak", "to"], "with": "subj.person"}},
    "model_utterance": {"display": "Claude の発言", "extends": "utterance", "mod": {"of": ["exp.v_speak", "to"], "with": "std.model"}},
    "session_summary": {"display": "文脈が尽きたときの要約", "extends": "model_utterance", "mod": {"of": ["v_refer", "from"], "with": "utterance"}},
    "v_say": {"display": "発言する", "extends": "exp.v_speak", "to": "utterance"},
}

if __name__ == "__main__":
    main()
