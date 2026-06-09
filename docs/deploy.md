# デプロイ（Railway）

本番エンドポイント: `https://facing-api-production.up.railway.app`（Railway project `ai` / service `facing-api`）。
API キー・admin パスワードはリポに置かない（Railway の環境変数と各自の `.env` のみ）。

## 方針

- Railway で Dockerfile ビルド。**ボリュームを `/data` にマウント**（SQLite・画像・埋め込みの永続化）。
- 埋め込みモデル（DINOv2 ONNX・約 80〜90MB）は**イメージに同梱**する（起動時にネット取得しない）。
  Git LFS で持つか、ビルド時に `scripts/export_dinov2_onnx.py` か公式配布から取得して `models/` に置く。
- 単一プロセス・単一ワーカー（CPU 推論・SQLite のため）。`uvicorn app.main:app --host 0.0.0.0 --port $PORT`。

## Dockerfile（目標の形）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
# onnxruntime/Pillow のための最小限のシステム依存だけ入れる
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .   # or uv
COPY app/ app/
COPY models/ models/                  # dinov2_vits14.onnx を同梱
ENV DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- 本番ランタイムに `torch` を入れない（onnxruntime だけ）。イメージを軽く保つ。
- `models/` をイメージに焼くことで、コールドスタートでモデル DL を待たない。

## railway.json（目標）

- ヘルスチェックを `/healthz` に向ける。
- ボリュームを `/data` にマウント（名前付きボリューム）。
- `PORT` は Railway 注入。`DATA_DIR=/data` を環境変数で設定。

## 永続化の注意

- **DB・画像・埋め込みは `/data`（ボリューム）に置く。** イメージ内に書くとデプロイのたびに消える。
- 起動時に `/data` が空なら schema を作成し、空の状態から始める（最初の project 作成から）。
- バックアップ: `/data/facing.db` と `/data/images/` を定期コピーできるようにしておくと安全
  （ラベルは人手で貯めた資産なので失うと痛い）。

## コスト感

- CPU 推論のみ。GPU 不要。小さいインスタンスで動く。
- 主なコストは常時起動分とボリューム。画像は元データを保存するので、ラベルが増えると
  `/data/images/` が増える（1枚あたり数十〜数百 KB。WebP/PNG 縮小で抑えられる）。

## ローカル実行

```
pip install -e .        # or uv sync
export DATA_DIR=./data
export AUTH_DISABLED=1   # ローカルだけ。本番では立てない
uvicorn app.main:app --reload
```
モデルファイルは `models/dinov2_vits14.onnx` を置いておく（無ければ起動時に明示エラー）。
