"""E33: h_round_trip_raises_sibling を確かめる。抽象と具体の往復で教えると、兄弟概念の弁別が上がるか。

仮説（exp.yaml）: v_refer(h, v_raise(teacher_round_trip, sibling_discrimination))。登録 #638（issue #639）。
  teacher_round_trip: 適用で出た判定に依って直す定義文と適用例（round_trip_material）を教師にする。
  比べる相手は teacher_both（定義文の暗唱と適用例を、毎回同時に混ぜる）。

仕組み（E3 と同じ。e3_concept_vectors の Injector と label_mask を使う）:
  モデル Qwen/Qwen2.5-1.5B-Instruct、層 8、本体の重みは固定。概念ごとに 1 本のベクトルを持ち、
  入力の中でその概念の語が現れたトークン位置で、層の出力に加える。初期値はゼロ。Adam、lr 0.1。
  E3 と違うところ: 兄弟の 2 概念のベクトルを、組ごとに一緒に学習する（設問に両方の語が出るため）。

材料（このファイルに書いた。手で作った。12 組 24 概念）:
  組 1〜4 は concepts_ja.json の G3 の 4 組（定義はそこから読む）、組 5〜12 は新しく作った組（下の NEW_DEFS）。
  教える設問（TRAIN）: 組ごとに 4 問の穴埋め二択（各概念が正答の問いが 2 つずつ）。評価には使わない。
  評価の設問（EVAL）: 組ごとに 4 問。組 1〜4 は G3 の 2 問ずつに、新しく作った 2 問ずつを足す。
  行: 暗唱の行は、概念ごとに E3 の 3 つの問いの型と定義文（6 行/組）。設問の行は、設問ごとに選択肢の順の 2 通り（8 行/組）。

条件（予算は最適化の段数で、どれも 24 段にそろえる）:
  none:  学習しない（ベクトルはゼロ）。
  both:  毎段、暗唱の 6 行と設問の 8 行（teacher_both）。
  round: 4 回の往復。1 回の往復は、抽象の 3 段と具体の 3 段。
    抽象の段の材料: その時点の判定で誤った設問の、正答の概念の暗唱の行（取り違えられた側の定義を直す）。
      1 回目は判定がまだないので、両方の概念。誤りがなければ両方の概念。
    具体の段の材料: 抽象の段の後に、教える設問を今のベクトルで判定し、誤った設問（どちらかの順で余裕 <= 0）の 2 行。
      誤りがなければ 8 行すべて。
    判定は抽象の段の前（2 回目以降）と具体の段の前に行う（勾配は取らない）。
  開示: 段数をそろえたので、both は 1 段あたりの行が最も多く、round は少ない。計算量は both に有利。
  定義文だけ・適用例だけの条件は、判定に使わず、時間（both の 1 段が CPU で約 18 秒）がかかるので置かない。

評価: 評価の設問 48 問を、組のベクトル 2 本を入れて解かせる（E3 の vec と同じ。定義文は文脈に置かない）。
  余裕（margin）は、選択肢の順の 2 通りの平均。acc は余裕 > 0 の割合、acc_both は両方の順で正しい割合。
行（e33_round_trip_sibling.json）: 組ごと・条件ごとの損失の最初と最後、round の判定の誤りの数の推移、
  設問ごとの margin と both。s: 条件ごとの acc, acc_both, mean_margin。

判定（事前に決める。主の指標は acc_both）:
  外れ（状態を変えない）: both の acc_both が none の acc_both を上回らない（教えても効かず、比べられない）。
  支持: acc_both(round) - acc_both(both) >= 0.10 かつ mean_margin(round) > mean_margin(both)。
  反証: acc_both(round) <= acc_both(both)。
  mixed: それ以外。
開示: 評価の 48 問は少なく、0.10 は 5 問に当たる。乱数は使わない（初期値ゼロ、順は固定）ので、繰り返しの幅は測れない。
  新しい組の語（丙・丁、子・丑など）は、意味の手がかりにならないように選んだが、偏りは確かめていない。
  走らせる前に、数は計算していない。
再開（走らせ始めた後に足した。手順と判定は変えていない）:
  この環境のコンテナは再起動するので、組と条件ごとに、そこまでの行を e33_round_trip_sibling.partial.json に書く。
  走らせ直すと、書いてある組と条件を飛ばして続ける。乱数を使わないので、飛ばしても値は同じ。
  最初の起動は組 2 の途中で止め、この仕組みを足して走らせ直した（止めた時点で組 1 の 3 条件の結果を見ている）。
使い方:
  python exp/experiments/e33_round_trip_sibling.py
"""
import json
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from e1_context_injection import ROOT, Runner, question_text  # noqa: E402
from e3_concept_vectors import TEMPLATES, Injector, label_mask  # noqa: E402

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LAYER = 8
LR = 0.1
STEPS = 24
CYCLES = 4
HALF = 3
BUDGET = 1024

