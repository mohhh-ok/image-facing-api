# 実装ロードマップ

設計ドキュメントに従って、下から積む。各フェーズは「動いて確認できる」単位で切る。

## フェーズ 0: 足場

- [ ] `pyproject.toml`（fastapi, uvicorn, onnxruntime, pillow, numpy, jinja2。torch は dev/scripts のみ）
- [ ] `.gitignore`（`data/`, `.env`, `__pycache__`, 大きいモデルは LFS か別管理）
- [ ] `app/config.py`（[env.md](env.md) の変数を読む）
- [ ] `app/db.py`（[database.md](database.md) の schema を `CREATE TABLE IF NOT EXISTS`）
- [ ] `GET /healthz`

## フェーズ 1: 埋め込み

- [ ] `scripts/export_dinov2_onnx.py`（DINOv2 ViT-S/14 → `models/dinov2_vits14.onnx`）
- [ ] `app/embed.py`（前処理を [model.md](model.md) どおり固定 → 384 次元 L2 正規化ベクトル）
- [ ] 単体確認: 同じ画像と、その水平反転が**別ベクトル**になること（向き情報を保持している証拠）

## フェーズ 2: 学習集合と k-NN

- [ ] `app/store.py`（起動時に embeddings を project ごと numpy 行列へ。label で append）
- [ ] `app/classifier.py`（cosine 近傍・多数決・confidence・[model.md](model.md) の式）
- [ ] flip 拡張（label 時に逆ラベルで追加・`origin_sample_id` で紐付け）

## フェーズ 3: API

- [ ] `app/auth.py`（API キー hash 照合・admin Basic・`AUTH_DISABLED` はローカルのみ）
- [ ] `POST /v1/projects`（作成・キー発行）/ `GET /v1/projects`
- [ ] `POST /v1/{project}/label`（dedupe・画像保存・埋め込み・flip 拡張・即反映）
- [ ] `POST /v1/{project}/predict`（判定・confidence・uncertain）
- [ ] エラーコード（[api.md](api.md)）・画像サイズ上限（[security.md](security.md)）

## フェーズ 4: admin UI

- [ ] `GET /admin`（project 選択・サンプル一覧・プレビュー反転・`[←left][right→]` トグル）
- [ ] uncertain / 未ラベル / 最近追加のフィルタ、flip 拡張行を隠す
- [ ] 元サンプル修正時に flip 拡張行を自動追従

## フェーズ 5: デプロイ

- [ ] `Dockerfile`（モデル同梱・torch 無し）
- [ ] `railway.json`（`/healthz`・`/data` ボリューム）
- [ ] 本番に project 作成、API キー発行

## フェーズ 6: クライアント連携（ai-kyoto-osaka）

- [ ] `scripts/import_labels.py`（既存の facing_judgements / 画像から種ラベルを一括投入）
- [ ] ai-kyoto-osaka 側を [client-integration.md](client-integration.md) どおり改修
      （flop 廃止・`yokai.facing` 追加・UI 反転・`facing='left'` 初期化・フォールバック）

## 検証の観点

- 同一画像→反転で facing が反転すること（対称性）。
- ラベルを足すと uncertain が減ること（学習が効いている）。
- admin 修正が次の predict に即反映されること（再起動不要）。
- API キー / project スコープの分離（他 project のラベルに触れない）。
- 画像不正・サイズ超過・認証なしが正しく弾かれること。
