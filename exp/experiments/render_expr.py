"""概念式を、モデルに与える文字列に変換する（実験の道具。表示の変換そのものは cscl/bootstrap/display）。

1行に1つの種類を書く:  名前 ＝ 上位 ∧ 限定
限定は 動詞(始点, 終点) の形で、自分の位置を「これ」と書く。否定は ¬、量の条件は 相手<25 のように書く。
題材の領域 subj の種類は、式の中で参照している subj の種類と事実までたどって並べる。

使い方: python exp/experiments/render_expr.py 顧客 在庫
"""
import re
import sys

import yaml
from pathlib import Path

_B = Path(__file__).resolve().parents[2] / "cscl" / "bootstrap"
sys.path[:0] = [str(_B / "type_checker"), str(_B / "display")]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import type_checker  # noqa: E402
import exp_check  # noqa: E402
import display  # noqa: E402
from display import ja as _ja_  # noqa: E402


def _ja(T, x, S):   # 実験のスクリプト（e13）が使う形
    return _ja_(T, x, S["individuals"])


DOM = "subj"


class Renderer:
    def __init__(self):
        self.T, self.O, self.S, _, _ = exp_check.build()
        if type_checker.errors:
            raise SystemExit("体系の検査に失敗: " + "; ".join(type_checker.errors[:3]))
        self.by_ja = {n.get("display"): nid for nid, n in self.T.N.items() if nid.startswith(DOM + ".")}

    def line(self, nid):
        return display.line(self.T, nid, self.S["individuals"])

    def refs(self, nid):
        return display.refs(self.T, nid)

    def facts(self, nids):
        out = []
        for f in self.S.get("facts") or []:
            if any(f.get(k) in nids for k in ("from", "to")):
                v = type_checker.qualify(f["is"], self.S["_local"], DOM)
                a, b = (type_checker.qualify(f[k], self.S["_local"], DOM) for k in ("from", "to"))
                out.append(display.fact(self.T, v, a, b, self.S["individuals"]))
        return out

    def text(self, word, mask=False, opaque=False, inds=False):
        """語の概念式と、それがたどる subj の種類と事実。

        opaque: axiom 以外の識別子（subj の種類・動詞・個体の名前）を、意味を持たない記号 X01, X02, ... に置き換える。
        表示名は、語そのものと個体（設問に出てくる固有のもの）だけ残す（mask と同じ）。識別はできるが、
        意味を運ぶのは axiom の識別子と、式の構造（extends, mod, of, neg, at など）だけになる。
        inds: 種類の限定が参照する個体（日曜、本州など）の行も並べる。False は E10・E11・E3-expr で使った出力
        （mod が並びのとき個体の行が落ちていた）を再現する。"""
        start = self.by_ja[word]
        seen, order, todo = set(), [], [start]
        while todo:
            x = todo.pop(0)
            if x in seen or not x.startswith(DOM + ".") or x not in self.T.N:
                continue
            seen.add(x)
            order.append(x)
            todo += self.refs(x)
        local = {x.split(".", 1)[1] for x in seen}
        lines = self.raw(local, inds)
        if mask:   # 表示名を外す。語そのものの種類と、個体（設問に出てくる固有のもの）の表示名は残す
            keep = start.split(".", 1)[1]
            lines = [l if l.startswith(keep + ":") or l.startswith("{") or "{is:" in l.split(":", 1)[1][:6]
                     else re.sub(r"display: [^,]*, ", "", l) for l in lines]
        if opaque:
            names = set(self.S.get("nodes") or {}) | set(self.S.get("individuals") or {}) | local
            order = []
            for l in lines:
                for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", l):
                    if tok in names and tok not in order:
                        order.append(tok)
            code = {n: f"X{i + 1:02d}" for i, n in enumerate(order)}
            lines = [re.sub(r"[A-Za-z_][A-Za-z0-9_]*", lambda m: code.get(m.group(0), m.group(0)), l) for l in lines]
        return "\n".join(lines)

    def raw(self, local, with_inds=False):
        """subj.yaml に書いたままの行。種類の行と、それらに触れる個体と事実の行。"""
        src = (type_checker.SPEC / type_checker.domain_files()["subj"]).read_text(encoding="utf-8").splitlines()
        import re
        inds = {f.get(k) for f in self.S.get("facts") or [] for k in ("from", "to") if f.get("to") in local or f.get("from") in local}
        for n in local:
            mod = self.T.N[f"{DOM}.{n}"].get("mod")
            for m in (mod if with_inds and isinstance(mod, list) else [mod]):
                if isinstance(m, dict) and m.get("with") in self.S["individuals"]:
                    inds.add(m["with"])
        nodes, ind, facts = [], [], []
        for l in src:
            k = re.match(r"^  (\w+):", l)
            if k and k.group(1) in local:
                nodes.append(l.strip())
            elif k and k.group(1) in inds:
                ind.append(l.strip())
            elif l.startswith("  - ") and any((yaml.safe_load(l[4:]) or {}).get(k) in local for k in ("from", "to")):
                facts.append(l.strip()[2:])
        return nodes + ind + facts


if __name__ == "__main__":
    R = Renderer()
    for w in sys.argv[1:]:
        print(R.text(w), end="\n\n")
