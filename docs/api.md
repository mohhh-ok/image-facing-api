# HTTP API 仕様

ベース URL は環境依存（ローカル `http://localhost:8000`、本番は Railway の URL）。
バージョンプレフィックスは `/v1`。認証は [security.md](security.md) と [multi-tenant.md](multi-tenant.md) を参照。

全エンドポイント共通:
- 画像の渡し方は **3 通り対応**（どれか1つ）: `multipart/form-data` のファイル、JSON の `image_base64`、JSON の `image_url`。
- 認証: サービス間呼び出しは `X-API-Key` ヘッダ（project に紐づくキー）。admin UI は Basic 認証。
- エラーは `{"error": {"code": "...", "message": "..."}}` 形式・適切な HTTP ステータス。

---

## POST /v1/{project}/predict

画像の向きを判定する。**学習データには加えない**（ラベルではない）。

リクエスト（JSON 例）:
```json
{ "image_base64": "iVBORw0KGgo..." }
```
または multipart の `file` フィールド、または `{"image_url": "https://..."}`。

レスポンス:
```json
{
  "facing": "left",
  "confidence": 0.86,
  "uncertain": false,
  "neighbors": [
    { "sample_id": 1421, "facing": "left", "similarity": 0.94 },
    { "sample_id": 0987, "facing": "left", "similarity": 0.91 }
  ],
  "model": "dinov2_vits14",
  "k": 9
}
```

- `facing`: `"left" | "right"`。
- `confidence`: 0..1。近傍の票割合と距離から算出（[model.md](model.md)）。
- `uncertain`: しきい値未満（票が割れた / 近傍が遠い / ラベルがまだ少ない）の場合 true。
  クライアントはこれを見て **フォールバック（例: LLM 判定）や admin 行き**に回せる。
- `neighbors`: デバッグ・admin 表示用（`include_neighbors=false` で省略可）。

`uncertain=true` でも `facing` は必ず返す（クライアントが二択を必要とするため）。

---

## POST /v1/{project}/label

正解ラベルを登録する。学習データに加わり、以降の predict に**即時反映**される。

リクエスト（JSON 例）:
```json
{
  "image_base64": "iVBORw0KGgo...",
  "facing": "right",
  "external_id": "yokai-51",     // 任意。クライアント側の識別子（DB に保存するだけ。突合には使わない）
  "source": "human"               // 任意。"human" | "import" | "model" など。既定 "human"
}
```

レスポンス:
```json
{ "sample_id": 1422, "facing": "right", "deduped": false, "flip_added": true, "project_size": 318 }
```

- 同一画像（sha256 一致）が既にあれば **facing を更新**（`deduped: true`）。
- `flip_added`: 水平反転版を逆ラベルで追加したか（既定で追加。[model.md](model.md)）。
- `project_size`: 反転拡張込みの現在のラベル件数。
- `source="human"` は admin/人手の最優先ラベル。`model` 由来は信頼度を下げて扱ってよい。

---

## POST /v1/{project}/predict_and_maybe_label （任意・将来）

predict した結果 confidence が高ければ自動でラベル化する省力フロー。初版は実装しなくてよい。

---

## POST /v1/projects

project を新規作成し API キーを発行する（**admin 認証必須**）。

リクエスト: `{ "name": "ai-kyoto-osaka", "description": "妖怪姿絵の向き合わせ" }`

レスポンス:
```json
{ "project": "ai-kyoto-osaka", "api_key": "fk_live_xxx", "created_at": "..." }
```
`api_key` は**この応答でしか平文を返さない**（DB はハッシュ保存）。

## GET /v1/projects

project 一覧（**admin 認証必須**）。件数・最終更新等を返す。

---

## GET /admin

admin UI（**Basic 認証**）。project を選び、サンプルの一覧と向きをポチポチ修正する。
詳細は [admin.md](admin.md)。修正は内部的に label と同じ経路を通る。

## GET /healthz

`{ "status": "ok", "model_loaded": true, "projects": 3 }`。認証不要。Railway のヘルスチェック用。

---

## ステータスコードとエラーコード

| HTTP | code | 意味 |
|---|---|---|
| 400 | `bad_image` | 画像がデコードできない・サイズ超過・形式非対応 |
| 400 | `bad_request` | 必須フィールド欠落・facing が left/right 以外 |
| 401 | `unauthorized` | API キー / Basic 認証なし・不正 |
| 403 | `forbidden` | キーは有効だが project 不一致 |
| 404 | `no_such_project` | project が存在しない |
| 413 | `payload_too_large` | 画像が上限超過（[security.md](security.md)） |
| 422 | （FastAPI 既定のバリデーションエラー） | |
| 500 | `internal` | 想定外。握りつぶさずログに残す |