PAIRS = [
    ("甲種注文", "乙種注文"), ("A変更", "B変更"), ("一類利用者", "二類利用者"), ("赤納品", "青納品"),
    ("丙票", "丁票"), ("東案件", "西案件"), ("松返品", "竹返品"), ("第一保留", "第二保留"),
    ("梅会員", "桜会員"), ("子障害", "丑障害"), ("寅申請", "卯申請"), ("辰出荷", "巳出荷"),
]
NEW_DEFS = {
    "丙票": "丙票：票のうち、社内だけで回覧するもの。",
    "丁票": "丁票：票のうち、社外の取引先にも送るもの。",
    "東案件": "東案件：案件のうち、期日が今月中のもの。",
    "西案件": "西案件：案件のうち、期日が来月以降のもの。",
    "松返品": "松返品：返品のうち、商品に欠陥があったもの。",
    "竹返品": "竹返品：返品のうち、商品に欠陥がなく、顧客の都合によるもの。",
    "第一保留": "第一保留：保留のうち、顧客の返答を待っているもの。",
    "第二保留": "第二保留：保留のうち、社内の確認を待っているもの。",
    "梅会員": "梅会員：会員のうち、年会費を一括で前払いしたもの。",
    "桜会員": "桜会員：会員のうち、会費を毎月払っているもの。",
    "子障害": "子障害：障害のうち、利用者に影響が出たもの。",
    "丑障害": "丑障害：障害のうち、利用者に影響が出ていないもの。",
    "寅申請": "寅申請：申請のうち、必要な書類がすべてそろっているもの。",
    "卯申請": "卯申請：申請のうち、必要な書類の一部が欠けているもの。",
    "辰出荷": "辰出荷：出荷のうち、国内に送るもの。",
    "巳出荷": "巳出荷：出荷のうち、海外に送るもの。",
}
TRAIN = {
    0: [("代金の入金が確かめられ、倉庫で商品も確保された注文は、＿＿である。", 1),
        ("支払いの確認も在庫の確保もまだの注文は、＿＿である。", 0),
        ("振込が確認でき、出荷用の在庫もすでに押さえた注文は、＿＿である。", 1),
        ("入金を待っていて、在庫もまだ割り当てていない注文は、＿＿である。", 0)],
    1: [("課長の決裁がなければ始められない変更は、＿＿である。", 1),
        ("担当者が自分の判断だけで行える変更は、＿＿である。", 0),
        ("上司の許可を取ってから着手する変更は、＿＿である。", 1),
        ("誰にも承認を求めずに進めてよい変更は、＿＿である。", 0)],
    2: [("年間の有料契約を結び、代金を払っている人は、＿＿である。", 1),
        ("アカウントを作っただけで、お金は払っていない人は、＿＿である。", 0),
        ("有料の会員契約をして、毎年料金を納めている人は、＿＿である。", 1),
        ("無料で登録だけをして使っている人は、＿＿である。", 0)],
    3: [("50個の注文のうち、20個だけを先に届けた。これは＿＿である。", 1),
        ("30個の注文に対して、30個をそろえて届けた。これは＿＿である。", 0),
        ("注文の半分だけを今回届け、残りは来週になる。これは＿＿である。", 1),
        ("注文された数をすべて一回で届けた。これは＿＿である。", 0)],
    4: [("部署の中だけで回して読む票は、＿＿である。", 0),
        ("取引先の担当者にも送付する票は、＿＿である。", 1),
        ("社員だけが見る、外に出さない票は、＿＿である。", 0),
        ("協力会社にも写しを届ける票は、＿＿である。", 1)],
    5: [("締め切りが今月の末日である案件は、＿＿である。", 0),
        ("期日が再来月に設定された案件は、＿＿である。", 1),
        ("今月の15日までに終える案件は、＿＿である。", 0),
        ("期日が来月の初めの案件は、＿＿である。", 1)],
    6: [("届いた商品が壊れていたので返した。これは＿＿である。", 0),
        ("色が好みでなかったので、未使用のまま返した。これは＿＿である。", 1),
        ("動作しない不良品だったので返した。これは＿＿である。", 0),
        ("サイズを間違えて注文したので返した。これは＿＿である。", 1)],
    7: [("お客様からの回答を待って止めている保留は、＿＿である。", 0),
        ("法務部のチェックが終わるのを待っている保留は、＿＿である。", 1),
        ("顧客に質問を送り、その返事待ちの保留は、＿＿である。", 0),
        ("社内の上長の確認待ちで止まっている保留は、＿＿である。", 1)],
    8: [("一年分の会費を最初にまとめて払った会員は、＿＿である。", 0),
        ("会費を月ごとに払っている会員は、＿＿である。", 1),
        ("入会時に年会費を全額前払いした会員は、＿＿である。", 0),
        ("毎月の引き落としで会費を納める会員は、＿＿である。", 1)],
    9: [("利用者がログインできなくなった障害は、＿＿である。", 0),
        ("予備のサーバーが止まったが、利用者は何も困らなかった障害は、＿＿である。", 1),
        ("画面が表示されず、利用者から問い合わせが来た障害は、＿＿である。", 0),
        ("社内の監視だけが気づき、利用者には何も起きなかった障害は、＿＿である。", 1)],
    10: [("必要な書類がすべて添付された申請は、＿＿である。", 0),
         ("住民票が足りず、書類がそろっていない申請は、＿＿である。", 1),
         ("求められた書類が一つ残らず出ている申請は、＿＿である。", 0),
         ("添付すべき証明書の一部が抜けている申請は、＿＿である。", 1)],
    11: [("大阪の取引先に送る出荷は、＿＿である。", 0),
         ("アメリカの顧客に送る出荷は、＿＿である。", 1),
         ("国内の店舗へ届ける出荷は、＿＿である。", 0),
         ("船便で海外へ送る出荷は、＿＿である。", 1)],
}
EVAL_NEW = {
    0: [("クレジットの決済が通り、在庫の引き当ても終わった注文は、＿＿である。", 1),
        ("受け付けたばかりで、決済も在庫の手配も済んでいない注文は、＿＿である。", 0)],
    1: [("事前に上長の承認印が要る設定の変更は、＿＿である。", 1),
        ("承認の手続きなしで現場がその場で直せる変更は、＿＿である。", 0)],
    2: [("法人として有料契約を結び、請求どおりに支払っている人は、＿＿である。", 1),
        ("会員登録を終えたが、課金はしていない人は、＿＿である。", 0)],
    3: [("200箱の注文に対して、今日は150箱を届けた。これは＿＿である。", 1),
        ("10台の注文に対して、10台すべてを納めた。これは＿＿である。", 0)],
    4: [("社内の掲示板にだけ回覧する票は、＿＿である。", 0),
        ("仕入れ先にもメールで送る票は、＿＿である。", 1),
        ("経理部と営業部の間だけで回す票は、＿＿である。", 0),
        ("外部の取引相手にも渡す票は、＿＿である。", 1)],
    5: [("期日が今月の20日の案件は、＿＿である。", 0),
        ("期日が半年先の案件は、＿＿である。", 1),
        ("期日が今月の10日の案件は、＿＿である。", 0),
        ("期日が来月の末の案件は、＿＿である。", 1)],
    6: [("製造時の傷が見つかったので返した。これは＿＿である。", 0),
        ("気が変わって、要らなくなったので返した。これは＿＿である。", 1),
        ("部品が欠けていたので返した。これは＿＿である。", 0),
        ("同じものを二重に買ってしまったので返した。これは＿＿である。", 1)],
    7: [("顧客が見積もりを検討中で、返事がまだの保留は、＿＿である。", 0),
        ("経理部の確認が済むまで止めている保留は、＿＿である。", 1),
        ("依頼主からの返信を待っている保留は、＿＿である。", 0),
        ("自社の技術部門の確認を待つ保留は、＿＿である。", 1)],
    8: [("年会費を一度に前納した会員は、＿＿である。", 0),
        ("月々の分割で会費を払う会員は、＿＿である。", 1),
        ("12か月分をまとめて先に払った会員は、＿＿である。", 0),
        ("毎月末に一か月分ずつ払う会員は、＿＿である。", 1)],
    9: [("決済ができず、利用者が買い物できなかった障害は、＿＿である。", 0),
        ("夜間の集計が遅れたが、利用者には見えなかった障害は、＿＿である。", 1),
        ("利用者のデータが一時的に見えなくなった障害は、＿＿である。", 0),
        ("冗長化された装置の片方が壊れたが、サービスは続いた障害は、＿＿である。", 1)],
    10: [("書類に不足がなく、全部そろった申請は、＿＿である。", 0),
         ("印鑑証明が未提出の申請は、＿＿である。", 1),
         ("提出書類が完全な申請は、＿＿である。", 0),
         ("必要な書類のうち二つがまだ出ていない申請は、＿＿である。", 1)],
    11: [("札幌の倉庫へ送る出荷は、＿＿である。", 0),
         ("ドイツの代理店に送る出荷は、＿＿である。", 1),
         ("東京都内の顧客へ届ける出荷は、＿＿である。", 0),
         ("台湾の工場へ送る出荷は、＿＿である。", 1)],
}
CONDS = ["none", "both", "round"]


