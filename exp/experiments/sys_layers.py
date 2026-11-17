"""体系そのものを数える: シグネチャ（基礎の関係）から定まる分類と、今の層の置き場。仮説 h_layers_signature の確かめ。
結果を見る前に、この説明と手順を登録した。

分類（シグネチャだけで書ける）:
  各ノードから定義の辺をたどって届くノードの集まりを求める。辺は、上位（extends）、限定の動詞（mod の of）と相手（with）、
  名前を付けた限定の of と with、動詞の端の種類（from, to, new_kind）。
  届いたノード（自分を含む）の holds・pre・post の原子に出る基礎の関係を集める。原子の読み方（真・偽・述べられていない）によらず数える
  （否定は「述べられていない」で、語としてはその関係を使う）。
    change  届いたノードに、pre か post を持つ動詞がある（変化する）
    refer   change でなく、基礎の関係に refer がある（述べる）
    still   change でも refer でもない（述べない・変わらない）
  比べる版（観察だけ。判定には使わない）: 否定の限定（neg の付いた mod・with）の辺をたどらない版 *_pos。

仮説 h_layers_signature: 層 ontology・syntax・runtime の置き場は、シグネチャから定まる分類と一致する。
  対応: ontology → still、syntax → refer、runtime → change。
判定（登録した基準）: 3つの層のすべてのノードが対応する分類に入れば支持（agree の平均が 1.0）。1つでも外れれば反証。
  層を法則で決めるには、どのノードも事実から判定できなければならないので、基準は「すべて」にした。
登録の前に分かっていること: 前の版の体系で、似た表を会話の中で作った（否定の読み方を決める前）。
  そのときは、否定の辺を数えると syntax の多くが変化に入り、数えなくても ontology に述べる語が 14 あった。だから反証が見込まれる。
  この確かめの目的は、一致の度合いと、外れるノードを記録に残すことにある。

sys_layers.json  ノード1つが1行（"node ノード"）。値はどれも 0 か 1。
  {層}_still, {層}_refer, {層}_change            その層のノードだけが持つ。分類（否定の辺もたどる）
  {層}_still_pos, {層}_refer_pos, {層}_change_pos  同じ、否定の辺をたどらない版
  agree, agree_pos                               ontology・syntax・runtime のノードだけが持つ。対応する分類に入る
  summary 行: supported

使い方:
  python exp/experiments/sys_layers.py
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cscl/bootstrap/type_checker"))
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc  # noqa: E402

OUT = ROOT / "exp/experiments/results"
EXPECT = {"ontology": "still", "syntax": "refer", "runtime": "change"}


def edges(T, nid, pos_only):
    n, out = T.N[nid], []
    if n.get("extends") in T.N:
        out.append(n["extends"])
    for k in ("from", "to", "new_kind"):
        if isinstance(n.get(k), str) and n[k] in T.N:
            out.append(n[k])
    lims = [n] if "of" in n else []
    ms = n.get("mod") or []
    lims += [m for m in (ms if isinstance(ms, list) else [ms]) if isinstance(m, dict)]
    for m in lims:
        if pos_only and m.get("neg"):
            continue
        if m.get("of") and m["of"][0] in T.N:
            out.append(m["of"][0])
        if m.get("with") in T.N:
            out.append(m["with"])
    return out


def classify(T, nid, pos_only):
    seen, todo = {nid}, [nid]
    while todo:
        for b in edges(T, todo.pop(), pos_only):
            if b not in seen:
                seen.add(b)
                todo.append(b)
    change = any("pre" in T.N[x] or "post" in T.N[x] for x in seen)
    rels = {a["is"] for x in seen for k in ("holds", "pre", "post") for a in T.N[x].get(k) or [] if isinstance(a, dict)}
    return "change" if change else "refer" if "refer" in rels else "still"


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        T, O, _ = tc.build()
    if tc.errors:
        raise SystemExit("体系の検査に失敗しているので測らない: " + "; ".join(tc.errors[:3]))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows, table = {}, {}
    for nid in sorted(T.N):
        layer = nid.split(".")[0]
        c, cp = classify(T, nid, False), classify(T, nid, True)
        row = {f"{layer}_{k}": int(c == k) for k in ("still", "refer", "change")}
        row |= {f"{layer}_{k}_pos": int(cp == k) for k in ("still", "refer", "change")}
        if layer in EXPECT:
            row |= {"agree": int(c == EXPECT[layer]), "agree_pos": int(cp == EXPECT[layer])}
            if c != EXPECT[layer]:
                print("外れ:", nid, c, "(否定の辺なし:", cp + ")")
        rows[f"node {nid}"] = row
        table.setdefault(layer, {}).setdefault(c, 0)
        table[layer][c] += 1
    agree = [r["agree"] for r in rows.values() if "agree" in r]
    rows["summary"] = {"supported": int(all(agree))}
    for layer, t in sorted(table.items()):
        print(layer, t)
    print("一致:", f"{sum(agree)}/{len(agree)}",
          "否定の辺なし:", f"{sum(r['agree_pos'] for r in rows.values() if 'agree_pos' in r)}/{len(agree)}")
    (OUT / "sys_layers.json").write_text(json.dumps(
        {"_source": "exp/experiments/sys_layers.py", "_commit": commit, "rows": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("判定:", "支持" if all(agree) else "反証")


if __name__ == "__main__":
    main()
