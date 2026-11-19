"""sys_above_individual の訂正（開示）: 写しに exp/experiments/results を入れていなかったため、exp の検査が結果ファイルを
見つけられず、before でも ec_errors 1673 が出た（sys_above_individual.json、判定「外れ」）。測りの欠けで、変種の差ではない。

訂正: 写しに exp/experiments/results も入れて、同じ 3 変種（before・A・B）を測り直す。手順・判定・変種の書き換えは
sys_above_individual.py のまま（そこから読み込む）。あわせて、before とハッシュが違う関係の名（changed の中身）を行に書く。
元の結果ファイルは上書きしない。出力は sys_above_individual_fix.json。

結果を見て分かっていること（開示）: 元の実行で、tc の errors は before 0・A 13623（すべて above_is_ancestor）・B 0。
  浅い・深い端の分類と違反の組の差は A・B とも 0。changed は A・B とも 3（中身は見ていない）。above_ind は 13623
  （始点が個体の above。個体は 13 でなく、体系のすべての個体）。

使い方:
  python exp/experiments/sys_above_individual_fix.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys_above_individual as m  # noqa: E402

ROOT = m.ROOT
OUT = ROOT / "exp/experiments/results/sys_above_individual_fix.json"
PROBE = m.PROBE.replace('"above_ind":', '"rel_names": sorted(rel), "above_ind":')


def variant(edits):
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src", "exp/experiments/results"):
            src, dst = ROOT / p, Path(d) / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        f = Path(d) / m.SYN
        s = f.read_text(encoding="utf-8")
        for old, new in edits:
            assert s.count(old) == 1, old
            s = s.replace(old, new)
        f.write_text(s, encoding="utf-8")
        out = subprocess.run([sys.executable, "-c", PROBE], cwd=d, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[-2000:]
        return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    A = [(m.NODE_ANCHOR, m.NODE_ANCHOR + m.NEW_NODES), (m.FACT_ANCHOR, m.FACT_ANCHOR + m.NEW_FACTS)] + m.REPL
    B = A + [(m.B_ANCHOR, m.B_ANCHOR + m.B_ADD)]
    res = {"before": variant([]), "A": variant(A), "B": variant(B)}
    b0 = res["before"]
    rows = {}
    for k, r in res.items():
        d = lambda key: len(set(r[key]) ^ set(b0[key]))
        ch = sorted(x for x in set(r["rel"]) | set(b0["rel"]) if r["rel"].get(x) != b0["rel"].get(x))
        rows[f"variant {k}"] = {"errors": r["errors"], "ec_errors": r["ec_errors"], "above_ind": r["above_ind"],
                                "n_shallow": len(r["shallow"]), "n_deep": len(r["deep"]), "n_V": len(r["V"]),
                                "shallow_diff": d("shallow"), "deep_diff": d("deep"), "V_diff": d("V"), "changed": len(ch)}
        rows[f"variant {k}"] |= {f"law_errors_{n}": c for n, c in sorted(r["laws"].items())}
        rows |= {f"changed {k} {x}": {"before": b0["rel"].get(x), "after": r["rel"].get(x)} for x in ch}
        rows |= {f"error {k} {i}": {"text": e} for i, e in enumerate(r["err_text"])}
    B_ = rows["variant B"]
    if B_["errors"] or B_["ec_errors"]:
        verdict = "外れ"
    elif B_["shallow_diff"] or B_["deep_diff"] or B_["V_diff"] or B_["changed"]:
        verdict = "反証"
    else:
        verdict = "支持"
    rows["summary 要約"] = {"verdict_support": int(verdict == "支持"), **{f"{k}_{x}": rows[f"variant {k}"][x]
                          for k in res for x in ("errors", "ec_errors", "above_ind", "shallow_diff", "deep_diff", "V_diff", "changed")}}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rows.items():
        if not k.startswith("error"):
            print(k, json.dumps(v, ensure_ascii=False))
    print("判定:", verdict)


if __name__ == "__main__":
    main()
