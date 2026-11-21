"""Wait—turn that observation into a hypothesis?（Stop）

応答を終える前に、最後の応答の文に「していません」系の否定（ません・ていない・がない など。英語の not・n't、中国語の 没有・不是 なども）があれば、
止まるのを一度だけ止めて、その否定を未検証の仮説として登録するかを Claude に問い直させる。

「体系に〜がない」「〜していない」は、確かめた事実のこともあるが、確かめていない主張のことも多い。
確かめていない主張なら、それを理由に何かを見送る前に、仮説として登録する（CLAUDE.md の「提案」）。

考えや応答が英語や中国語に流れたときにも働くよう、英語と中国語の否定も拾う。言語そのものは問わない（英語で考えることは止めない）。

連鎖を防ぐため、stop_hook_active のとき（このフックで続けた後の停止）は何もしない。
"""
import json
import re
import sys

TITLE = "Wait—turn that observation into a hypothesis?"
NEG_JA = re.compile(r"(ません|ていない|でいない|していない|がない|はない|もない|できない|られない|わからない|分からない)")
NEG_EN = re.compile(r"(?i)\b(not|no|never|none|nothing|cannot|without|\w+n't)\b")
NEG_ZH = re.compile(r"(没有|没|不是|不能|不会|无法|并未|尚未|不存在|未能)")


def negations(s):
    return NEG_JA.search(s) or NEG_EN.search(s) or NEG_ZH.search(s)



def last_text(data):
    t = data.get("last_assistant_message")
    if isinstance(t, str) and t.strip():
        return t
    path = data.get("transcript_path")
    if not path:
        return ""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return ""
    out = []
    for ln in reversed(lines):
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        msg = e.get("message") or {}
        if e.get("type") == "user":
            c = msg.get("content")
            if isinstance(c, str) or not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c or []):
                break
            continue
        if e.get("type") == "assistant":
            for b in reversed(msg.get("content") or []):
                if isinstance(b, dict) and b.get("type") == "text":
                    out.append(b.get("text", ""))
            if out:
                break
    return "\n".join(reversed(out))


def sentences(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    parts = re.split(r"(?<=[。！？\n])|(?<=[.!?])\s+", text)
    return [s.strip(" -*\n") for s in parts if s and negations(s)]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("stop_hook_active"):
        return
    hits = sentences(last_text(data))
    if not hits:
        return
    listed = "\n".join(f"- {s}" for s in hits[:8])
    reason = (
        f"{TITLE}\n"
        f"最後の応答に、否定の文がある:\n{listed}\n"
        "それぞれについて決める:\n"
        "1. 確かめた事実（測った・読んだ・検査が言った）なら、そのまま終えてよい。\n"
        "2. 確かめていない主張（とくに「体系に〜がない」「〜できない」を、何かを見送る理由にしているもの）なら、"
        "未検証の仮説として登録する（h_ と b_、v_refer、v_check、v_ground。結ぶ決定がなければ「わき道」）。\n"
        "3. 進みの報告（走っている・終わっていない など）は、そのまま終えてよい。\n"
        "登録したものと、登録しなかった理由を一言ずつ添えて終える。"
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
