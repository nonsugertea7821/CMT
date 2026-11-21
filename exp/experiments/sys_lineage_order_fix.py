"""sys_lineage_order の訂正: 鍵の改名の commit（de07f15）の行を除いて数え直す。

sys_lineage_order.json を読むだけで、履歴は読み直さない。n_noun・n_verb は元の量をそのまま使う。
s: n_ev_noun, n_ev_verb, n_led_noun, n_led_verb, rate_noun, rate_verb, led_share_noun（元と同じ定義）。
使い方:
  python exp/experiments/sys_lineage_order_fix.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve()
DROP = ("de07f15",)


def main():
    res = HERE.parents[2] / "exp/experiments/results"
    d = json.loads((res / "sys_lineage_order.json").read_text(encoding="utf-8"))
    s0 = d["s"]
    ev = [r for r in d["rows"].values() if r["commit"] not in DROP]
    n = lambda k, led=False: sum(r["kind"] == k and (r["own_led"] or not led) for r in ev)
    s = {"n_ev_noun": n("noun"), "n_ev_verb": n("verb"), "n_led_noun": n("noun", True), "n_led_verb": n("verb", True)}
    s |= {"rate_noun": s["n_ev_noun"] / s0["n_noun"], "rate_verb": s["n_ev_verb"] / s0["n_verb"],
          "led_share_noun": (s["n_led_noun"] / s["n_ev_noun"]) if s["n_ev_noun"] else 0.0}
    rows = {"dropped": {"commits": list(DROP), "n": len(d["rows"]) - len(ev)}}
    (res / "sys_lineage_order_fix.json").write_text(json.dumps({"rows": rows, "s": s}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
