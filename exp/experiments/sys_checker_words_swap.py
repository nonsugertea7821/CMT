"""h_checker_words_swap を確かめる: 型検査器が名前で読む 3 語を式の読みに替えても、検査の結果は変わらないか。

仮説（claims.yaml）: v_refer(h, v_not_depend(type_checker, syntax.identifier))。登録 6e26459。issue #515。
  出どころ: h_checker_words_by_formula（#300）で role と definition は属と mod の式で名前の集合と一致し、
  h_refer_by_exact_holds（#503、支持）で v_refer は holds の原子の全体の一致で名前の集合と一致した。
  集合が一致するなら、検査器の読みを差し替えても結果は変わらないはず、というのが含意。

操作: 体系のファイルも検査器のファイルも変えない。検査器の source を読み、メモリの上で次の 5 か所を差し替えた写しを作り、
  別のプロセスで build() と check_all() を呼ぶ（差し替えない写しも、同じく別のプロセスで 2 回呼ぶ）。
    A  occupies:   self.is_a(end, "role")            → end が S_form(role) にある
    B  grounding:  self.is_a(m["with"], "definition") → m["with"] が S_form(definition) にある
    C  check:      self.is_a(nid, "role")            → nid が S_form(role) にある
    D  gather:     short(verb) == "v_refer"           → verb が v_refer と同じ式を持つ（下の id_form）
    E  field_ok:   m["of"] == ["syntax.v_refer", "from"] → m["of"][0] が id_form で、位置が from
  式の読み（集合は build の途中で、木ができたあとに一度だけ作る）:
    S_form(W)（W = role, definition）: #300 の読み。G = W の extends。x が is_a(x, G) で、x か上位の mod に、
      W の mod と of・neg が同じで、with が W の mod の with の下にあるもの。
      ただし role の mod の with（definition）の下は、名前の is_a ではなく S_form(definition) で読む。
      属 G と、definition の mod の with（concept）は名前で読む（3 語ではない）。
    id_form(x): x 自身が holds か pre を持ち、check の「動詞の式が同じ」と同じ署名（holds・pre・post の原子と from・to・new_kind）が
      v_refer の署名と等しい。check がこの署名の重なりを誤りにするので、等しいのは v_refer だけになるはず。
      D と E はもとから名前の is_a ではなく名前の一致なので、式の読みも一致（下位を含めない）で書いた。
  比べるもの（行 name_1, name_2, form）:
    errors（並べたもの）、T.roles（並べたもの）、領域の中身 Dm の要約（sha256。集合は並べて書く）、check_all の領域の検査の結果の要約（sha256）。
    診断（判定の外）: 各か所の呼ばれた数と、名前の読みと式の読みが分かれた数（form の行だけ）。
行（sys_checker_words_swap.json）: name_1, name_2, form, s。
  s: ok_build, deterministic（name_1 と name_2 が等しい）, same_errors, same_roles, same_dm, same_out, n_site_hit, n_disagree。

判定（事前に決める）:
  差し替えがどれか 1 か所でもちょうど 1 回当たらないか、どれかの build が例外で止まるか、name_1 と name_2 が違えば外れ（状態を変えない）。
  支持: same_errors, same_roles, same_dm, same_out がすべて真。
  反証: どれか一つでも偽。
開示:
  - #300 と #503 で集合が一致したので、A・B・C の差し替えは同じ答えを返すはず、という見込みで登録した。見込みどおりなら、
    差し替えで何かが変わることは、集合の一致ではとらえていない読みの違い（呼ばれる時点・解き方の違い）を意味する。
  - id_form は、check の署名の一意性に寄りかかっている。署名の一意性そのものは確かめない。
  - 走らせる前に、差し替えた写しの build は試していない（差し替えの文字列が当たるかだけを、source の grep で見た）。
使い方:
  python exp/experiments/sys_checker_words_swap.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results/sys_checker_words_swap.json"
TC = ROOT / "cscl/bootstrap/type_checker/type_checker.py"
SITES = {
    "A": ('self.is_a(end, "role")', '_F("role", end, self, "A")'),
    "B": ('self.is_a(m["with"], "definition")', '_F("definition", m["with"], self, "B")'),
    "C": ('self.is_a(nid, "role")', '_F("role", nid, self, "C")'),
    "D": ('short(verb) == "v_refer"', '_FV(verb, T, "D")'),
    "E": ('m["of"] == ["syntax.v_refer", "from"]', '(_FV(self.q(m["of"][0]), self, "E") and m["of"][1] == "from")'),
}
CHILD = r"""
import contextlib, hashlib, io, json, os, sys, types
from pathlib import Path
mode, tc_path, sites = sys.argv[1], Path(sys.argv[2]), json.loads(sys.argv[3])
os.chdir(tc_path.parents[3])
src = tc_path.read_text(encoding="utf-8")
hits = {}
if mode == "form":
    for k, (old, new) in sites.items():
        hits[k] = src.count(old)
        src = src.replace(old, new)
mod = types.ModuleType("type_checker")
mod.__file__ = str(tc_path)
sys.modules["type_checker"] = mod
stat = {k: {"n": 0, "disagree": 0} for k in sites}
cache = {}

