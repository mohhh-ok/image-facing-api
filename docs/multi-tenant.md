# マルチテナント（project 分離）

## なぜ分けるか

汎用サービスなので、クライアントごとに画像ドメインが違う（妖怪イラスト / 写真 / 商品画像 …）。
**「何を left とするか」はドメインで変わる**し、ラベルを混ぜると k-NN の近傍が他ドメインに汚染される。
よって **project 単位でラベル空間・k-NN インデックス・API キーを完全分離**する。

## project とは

- URL に出る識別子（`/v1/{project}/...`）。英数・ハイフンのみ（例 `ai-kyoto-osaka`）。
- 1 project = 1 ラベル集合 = 1 k-NN インデックス = 1 API キー（複数キーにしたければ別テーブル化）。
- predict / label は **必ず project スコープ**で動く。グローバル横断の判定はしない。

## API キー

- project 作成時（`POST /v1/projects`・admin 認証）に発行。
- 形式の目安: `fk_live_<ランダム32桁>`。**平文は発行レスポンスでしか返さない**。
- DB には `api_key_hash` のみ保存（hash は sha256 or argon2。検索性のため sha256 でも可だが、
  漏洩時の安全性は [security.md](security.md) 参照）。
- 検証: リクエストの `X-API-Key` を hash 化し、`projects.api_key_hash` と一致 かつ URL の project と一致を確認。
  不一致は 401/403。

## ローテーション・無効化

- キー再発行は新しい hash で上書き（旧キーは即失効）。初版は「作り直し」で十分。
- 将来複数キー / 失効日時が要るなら `api_keys(project, hash, label, revoked_at)` テーブルに分離。

## admin とテナント

- admin（Basic 認証）は **全 project を横断**して閲覧・修正できる運用者向け。
- admin UI は project を選んでラベルを直す（[admin.md](admin.md)）。
- project の API キーは「サービス間の自動呼び出し」用、admin は「人が運用する」用、と役割を分ける。

## 既定 project

- 開発の立ち上げを楽にするため、env で `DEFAULT_PROJECT` を1つ用意してもよい（任意）。
- ただし本番では各クライアントに固有 project を切る。`default` に集約しない。
