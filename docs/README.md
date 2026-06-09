# ドキュメント目次

設計・仕様の正はこの `docs/` 配下。概要はルートの [README.md](../README.md) を参照。

**このリポは設計ドキュメント先行**で立ち上げてある。実装は docs に従って起こすこと。
読む順番は上から下でよい（overview → architecture → api → model …）。

| ドキュメント | 内容 |
|---|---|
| [overview.md](overview.md) | 目的・スコープ・非スコープ・用語（left/right の定義） |
| [architecture.md](architecture.md) | 技術スタック・ディレクトリ構成・リクエストのデータフロー |
| [api.md](api.md) | HTTP API 仕様（predict / label / projects / admin / healthz・リクエスト/レスポンス例） |
| [usage.md](usage.md) | API 利用ガイド（呼ぶ側の how-to・curl/Python/TS 例・判定→確認修正→修正フロー） |
| [model.md](model.md) | 判定モデル（DINOv2 埋め込み・k-NN・flip 拡張・confidence・前処理・モデル検討） |
| [database.md](database.md) | SQLite スキーマ・画像/埋め込みの保存・マイグレーション方針 |
| [multi-tenant.md](multi-tenant.md) | project キーによるテナント分離・API キー発行と検証 |
| [admin.md](admin.md) | admin UI・Basic 認証・アクティブラーニングの運用フロー |
| [security.md](security.md) | 認証・untrusted input（画像/メタデータ）の扱い・リソース制限 |
| [deploy.md](deploy.md) | Railway デプロイ・Dockerfile・ボリューム・モデル同梱 |
| [env.md](env.md) | 環境変数一覧 |
| [client-integration.md](client-integration.md) | クライアント連携手順（ai-kyoto-osaka を例に） |
| [roadmap.md](roadmap.md) | 実装ステップ（フェーズ分け）・検証計画 |

## 設計の前提（議論で確定済み）

- 目的は **汎用の left/right 判定**。ai-kyoto-osaka 専用ではなく、複数サービスから再利用する。
- スタックは **Python + FastAPI**（埋め込みモデルの推論が要なので ML エコシステムに寄せる）。
- 判定は **DINOv2 埋め込み + k-NN**（CNN 丸ごと学習はしない＝少データ・CPU・即時反映）。
- テナントは **project キーで分離**（ドメインの違う画像でラベルを混ぜない）。
- リポは **独立リポ**（`~/Dev/ai-facing-api`）。
