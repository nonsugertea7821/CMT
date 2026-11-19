"""h_roadmap_by_ground を確かめる: 未検証の仮説は、ロードマップの決定に結べるか（トリアージを兼ねる）。

仮説（exp.yaml）: v_depend(hypothesis, d_goal)。
  読み: どの仮説も、決定どうしの v_depend と決定から仮説への v_ground をたどって d_goal に届くように書ける。
  届かない仮説がわき道である。
背景: 利用者と組んだロードマップ（PR #375）を、d_goal → d_metric → d_road_region・d_road_checker →
  lang.d_cscl_display_derived の決定の鎖として体系に書いた。結んだ根拠は 5 つの仮説だけ。
  ほかの未検証の仮説が、結び忘れなのか、わき道なのかを、名前でなく式で分ける。
操作: 体系を変えない。測るだけ。
数え方:
  H        未検証の仮説（is が hyp_untested の個体。exp と lang の両方）
  R        exp.d_goal から、始点が決定（名前 d_ の個体）の v_depend と v_ground をたどって届く個体
  on_path  H のうち R に入るもの（いま結ばれている）
  TR       R に入る決定の v_refer の式に現れる語（ロードマップの語）
  語の取り出し: 式（入れ子を含む）の from と to に現れる名字を集める。動詞（T.is_verb）は除く。
    名前の解決: 「.」を含めばそのまま。含まなければ、その仮説の領域.名前、次に syntax・std・ontology・signature・runtime・
    exp・lang の順で T.N にあるものを取る。どこにもなければ名前のまま（個体）。
  linkable 仮説 h（on_path でない）の式の語 c のどれかが、TR の語 t と等しいか、t を祖先（T.ancestors）に持つ。
    つまり、仮説がロードマップの語そのもの、またはその下位について述べている。
  厳しい数え方（判定に使う）: TR から、文法・シグネチャ・存在論の語（syntax.・signature.・ontology. で始まる語）を除く。
    これらは一般の語で、下位が多く、どの仮説でも当たりうるため。
  緩い数え方（記録だけ）: TR をそのまま使う。
  detour   on_path でも linkable でもないもの
  share    (on_path + linkable) / |H|（厳しい数え方）
行（sys_roadmap_reach.json）:
  "summary 要約": n_h、n_on_path、n_linkable、n_detour、share、n_linkable_loose、share_loose、tr（厳しい TR）、tr_loose、
                  verdict（1 支持、0 反証、2 mixed）、errors、ec_errors
  "h <名前>": domain、cls（on_path / linkable / detour）、cls_loose、terms（式の語）、hits（当たった TR の語）
判定（事前に決める。厳しい数え方で）:
  errors か ec_errors が 0 でなければ外れとし、状態は変えない。
  share ≥ 0.8 なら支持（大半の仮説はロードマップの語について述べていて、結べる）。
  share < 0.5 なら反証（半分以上はロードマップの語に触れず、わき道か、ロードマップに欠けた枝がある）。
  そのあいだは mixed。
  仮説の文言は「どの仮説も」だが、語の重なりは結べることの必要条件でしかなく、取りこぼしもある。そのため 1.0 を求めず、上の幅で読む。
登録の前に分かっていること:
  - 下調べで on_path は 51 のうち 5（PR #375 の本文。手で数えた目安）。
  - TR の厳しい語は、exp.redefinition_success、exp.cross_usage_consistency、exp.midpoint_membership、
    exp.formalization_accuracy、lang.type_checker の見込み（exp.this_design は個体）。緩い語には syntax.display・syntax.system が入る。
  - 個々の仮説がどれに当たるかは、まだ数えていない。
  - 語の重なりは、仮説がロードマップの目標を支えることまでは示さない（同じ語について別のことを述べうる）。linkable は候補であり、
    結ぶかどうかは、後の PR で v_ground を書くときに決める。
使い方:
  python exp/experiments/sys_roadmap_reach.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "cscl/bootstrap/type_checker"), str(ROOT / "exp/src")]
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402
OUT = ROOT / "exp/experiments/results/sys_roadmap_reach.json"
FILES = {"exp": ROOT / "exp/src/exp.yaml", "lang": ROOT / "cscl/design/claims.yaml"}
ORDER = ["syntax", "std", "ontology", "signature", "runtime", "exp", "lang"]
GENERIC = ("syntax.", "signature.", "ontology.")


def resolve(x, dom, T):
    if "." in x:
        return x
    for p in [dom] + ORDER:
        if f"{p}.{x}" in T.N:
            return f"{p}.{x}"
    return x


def words(e, dom, T, out):
    if isinstance(e, list):
        for v in e:
            words(v, dom, T, out)
    elif isinstance(e, dict):
        for k in ("from", "to"):
            if k in e:
                words(e[k], dom, T, out)
    elif isinstance(e, str):
        q = resolve(e, dom, T)
        if not (q in T.N and T.is_verb(q)):
            out.add(q)


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    n_err = len(tc.errors)
    with contextlib.redirect_stdout(io.StringIO()):
        import exp_check
        del tc.errors[:]
        try:
            exp_check.build()
        except SystemExit:
            pass
    ec_err = len(tc.errors)
    D = {d: yaml.safe_load(p.read_text(encoding="utf-8")) for d, p in FILES.items()}

    def qi(x, d):
        return x if "." in x else f"{d}.{x}"

    H = {}
    for d, Y in D.items():
        for k, v in (Y.get("individuals") or {}).items():
            if isinstance(v, dict) and str(v.get("is", "")).split(".")[-1] == "hyp_untested":
                H[qi(k, d)] = d
    edges, refer = {}, {}
    for d, Y in D.items():
        for f in Y["facts"]:
            t = str(f.get("is", "")).split(".")[-1]
            fr = f.get("from")
            if not isinstance(fr, str):
                continue
            if t in ("v_depend", "v_ground") and fr.split(".")[-1].startswith("d_"):
                for x in (f["to"] if isinstance(f["to"], list) else [f["to"]]):
                    if isinstance(x, str):
                        edges.setdefault(qi(fr, d), []).append(qi(x, d))
            if t == "v_refer":
                refer.setdefault(qi(fr, d), []).append((f["to"], d))
    R, st = set(), ["exp.d_goal"]
    while st:
        n = st.pop()
        if n not in R:
            R.add(n)
            st += edges.get(n, [])
    tr_loose = set()
    for n in R:
        if n.split(".")[-1].startswith("d_"):
            for e, d in refer.get(n, []):
                words(e, d, T, tr_loose)
    tr = {t for t in tr_loose if not t.startswith(GENERIC)}

    def hits(terms, TR):
        out = set()
        for c in terms:
            anc = set(T.ancestors(c)) if c in T.N else set()
            out |= {t for t in TR if t == c or t in anc}
        return out

    rows = {}
    for h, d in sorted(H.items()):
        terms = set()
        for e, dd in refer.get(h, []):
            words(e, dd, T, terms)
        if h in R:
            cls = cls_l = "on_path"
            hs = hl = set()
        else:
            hs, hl = hits(terms, tr), hits(terms, tr_loose)
            cls = "linkable" if hs else "detour"
            cls_l = "linkable" if hl else "detour"
        rows[f"h {h}"] = {"domain": d, "cls": cls, "cls_loose": cls_l, "terms": sorted(terms), "hits": sorted(hs | hl)}
    n = len(H)
    cnt = {c: sum(1 for r in rows.values() if r["cls"] == c) for c in ("on_path", "linkable", "detour")}
    lin_l = sum(1 for r in rows.values() if r["cls_loose"] == "linkable")
    s = {"n_h": n, "n_on_path": cnt["on_path"], "n_linkable": cnt["linkable"], "n_detour": cnt["detour"],
         "share": (cnt["on_path"] + cnt["linkable"]) / n if n else 0.0,
         "n_linkable_loose": lin_l, "share_loose": (cnt["on_path"] + lin_l) / n if n else 0.0,
         "tr": sorted(tr), "tr_loose": sorted(tr_loose), "errors": n_err, "ec_errors": ec_err}
    if n_err or ec_err:
        s["verdict"] = -1
    elif s["share"] >= 0.8:
        s["verdict"] = 1
    elif s["share"] < 0.5:
        s["verdict"] = 0
    else:
        s["verdict"] = 2
    rows = {"summary 要約": s, **rows}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    for k, r in rows.items():
        if k.startswith("h "):
            print(r["cls"], r["cls_loose"], k, r["hits"])


if __name__ == "__main__":
    main()
