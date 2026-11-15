"""モデルが書いた途中経過を、1行ずつ体系で検査する。

受け付ける行は3つの形:
  個体:  名前: {is: 種類}                      種類は体系のノード
  事実:  {is: 動詞, from: 始点, to: 終点, neg: true}   端は、宣言した個体・subj の個体・ノード。端の種類に当たること
  帰属:  {is: is, from: 名前, to: 種類}          個体が種類に属する（否定は neg: true）
識別子は、領域を書かずに書いてよい（subj、core の順に解決する）。

check(lines) は行ごとに (行, 形, 誤りの並び) を返す。誤りが空の行が、検査に通った行。
"""
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import check_spec  # noqa: E402

DOM = "subj"


class LineChecker:
    def __init__(self):
        self.T, self.O, self.S, _, _ = check_spec.build()
        if check_spec.errors:
            raise SystemExit("体系の検査に失敗: " + "; ".join(check_spec.errors[:3]))
        self.subj_ind = {i: f"{DOM}.{x['is']}" if f"{DOM}.{x['is']}" in self.T.N else x["is"]
                         for i, x in self.S["individuals"].items()}

    def node(self, w):
        if not isinstance(w, str):
            return None
        return self.T.resolve(w, DOM) if self.T.resolve(w, DOM) in self.T.N else None

    def kind_of(self, w, local):
        """端に来たものの種類。個体ならその種類、ノードならそれ自身。"""
        if w in local:
            return local[w]
        if w in self.subj_ind:
            return self.subj_ind[w]
        return self.node(w)

    def check(self, lines):
        T, local, out = self.T, {}, []
        for raw in lines:
            line = raw.strip().strip("`").lstrip("- ").strip()
            if not line:
                continue
            errs = []
            try:
                y = yaml.safe_load(line)
            except yaml.YAMLError:
                out.append((raw, "unparsed", ["YAML として読めない"]))
                continue
            if isinstance(y, dict) and len(y) == 1 and isinstance(next(iter(y.values())), dict) and "is" in next(iter(y.values())) \
                    and set(next(iter(y.values()))) <= {"is", "ja"}:
                (name, x), = y.items()
                k = self.node(x["is"])
                if k is None:
                    errs.append(f"種類 {x['is']} がノードでない")
                elif str(name) in self.subj_ind or self.node(str(name)):
                    errs.append(f"名前 {name} が、体系の識別子と重なる")
                else:
                    local[str(name)] = k
                out.append((raw, "individual", errs))
                continue
            if not (isinstance(y, dict) and "is" in y):
                out.append((raw, "unparsed", ["個体・事実・帰属のどの形でもない"]))
                continue
            if set(y) - {"is", "from", "to", "new", "neg", "at"}:
                errs.append(f"語 {set(y) - {'is', 'from', 'to', 'new', 'neg', 'at'}} は事実に書けない")
            if y["is"] == "is":
                s, k = self.kind_of(y.get("from"), local), self.node(y.get("to"))
                if s is None:
                    errs.append(f"始点 {y.get('from')} が、宣言した個体でも体系のものでもない")
                if k is None:
                    errs.append(f"終点 {y.get('to')} が種類でない")
                out.append((raw, "membership", errs))
                continue
            verb = self.node(y["is"])
            if verb is None or not T.is_verb(verb):
                out.append((raw, "fact", errs + [f"{y['is']} は動詞でない"]))
                continue
            for pos in ("from", "to"):
                if pos not in y:
                    continue
                k = self.kind_of(y[pos], local)
                end = T.end(verb, pos)
                if k is None:
                    errs.append(f"{pos} の {y[pos]} が、宣言した個体でも体系のものでもない")
                elif end not in ("any", None) and not (T.is_a(k, end) or T.occupies(k, end, verb)):
                    errs.append(f"{pos} の {y[pos]}（{k}）は、{verb} のその位置（{end}）に来られない")
            out.append((raw, "fact", errs))
        return out


def extract(text):
    """生成した文章から、検査にかける行を取り出す。波括弧か「名前: {」を含む行。"""
    return [l for l in text.splitlines() if re.search(r"\{.*\}", l)]


if __name__ == "__main__":
    C = LineChecker()
    demo = ["x: {is: goods}", "w: {is: warehouse}", "o: {is: order}", "{is: v_store, from: x, to: w}",
            "{is: v_allocate, from: o, to: x}", "{is: is, from: x, to: stock, neg: true}", "{is: v_store, from: w, to: x}",
            "{is: v_fly, from: x, to: w}"]
    for raw, form, errs in C.check(demo):
        print("OK " if not errs else "NG ", form, raw, errs)