def atom_sig(T, x):
    n = T.N[x]
    a = mod.atom
    return tuple(tuple(sorted(map(a, n.get(k, [])))) for k in ("holds", "pre", "post")) + (n.get("from"), n.get("to"), n.get("new_kind"))

def forms(T):
    if "S" in cache:
        return cache["S"]
    N = T.N
    res = lambda w: w if (not isinstance(w, str) or w in N) else (T.resolve(w, "signature") or w)
    def mods(x):
        out = []
        for y in [x] + T.ancestors(x):
            ms = N[y].get("mod") or []
            for m in (ms if isinstance(ms, list) else [ms]):
                if isinstance(m, str):
                    m = N.get(res(m), {})
                if isinstance(m, dict) and "of" in m:
                    out.append({"of": [res(m["of"][0]), m["of"][1]], "with": res(m.get("with")) if m.get("with") else None,
                                "neg": bool(m.get("neg"))})
        return out
    def wmod(W):
        ms = N[W].get("mod")
        ms = ms if isinstance(ms, list) else [ms]
        m = ms[0]
        if isinstance(m, str):
            m = N.get(res(m), {})
        return {"of": [res(m["of"][0]), m["of"][1]], "with": res(m.get("with")) if m.get("with") else None, "neg": bool(m.get("neg"))}
    def s_form(W, under):
        G = res(N[W].get("extends"))
        wm = wmod(W)
        return {x for x in N if T.is_a(x, G) and any(
            m["of"] == wm["of"] and m["neg"] == wm["neg"] and (wm["with"] is None or (m["with"] and under(m["with"], wm["with"])))
            for m in mods(x))}
    D = res("definition")
    sd = s_form(D, lambda a, b: T.is_a(a, b))
    sr = s_form(res("role"), lambda a, b: a in sd if b == D else T.is_a(a, b))
    V = res("v_refer")
    cache["S"] = {"role": sr, "definition": sd, "vsig": atom_sig(T, V), "V": V}
    return cache["S"]

def _F(word, x, T, site):
    S = forms(T)
    xq = T.q(x)
    a = xq in S[word]
    b = T.is_a(x, word)
    stat[site]["n"] += 1
    stat[site]["disagree"] += a != b
    return a

def _FV(verb, T, site):
    S = forms(T)
    v = verb if verb in T.N else T.q(verb)
    a = v in T.N and ("holds" in T.N[v] or "pre" in T.N[v]) and atom_sig(T, v) == S["vsig"]
    b = mod.short(verb) == "v_refer" if site == "D" else verb == "syntax.v_refer"
    stat[site]["n"] += 1
    stat[site]["disagree"] += a != b
    return a

mod._F, mod._FV = _F, _FV
def norm(v):
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((norm(x) for x in v), key=lambda z: json.dumps(z, sort_keys=True, ensure_ascii=False))
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)
digest = lambda v: hashlib.sha256(json.dumps(norm(v), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
row = {"mode": mode, "hits": hits}
try:
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(src, str(tc_path), "exec"), mod.__dict__)
        T, O, Dm, out = mod.check_all()
    row.update({"ok": True, "errors": sorted(mod.errors), "roles": sorted(T.roles), "dm": digest(Dm), "out": digest(out)})
except Exception as e:
    row.update({"ok": False, "exc": repr(e)[:500]})
row["stat"] = stat if mode == "form" else {}
print(json.dumps(row, ensure_ascii=False))
"""


def run(mode):
    p = subprocess.run([sys.executable, "-c", CHILD, mode, str(TC), json.dumps(SITES)], capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"mode": mode, "ok": False, "exc": (p.stderr or p.stdout)[-800:]}


def main():
    r = {"name_1": run("name"), "name_2": run("name"), "form": run("form")}
    ok = all(x.get("ok") for x in r.values())
    hits_ok = r["form"].get("hits") == {k: 1 for k in SITES}
    keys = ("errors", "roles", "dm", "out")
    det = ok and all(r["name_1"][k] == r["name_2"][k] for k in keys)
    s = {"ok_build": ok, "hits_ok": hits_ok, "deterministic": det}
    if ok:
        for k in keys:
            s[f"same_{k if k not in ('dm', 'out') else k}"] = r["name_1"][k] == r["form"][k]
        st = r["form"]["stat"]
        s["n_site_hit"] = sum(1 for v in st.values() if v["n"])
        s["n_disagree"] = sum(v["disagree"] for v in st.values())
        s["n_err_name"], s["n_err_form"] = len(r["name_1"]["errors"]), len(r["form"]["errors"])
        s["err_only_form"] = sorted(set(r["form"]["errors"]) - set(r["name_1"]["errors"]))[:20]
        s["err_only_name"] = sorted(set(r["name_1"]["errors"]) - set(r["form"]["errors"]))[:20]
    if not (ok and hits_ok and det):
        s["verdict"] = "外れ"
    else:
        s["verdict"] = "支持" if all(s[f"same_{k}"] for k in keys) else "反証"
    OUT.write_text(json.dumps({**r, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