def item(q, k, pair):
    return {"type": "fill", "q": q, "correct": pair[k], "wrong": pair[1 - k]}


class PairTrainer:
    def __init__(self, r, inj, pair, defs, train_items):
        self.r, self.inj, self.pair = r, inj, pair
        self.d = r.model.config.hidden_size
        self.rows = {}
        for c in pair:
            for j, t in enumerate(TEMPLATES):
                self.rows[("def", c, j)] = self._row(r.render(None, t.format(L=c)), defs[c] + r.tok.eos_token)
        for i, it in enumerate(train_items):
            for swap in (False, True):
                body, no = question_text(it, swap)
                self.rows[("qa", i, swap)] = self._row(r.render(None, body), str(no))
        self.train_items = train_items

    def _row(self, prompt, cont):
        full = prompt + cont
        n_prompt = len(self.r.tok(prompt, add_special_tokens=False).input_ids)
        ids = self.r.tok(full, add_special_tokens=False).input_ids
        masks = [label_mask(self.r.tok, full, c)[1] for c in self.pair]
        return ids, n_prompt, masks

    def delta(self, masks, V, width):
        out = torch.zeros(1, width, self.d)
        for m, v in zip(masks, V):
            mm = torch.tensor(m + [False] * (width - len(m)), dtype=torch.float32).view(1, -1, 1)
            out = out + mm * v.view(1, 1, -1)
        return out

    def step(self, V, opt, keys):
        rows = [self.rows[k] for k in keys]
        n = len(rows)
        order = sorted(range(n), key=lambda i: len(rows[i][0]))
        groups, cur = [], []
        for i in order:
            if cur and (len(cur) + 1) * len(rows[i][0]) > BUDGET:
                groups.append(cur)
                cur = []
            cur.append(i)
        groups.append(cur)
        pad = self.r.tok.pad_token_id if self.r.tok.pad_token_id is not None else self.r.tok.eos_token_id
        opt.zero_grad()
        total = 0.0
        for g in groups:
            w = max(len(rows[i][0]) for i in g)
            ids = torch.full((len(g), w), pad)
            att = torch.zeros((len(g), w), dtype=torch.long)
            lab = torch.full((len(g), w), -100)
            deltas = []
            for b, i in enumerate(g):
                rid, n_prompt, masks = rows[i]
                k = len(rid)
                ids[b, :k] = torch.tensor(rid)
                att[b, :k] = 1
                lab[b, n_prompt:k] = torch.tensor(rid[n_prompt:])
                deltas.append(self.delta(masks, V, w))
            self.inj.delta = torch.cat(deltas, 0)
            logits = self.r.model(ids, attention_mask=att).logits
            per_tok = torch.nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, logits.shape[-1]), lab[:, 1:].reshape(-1), reduction="none"
            ).view(len(g), -1)
            valid = (lab[:, 1:] != -100).float()
            loss = ((per_tok * valid).sum(1) / valid.sum(1)).sum() / n
            loss.backward()
            total += loss.item()
        self.inj.delta = None
        opt.step()
        return total

    @torch.no_grad()
    def margin(self, it, V):
        ms = []
        for swap in (False, True):
            body, no = question_text(it, swap)
            text = self.r.render(None, body)
            ids = self.r.tok(text, add_special_tokens=False).input_ids
            masks = [label_mask(self.r.tok, text, c)[1] for c in self.pair]
            self.inj.delta = self.delta(masks, V, len(ids))
            last = self.r.model(torch.tensor([ids])).logits[0, -1]
            self.inj.delta = None
            l1, l2 = last[self.r.id1].item(), last[self.r.id2].item()
            ms.append((l1 - l2) if no == 1 else (l2 - l1))
        return ms

    def wrong(self, V):
        return [i for i, it in enumerate(self.train_items) if min(self.margin(it, V)) <= 0]

    def def_keys(self, concepts):
        return [("def", c, j) for c in concepts for j in range(len(TEMPLATES))]

    def qa_keys(self, idx):
        return [("qa", i, s) for i in idx for s in (False, True)]

    def train(self, cond):
        V = [torch.zeros(self.d, requires_grad=True) for _ in self.pair]
        log = {"losses": [], "wrong": []}
        if cond == "none":
            return [v.detach() for v in V], log
        opt = torch.optim.Adam(V, lr=LR)
        all_qa = list(range(len(self.train_items)))
        if cond == "both":
            keys = self.def_keys(self.pair) + self.qa_keys(all_qa)
            for _ in range(STEPS):
                log["losses"].append(self.step(V, opt, keys))
            return [v.detach() for v in V], log
        focus = list(self.pair)
        for cyc in range(CYCLES):
            if cyc > 0:
                w = self.wrong(V)
                log["wrong"].append(len(w))
                fc = [c for c in self.pair if any(c == self.train_items[i]["correct"] for i in w)]
                focus = fc or list(self.pair)
            for _ in range(HALF):
                log["losses"].append(self.step(V, opt, self.def_keys(focus)))
            w = self.wrong(V)
            log["wrong"].append(len(w))
            for _ in range(HALF):
                log["losses"].append(self.step(V, opt, self.qa_keys(w or all_qa)))
        log["wrong"].append(len(self.wrong(V)))
        return [v.detach() for v in V], log


