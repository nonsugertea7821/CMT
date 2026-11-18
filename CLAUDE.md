# このリポジトリで作業するときの取り決め

## 提案
- 「やったほうがいい」と考えたことは、伝える前に、未検証の仮説として体系に登録する。
  - 仮説は `cscl/design/claims.yaml`（言語について）か `exp/src/exp.yaml`（実験について）に置く: `h_<名前>: {is: exp.hyp_untested}`。
  - 中身は `v_refer` で書く: `{is: v_refer, from: h_<名前>, to: {...}}`。
  - 確かめる残り項目を対で置く: `b_<名前>: {is: exp.item_queued}` と `{is: exp.v_check, from: b_<名前>, to: h_<名前>}`。
  - 仮説は main に入ると issue に写る（`.github/scripts/sync_issues.py`）。残り項目そのものは写らない。

## 仮説を確かめる流れ
1. 仮説が main に入り、issue が立つ。
2. 仮説ごとにブランチ `claude/h_<仮説名>` を切り、Draft の PR を立てる。本文で issue を参照する。最初の commit は事前登録（手順と判定）。
3. 測って、観察を体系に書き、仮説を `v_support` か `v_contradict` で結ぶ。解釈は commit のメッセージと PR の本文に書く。
4. ec が通り、状態が支持・反証・mixed のどれかになったら、Draft を外す（確認の合図。承認でもマージでもない）。外れて訂正し、未検証のまま残るなら Draft のまま。
5. 利用者が確認してマージする。Claude はマージしない。main への push で sync が状態を読み、issue を閉じる。
   - 例外: ワークフロー auto-merge（`.github/scripts/auto_merge.py`）は、条件を満たす PR を自動でマージする。
     条件は、範囲の内のファイルだけを触り、状態が未検証から支持か反証になり、事前登録が結果より前にあり、訂正がなく、tc と ec が通ること。
     訂正・mixed・評価器や文法の変更は手で見る。前提は仮説 `h_auto_merge_uncorrected`。
   - 自動マージに乗せるため、事前登録の commit はスクリプトだけを触り、結果ファイルは後の commit で足す。

## 体系のファイル（cscl.yaml, cscl/library, cscl/design, exp/src の yaml）
- コメントを足さない。定義に効く内容は式で書く。経緯と解釈は commit のメッセージと会話に書く。
  - `.claude/hooks/no_new_comments.py` が、ファイルを書いたときと `git commit` の前に検査する。
- 表示語（display）は、式から訳した名前。式にできていない意味の置き場として使うときは、そう自覚して使う。
- 名前で読んでよいのは、シグネチャと文法の語だけ。ほかの区別は式で書く。

## 実験（exp/experiments）
- 手順と判定は、実行の前に commit する（事前登録）。訂正は手順に書き足して開示する。表は観察から演繹する。
- 結果のファイル（`exp/experiments/results/`）とスクリプトは `git add -f` で足す。
- 記録済みの実験スクリプトを、確かめのためにもう一度走らせない（結果のファイルを上書きする）。確かめは tc
  （`cscl/bootstrap/type_checker/type_checker.py`）と ec（`exp/src/exp_check.py`）で行う。
- 仮説の状態（未検証・支持・反証）と根拠の照合は ec が行う。
- CI は GitHub に任せ、手元で回さない。

## git
- ファイルを戻すときは `git show HEAD:<path> > <path>` を使う。`git checkout` と `git stash` は使わない。
