# CMT — Conceptual Model Training

**定義を、文ではなく型の付いた式で書く。** 言語モデルに語の意味を与え直す研究で、その定義・主張・仮説を、すべて検査できる式として置いている実験的なリポジトリ。

*An experimental research repository on redefining concepts for language models. Every definition, claim and hypothesis is a typed formula; natural-language text is derived from it, and each hypothesis is pre-registered and checked by machine.*

[仮説の一覧](https://github.com/nonsugertea7821/CMT/issues?q=label%3Ahypothesis) ·
[未検証](https://github.com/nonsugertea7821/CMT/issues?q=is%3Aopen+label%3Auntested) ·
[支持](https://github.com/nonsugertea7821/CMT/issues?q=label%3Asupported) ·
[反証](https://github.com/nonsugertea7821/CMT/issues?q=label%3Arefuted) ·
[決定の一覧](https://github.com/nonsugertea7821/CMT/issues?q=label%3Adecision) ·
[作業の取り決め](CLAUDE.md)

## なぜ式で書くのか

- **食い違いが検査で出る。** 定義は型検査器が読む。二つの定義が矛盾すれば、読み手の解釈の違いとしてではなく、検査の誤りとして出る。
- **文は導かれる。** 日本語の文は式から訳したもので、正本ではない。文を直したいときは式を直す。訳した文が元の式に一つで読み戻せることも、仮説として確かめている。
- **主張に履歴がある。** 仮説は、確かめる前に手順と判定を登録し、測った結果と照らして状態が決まる。支持だけでなく、反証も取り下げも消さずに残す。

## 採用した決定

いま体系が「採用」として置いている決定。どれも式が正本で、左の文は式から訳したもの。

<!-- generated:begin -->
_この節は体系から生成している。手で編集しない（`.github/scripts/build_readme.py`）。_

**実験**

| 文（式から訳したもの） | 式 |
|---|---|
| 本設計が再定義の成功を上げる | `{is: v_raise, from: this_design, to: redefinition_success}` |
| 使い方をまたぐ一貫性が再定義の成功を測る | `{is: v_measure, from: cross_usage_consistency, to: redefinition_success}` |
| 他の記述が依存する記述が型付きグラフの部分になる | `{is: v_compose, from: depended_information, to: typed_graph}` |
| テストは適用例の一種である | `{is: is_a, from: test, to: application_example}` |
| 他の記述が依存する記述が概念体系制御言語で書かれる | `{is: v_express, from: depended_information, to: cscl}` |
| 自然言語に変換した文が他の記述が依存する記述に頼る | `{is: v_rely, from: rendered_text, to: depended_information}` |
| 概念ベクトルが重みが公開されたモデルに頼る | `{is: v_rely, from: concept_vector, to: open_weight_model}` |
| APIでしか使えないモデルが文章での注入に頼る | `{is: v_rely, from: api_only_model, to: text_injection}` |

**言語**

| 文（式から訳したもの） | 式 |
|---|---|
| 規則で書いた法則が概念体系制御言語で書かれる | `{is: v_express, from: law_rule, to: cscl}` |
| runtimeが閉世界（書かれていない文は偽）の前提として置くと述べる | `{is: v_presume, from: runtime, to: closed_world}` |
| 標準の語彙の層が公理の層を依存する | `{is: v_depend, from: std_layer, to: axiom_layer}` |
| 表示語が体系を依存する | `{is: v_depend, from: display, to: system}` |
| 依存されるものは持続体の一種である | `{is: is_a, from: depended, to: continuant}` |
| 状態の関係が基礎の節の部分になる | `{is: v_compose, from: state_relation, to: base}` |
| 定義の循環が否定（示されていない文を述べる文）に依存しない | `{is: v_not_depend, from: definition_cycle, to: not}` |
<!-- generated:end -->

## 仮説の流れ

1. 仮説を、未検証のまま体系に登録する。main に入ると issue が立つ。
2. 仮説ごとに枝を切り、最初の commit で手順と判定を登録する（事前登録）。
3. 測った結果を観察として体系に書き、仮説を「支持」か「反証」で結ぶ。照合は検査器（ec）が行う。
4. 状態が変わると、issue のラベルが変わり、閉じる。前提が崩れた仮説は「取り下げ」として残す。

数と状態は変わるので、ここには写さない。いまの状態は、上の issue のラベルで見る。

## 構成

| 場所 | 中身 |
|---|---|
| `cscl.yaml` | 体系の入口（どのファイルを読むか） |
| `cscl/library/` | 言語の層（シグネチャ・存在論・文法・実行・標準の語彙） |
| `cscl/design/` | 言語についての仮説と決定 |
| `exp/src/` | 実験についての仮説・決定・測定の族 |
| `exp/experiments/` | 実験のスクリプトと結果 |
| `cscl/bootstrap/` | 最初の実装（型検査器・実行の検査・表示への変換） |
| `.github/scripts/` | issue への同期、自動マージの判定、この README の生成 |

## 手元で検査する

```sh
pip install pyyaml
python cscl/bootstrap/type_checker/type_checker.py   # 型検査（tc）
python exp/src/exp_check.py                          # 仮説の状態と根拠の照合（ec）
python .github/scripts/build_readme.py --check       # この README の生成する部分が体系と合うか
```

## セッションの記録（規定では無効）

`.claude/settings.json` は、Claude Code の Stop フック `.claude/hooks/session_log.sh` を登録している。
このフックは、セッションの発言を取り出してブランチ `claude/session-log-<ユーザー名>` に足し、push する。

**規定では何もしない。** clone した人のセッションは、何も設定しなければ記録されない。
記録するのは、次の両方が成り立つときだけ:

1. 持ち主が自分で有効にしている:
   - 環境変数 `CMT_SESSION_LOG_OWNER=<GitHub のユーザー名>`、または
   - `git config cmt.sessionLogOwner <GitHub のユーザー名>`（`.git/config` に書く。commit されず、clone にも渡らない）
2. そのユーザー名が、`origin` の持ち主と同じ。

記録の前に、メールアドレス・電話番号・鍵らしい文字列などは伏せる。個人の情報を指すかもしれない利用者の発言は、書かずに保留する。
規則は記録のブランチの `claude_session_log/build.py` にある。

フックを使いたくない人は、`.claude/settings.local.json` で無効にするか、フックの設定を消してよい。

## ライセンス

[MIT](LICENSE)
