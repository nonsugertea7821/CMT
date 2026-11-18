"""README の生成する部分を、体系から作る。手で書く部分は体系の名前を一つも持たず、体系を指す部分はここが作る。

選び方は問い合わせ（状態が「採用」の決定すべて）で、名前を固定で持たない。文は表示の変換器（display.sentence）で式から訳す。
識別子や表示語の作り方が変われば、ここの出力も同じ変換を通って変わる。

使い方:
  python .github/scripts/build_readme.py          README.md の生成する部分を書き換える
  python .github/scripts/build_readme.py --check  今の体系から作り直したものと違えば 1 で終わる（CI）
"""
import contextlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / "cscl/bootstrap/display")]
with contextlib.redirect_stdout(io.StringIO()):
    import sync_issues  # noqa: E402
    import display  # noqa: E402
    from sync_issues import exp_check, type_checker  # noqa: E402

README = ROOT / "README.md"
BEGIN, END = "<!-- generated:begin -->", "<!-- generated:end -->"


def generated():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, S, M, C = exp_check.build()
    if type_checker.errors:
        raise SystemExit("体系の検査に失敗: " + "; ".join(type_checker.errors[:3]))
    I = sync_issues.individuals()
    short = type_checker.short
    rows = {}
    for cid, x in C["decisions"].items():
        if sync_issues.status_label(T, x["status"]) != "adopted":
            continue
        ss, oo = ([v] if isinstance(v, str) else v for v in (x["s"], x["o"]))
        side = display.ja(T, C["side"][cid], I)
        for a in ss:
            for b in oo:
                rows.setdefault(side, []).append(
                    (display.sentence(T, x["p"], a, b, I), f"{{is: {short(x['p'])}, from: {short(a)}, to: {short(b)}}}"))
    out = ["_この節は体系から生成している。手で編集しない（`.github/scripts/build_readme.py`）。_", ""]
    for side in sorted(rows):
        out += [f"**{side}**", "", "| 文（式から訳したもの） | 式 |", "|---|---|"]
        out += [f"| {s} | `{f}` |" for s, f in rows[side]] + [""]
    return "\n".join(out).rstrip("\n")


def render(text):
    body = f"{BEGIN}\n{generated()}\n{END}"
    new, n = re.subn(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: body, text, flags=re.S)
    if n != 1:
        raise SystemExit(f"README.md に {BEGIN} と {END} の組がちょうど一つ要る（{n} 組あった）")
    return new


def main():
    text = README.read_text(encoding="utf-8")
    new = render(text)
    if "--check" in sys.argv:
        if new != text:
            print("README.md の生成する部分が、今の体系と違う。python .github/scripts/build_readme.py で作り直す。")
            sys.exit(1)
        print("README.md の生成する部分は、今の体系と同じ。")
        return
    README.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
