# bootstrap（stage0）

CSCL の最初の実装（Python）。型の規則の大半は `cscl/library/core/ontology.yaml` に CSCL 自身で書いてあり、
ここにあるのは、それを読んで当てはめる評価器と、まだ規則で書けない法則（law_given）。

- `type_checker/` 型検査器（旧 tools/check_spec.py）と、1行の検査（check_line.py）
- `runtime/` 実行の検査（旧 tools/run_spec.py）
- `render/` 表示への変換（旧 tools/render_expr.py）

将来、CSCL が自分の実装を自分の概念として書けるようになれば（セルフホスト）、
信頼の基点は、この stage0 ではなく、その前の版になる。
