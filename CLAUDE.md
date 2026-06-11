# CLAUDE.md

このリポジトリで作業する際の入口メモ。**設計・仕様の正は [`docs/`](docs/README.md) 配下**。
まず [`docs/README.md`](docs/README.md)（ドキュメント目次）を読むこと。

このリポは **設計ドキュメント先行**で立ち上げてある。コードはまだ無い／薄い。
実装するときは docs に従い、docs と食い違ったら docs を直してから実装すること（docs が正）。

## このサービスは何か（1行）

画像を投げると `left` / `right` の向きを返す、汎用の左右向き判定マイクロサービス。
埋め込み（DINOv2）+ k-NN で、ラベルを足すほど賢くなる（human-in-the-loop）。

## 主要ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/README.md](docs/README.md) | ドキュメント目次（ここが入口） |
| [docs/overview.md](docs/overview.md) | 目的・スコープ・用語（left/right の定義） |
| [docs/architecture.md](docs/architecture.md) | スタック・ディレクトリ・データフロー |
| [docs/api.md](docs/api.md) | HTTP API 仕様（predict / label / projects / admin / healthz） |
| [docs/model.md](docs/model.md) | 判定モデル（DINOv2 埋め込み + k-NN + flip 拡張 + confidence） |
| [docs/database.md](docs/database.md) | SQLite スキーマ・永続化 |
| [docs/multi-tenant.md](docs/multi-tenant.md) | project キーによるテナント分離・API キー |
| [docs/admin.md](docs/admin.md) | admin UI・運用（アクティブラーニング） |
| [docs/security.md](docs/security.md) | 認証・untrusted input・画像の扱い |
| [docs/env.md](docs/env.md) | 環境変数一覧 |
| [docs/client-integration.md](docs/client-integration.md) | クライアント連携（ai-kyoto-osaka の例） |
| [docs/roadmap.md](docs/roadmap.md) | 実装ステップ |

## 押さえておくべき要点

- **CNN を丸ごと fine-tune しない**。重い・GPU前提になる・即時反映できない。
  採るのは「DINOv2 で埋め込み → k-NN で近傍多数決」。学習＝近傍集合に1件足すだけ。
  （理由と代替案の検討は [docs/model.md](docs/model.md)）
- **flip 拡張は label 保存時だけ**。ラベル画像は水平反転して逆ラベルでも登録する（データ倍増・左右対称化）。
  **predict のクエリ画像は反転しない**（そのままの向きを判定したいので）。
- **project でラベル空間を必ず分ける**。グローバルに混ぜない（[docs/multi-tenant.md](docs/multi-tenant.md)）。
- **判定はこのサービスの責務だけ**。LLM は呼ばない。外部に副作用を持たない（画像→ラベルの純関数的サービス）。
- **永続物は `/data` ボリューム**（SQLite・画像・埋め込み）。デプロイで消えてはならない。

## 作業上の注意（ファイル破壊・事故防止）

- Read とその結果に依存する Write/Edit を同じ並列バッチに入れない。巨大な並列ツールバッチを組まない。
- 既存ファイルの書き換えは Write（全置換）ではなく Edit（差分）。書き換え前に必ず最新を Read する。
- ビルド・テスト等の出力は `cmd > /tmp/x 2>&1; echo "rc=$?"` でファイルに逃がして Read で確認してから「完了」と言う。