def main():
    data = json.loads((ROOT / "data" / "concepts_ja.json").read_text(encoding="utf-8"))
    defs = dict(data["defs"])
    defs.update(NEW_DEFS)
    g3 = [it for it in data["items"] if it["group"] == "G3"]
    r = Runner(MODEL)
    for p in r.model.parameters():
        p.requires_grad_(False)
    inj = Injector(r.model, LAYER)
    part = HERE / "results" / "e33_round_trip_sibling.partial.json"
    rows = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {}
    for pi, pair in enumerate(PAIRS):
        train_items = [item(q, k, pair) for q, k in TRAIN[pi]]
        eval_items = [it for it in g3 if set(it["defs"]) == set(pair)]
        eval_items = [{"type": it["type"], "q": it["q"], "correct": it["correct"], "wrong": it["wrong"], "id": it["id"]}
                      for it in eval_items]
        eval_items += [dict(item(q, k, pair), id=f"P{pi + 1:02d}-{j + 1}") for j, (q, k) in enumerate(EVAL_NEW[pi])]
        assert len(eval_items) == 4, (pair, len(eval_items))
        pk = f"P{pi + 1:02d}"
        row = rows.setdefault(pk, {"pair": list(pair)})
        if all(c in row for c in CONDS):
            continue
        pt = PairTrainer(r, inj, pair, defs, train_items)
        for cond in CONDS:
            if cond in row:
                continue
            t0 = time.time()
            V, log = pt.train(cond)
            res = {}
            for it in eval_items:
                ms = pt.margin(it, V)
                res[it["id"]] = {"margin": sum(ms) / 2, "both": all(m > 0 for m in ms)}
            row[cond] = {"loss_first": log["losses"][0] if log["losses"] else None,
                         "loss_last": log["losses"][-1] if log["losses"] else None,
                         "wrong": log["wrong"], "items": res}
            print(f"[{pi + 1:02d} {pair[0]}/{pair[1]}] {cond}: "
                  f"acc_both={sum(x['both'] for x in res.values())}/4 wrong={log['wrong']} {time.time() - t0:.0f}s",
                  flush=True)
            part.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    s = {}
    for cond in CONDS:
        xs = [x for row in rows.values() for x in row[cond]["items"].values()]
        s[cond] = {"n": len(xs), "acc": sum(x["margin"] > 0 for x in xs) / len(xs),
                   "acc_both": sum(x["both"] for x in xs) / len(xs),
                   "mean_margin": sum(x["margin"] for x in xs) / len(xs)}
    out = HERE / "results" / "e33_round_trip_sibling.json"
    out.write_text(json.dumps({"model": MODEL, "layer": LAYER, "steps": STEPS, "rows": rows, "s": s},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    part.unlink()
    print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
