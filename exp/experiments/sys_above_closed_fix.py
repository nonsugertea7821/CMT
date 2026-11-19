"""sys_above_closed の訂正: changed を、新しい法則の名を含む文を除いて数え直す（手順は sys_above_closed.py の「訂正」）。

before の側は、手順の登録の commit（577cbcc）の syntax.yaml を写しに置いて閉じた事実を作り、after の側は作業木で作る。
どちらも新しい法則を除いた規則で閉じ、新しい法則の名を含む文を除いて、関係ごとに比べる。

使い方:
  python exp/experiments/sys_above_closed_fix.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exp/experiments/results"
BASE_REV = "577cbcc"
DIGEST = """
import contextlib, hashlib, io, json, sys
sys.path.insert(0, "cscl/bootstrap/type_checker")
with contextlib.redirect_stdout(io.StringIO()):
    import type_checker as tc
    T, O, _ = tc.build()
LAWS = %r
new = set(LAWS) | {"syntax." + x for x in LAWS}
rules = [(l, x) for l, x in tc.law_rules(O) if l not in new]
F = tc.Facts(T.syntax_facts())
tc.evaluate(rules, F, tc.variables(O))
out = {}
for r, xs in F.by.items():
    keep = sorted(str(x) for x in xs if not any(n in str(a) for a in x for n in LAWS))
    if keep:
        out[r] = [len(keep), hashlib.sha256("\\n".join(keep).encode()).hexdigest()[:16]]
print(json.dumps(out))
"""
LAWS = ["above_by_fact", "above_is_ancestor", "above_asymmetric", "above_transitive"]


def digest_in(d):
    out = subprocess.run([sys.executable, "-c", DIGEST % (LAWS,)], cwd=d, capture_output=True, text=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    with tempfile.TemporaryDirectory() as d:
        for p in ("cscl.yaml", "cscl", "exp/src"):
            src, dst = ROOT / p, Path(d) / p
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
        old_syntax = subprocess.run(["git", "show", f"{BASE_REV}:cscl/library/syntax/syntax.yaml"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout
        (Path(d) / "cscl/library/syntax/syntax.yaml").write_text(old_syntax, encoding="utf-8")
        before = digest_in(d)
    after = digest_in(ROOT)
    diff = sorted(r for r in set(before) | set(after) if before.get(r) != after.get(r))
    rows = {"summary 要約": {"changed_fixed": len(diff)}} | {f"changed {r}": {"before": before.get(r), "after": after.get(r)} for r in diff}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "sys_above_closed_after_fix.json").write_text(json.dumps({"rev": rev, "rows": rows}, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
