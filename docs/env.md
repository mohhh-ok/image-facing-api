# 環境変数一覧

`app/config.py` で読み込む。`.env` はコミットしない（本番は Railway の環境変数）。

| 変数 | 既定 | 説明 |
|---|---|---|
| `PORT` | 8000 | 待受ポート（Railway が注入） |
| `DATA_DIR` | `./data` | SQLite・画像・キャッシュの置き場。本番は `/data`（ボリューム） |
| `MODEL_PATH` | `models/dinov2_vits14.onnx` | 埋め込み ONNX のパス。無ければ起動時に明示エラー |
| `MODEL_NAME` | `dinov2_vits14` | DB に記録する埋め込みモデル名（再埋め込み判定用） |
| `EMBED_VERSION` | 1 | 前処理込みの埋め込みバージョン。変えたら再埋め込み |
| `KNN_K` | 9 | k-NN の既定 k（project 設定で上書き可） |
| `UNCERTAIN_THRESHOLD` | 0.55 | confidence がこれ未満で `uncertain=true` |
| `MAX_IMAGE_BYTES` | 10485760 | 受け取る画像の上限（10MB）。超過は 413 |
| `ALLOW_IMAGE_URL` | `false` | `image_url` 受付の可否。SSRF 懸念があるので既定オフ（[security.md](security.md)） |
| `ADMIN_USER` | （必須） | admin Basic 認証ユーザ |
| `ADMIN_PASS` | （必須） | admin Basic 認証パスワード |
| `AUTH_DISABLED` | `false` | **ローカル開発専用**。true で API キー/Basic を無効化。本番では絶対 true にしない |
| `DEFAULT_PROJECT` | （任意） | 開発用の既定 project 名。本番は使わない |
| `LOG_LEVEL` | `info` | ログレベル |

## 認証・秘密情報

- `ADMIN_PASS`・各 project の API キーはリポにコミットしない。
- API キーは DB に hash 保存。env には置かない（発行時にレスポンスで一度だけ平文を返す）。
