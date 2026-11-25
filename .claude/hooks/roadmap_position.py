"""ロードマップの位置の書き方（Stop）

応答を終える前に、最後の応答の終わりの「ロードマップの位置:」の段がそろっているかを見る（CLAUDE.md の「報告の終わり」）。
今いる場所だけでなく、何を確かめることで、どのように目的につなげるかという計画を見せるため。
見るもの: 目的の行、設計の行、計画の段（[今] の段が 1 つ以上、[次] か [先] の段が 1 つ以上。段はどれも「→」で、確かめることと決まることをつなぐ）、分かれ目の行。

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
    if not re.search(r"(?m)^\s*[-*]?\s*(?:\*\*)?目的(?:\*\*)?\s*[:：]\s*\S", block):
        out.append("「目的:」の行がない")
    if not re.search(r"(?m)^\s*[-*]?\s*(?:\*\*)?設計(?:\*\*)?\s*[:：]\s*\S", block):
        out.append("「設計:」の行がない（この仕事が設計のどの部品を確かめ、変えるか）")
    if not re.search(r"(?m)^\s*[-*]?\s*(?:\*\*)?分かれ目(?:\*\*)?\s*[:：]\s*\S", block):
        out.append("「分かれ目:」の行がない")
    steps = re.findall(r"(?m)^\s*[-*]?\s*\[(済|今|次|先)\](.*)$", block)
    marks = [m for m, _ in steps]
    if "今" not in marks:
        out.append("計画に [今] の段がない")
    if "次" not in marks and "先" not in marks:
        out.append("計画に [次] か [先] の段がない（目的までの先が見えない）")
    for m, body in steps:
        if "→" not in body:
            out.append(f"[{m}] の段に「確かめること → 決まること」の → がない: {body.strip()[:40]}")
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
        "応答の終わりを、次の形で書き直す（CLAUDE.md の「報告の終わり」）:\n"
        "ロードマップの位置:\n"
        "- 目的: <d_goal が何を上げるか、何で測るか>\n"
        "- 設計: <この仕事が確かめる・変える設計の部品と、全体のどこに入るか>\n"
        "- 計画:\n"
        "  - [済] <確かめたこと> → <決まったこと>\n"
        "  - [今] <いま確かめていること> → <それで決まること>\n"
        "  - [次] <次に確かめること> → <それで決まること>\n"
        "  - [先] <目的の判定に届く段> → <d_goal が言えること>\n"
        "- 分かれ目: <今の段が支持なら…／反証なら…>"
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
