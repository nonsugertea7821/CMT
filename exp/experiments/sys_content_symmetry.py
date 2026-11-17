"""体系そのものを数える（5）。仮説 h_content_asymmetry_harmless（B）の確かめ: 定義の中身が真偽の対を欠くことは、欠陥と結びつかないか。

この手順は、結果を見る前に登録した（cscl/design/claims.yaml の h_content_asymmetry_harmless と b_content_asymmetry_harmless）。
単位・対・欠陥の基準は sys_soundness.py と同じ。違うのは、まだ調べていない期間を使うことと、ノードを名前だけで同定すること。

版
  C0  e845f0b  main の first-parent で、ノードの書き方がいまの形（extends、表示は display、原子は辞書）になった最初の版
  C1  6bfac2f  置き場が cscl/library/* に変わる版（48a43c9）の、first-parent の1つ前
  この期間（49 コミット）は、h_symmetry_soundness の確かめ（48a43c9 → 933ddd6）と重ならない。
  ファイルの置き場がこの期間に変わる（spec/ → cscl/library/, exp/src/）ので、ノードは名前（領域の接頭辞を外したもの）で同定する。
  C0 で同じ名前が2つ以上あるノードは、同定できないので数えない。
  読むファイル: spec/、cscl/library/、cscl/design/、exp/src/ の .yaml。trial・runs・notes・measurements は読まない。

判定（登録した基準）。この仮説は「結びつかない」を述べるので、反証だけがはっきり決まる
  反証      対の無いノードの書き換えの割合が、対のあるノードより大きく、片側 Fisher の正確検定で p < 0.05
  反証されない  それ以外。支持の観察として記録するが、差を見つけられなかったことであって、差がないことの証明ではない

結果ファイル sys_content_symmetry.json（列は sys_soundness.json と同じ。行 "test" に p_value）

使い方:
  python exp/experiments/sys_content_symmetry.py
"""
import json
from pathlib import Path

import yaml

import sys_soundness as S

C0, C1 = "e845f0b", "6bfac2f"
SKIPFILES = ("trial", "runs", "notes", "measurements")


def files(c):
    names = S.git("ls-tree", "-r", "--name-only", c).split()
    return [n for n in names if n.endswith(".yaml") and n.split("/")[0] in ("spec", "cscl", "exp")
            and (n.startswith("spec/") or n.startswith("cscl/library/") or n.startswith("cscl/design/") or n.startswith("exp/src/"))
            and not any(s in n for s in SKIPFILES)]


def nodes(c):
    out, seen = {}, {}
    for f in files(c):
        d = yaml.safe_load(S.git("show", f"{c}:{f}")) or {}
        for k, v in (d.get("nodes") or {}).items():
            if isinstance(v, dict):
                seen[k] = seen.get(k, 0) + 1
                out[("", k)] = S.strip(v)
    dup = {k for k, n in seen.items() if n > 1}
    out = {k: v for k, v in out.items() if k[1] not in dup}
    named = {k: {x: v[x] for x in ("of", "with", "neg", "at") if x in v} for (_, k), v in out.items() if "of" in v}
    for v in out.values():
        if "mod" in v:
            ms = v["mod"] if isinstance(v["mod"], list) else [v["mod"]]
            v["mod"] = [named.get(m, m) if isinstance(m, str) else m for m in ms]
    return out, dup


def main():
    (N0, dup), (N1, _) = nodes(C0), nodes(C1)
    S.C0, S.C1 = C0, C1
    S.nodes = lambda c: N0 if c == C0 else N1
    out = S.OUT / "sys_content_symmetry.json"
    real = S.OUT / "sys_soundness.json"
    keep = real.read_text(encoding="utf-8") if real.exists() else None
    S.main()
    data = json.loads(real.read_text(encoding="utf-8"))
    data["_source"] = "exp/experiments/sys_content_symmetry.py"
    data["_versions"] = {"C0": C0, "C1": C1}
    data["_duplicate_names_skipped"] = sorted(dup)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if keep is not None:
        real.write_text(keep, encoding="utf-8")
    print("同じ名前で数えなかったノード", len(dup))


if __name__ == "__main__":
    main()
