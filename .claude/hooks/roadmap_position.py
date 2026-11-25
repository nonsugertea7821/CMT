"""ロードマップの位置の書き方（Stop）

応答を終える前に、最後の応答の終わりに「ロードマップの位置:」の 4 行（道・今・次・分かれ目）がそろっているかを見る。
今いる場所だけでなく、この先の計画が見えるようにするため（CLAUDE.md の「報告の終わり」）。
道の行は d_goal から始まる鎖か、「わき道」と書く。次の行は ① から始めて、2 つ以上を並べる。

連鎖を防ぐため、stop_hook_active のとき（このフックで続けた後の停止）は何もしない。
"""
import json
import re
import sys

from observation_to_hypothesis import last_text

TITLE = "ロードマップの位置"


def problems(text):
    i = text.rfind(TITLE)
    if i < 0:
        return ["「ロードマップの位置:」の段がない"]
    block = text[i:]
    out = []
    lines = {}
    for ln in block.splitlines():
        m = re.match(r"\s*[-*]?\s*(?:\*\*)?(道|今|次|分かれ目)(?:\*\*)?\s*[:：](.*)", ln)
        if m:
            lines.setdefault(m.group(1), m.group(2).strip())
    for k in ("道", "今", "次", "分かれ目"):
        if not lines.get(k):
            out.append(f"「{k}:」の行がない")
    road = lines.get("道", "")
    if road and "d_goal" not in road and "わき道" not in road:
        out.append("道の行が d_goal から始まる鎖になっていない（わき道なら「わき道」と書く）")
    nxt = lines.get("次", "")
    if nxt and "②" not in nxt:
        out.append("次の行に ① ② と 2 つ以上並んでいない")
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("stop_hook_active"):
        return
    ps = problems(last_text(data))
    if not ps:
        return
    reason = (
        f"{TITLE}の書き方がそろっていない:\n" + "\n".join(f"- {p}" for p in ps) + "\n"
        "応答の終わりを、次の 4 行で書き直す（CLAUDE.md の「報告の終わり」）:\n"
        "ロードマップの位置:\n"
        "- 道: d_goal ← <決定> ← <仮説>\n"
        "- 今: <何をしているか・状態>\n"
        "- 次: ① <次の仮説か作業>（何が決まるか） ② …\n"
        "- 分かれ目: <支持なら…／反証なら…>"
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
