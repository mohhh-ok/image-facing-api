# デプロイ（Railway）

本番エンドポイント: `https://facing-api-production.up.railway.app`（Railway project `ai` / service `facing-api`）。
API キー・admin パスワードはリポに置かない（Railway の環境変数と各自の `.env` のみ）。

デプロイは **素の `railway up`**（`--no-gitignore` は不要）。埋め込みモデル `dinov2_vits14.onnx` は
本体リポに含めず、配信用 public repo [`ai-facing-api-models`](https://github.com/mohhh-ok/ai-facing-api-models)
の Release アセットに置き、**Dockerfile がビルド時に匿名 `curl` で取得**して sha256 検証する。
これにより `railway up` に 84MB を毎回乗せず、`.gitignore` で onnx を git 除外したまま
`model_loaded:true` を保てる（旧来の `--no-gitignore` 運用は廃止）。`.env` は `.railwayignore` で
除外し、かつ Dockerfile も COPY しないのでイメージに入らない。

## 方針

- Railway で Dockerfile ビルド。**ボリュームを `/data` にマウント**（SQLite・画像・埋め込みの永続化）。
- 埋め込みモデル（DINOv2 ONNX・約 84MB）は**ビルド時に配信用 public repo の Release から取得**して
  イメージに焼く（起動時ではなくビルド時取得なので「起動時にネット取得しない」方針は維持）。
  再生成手順は配信用 repo の README 参照。
- 単一プロセス・単一ワーカー（CPU 推論・SQLite のため）。`uvicorn app.main:app --host 0.0.0.0 --port $PORT`。

## Dockerfile（目標の形）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
# onnxruntime/Pillow のための最小限のシステム依存 + モデル取得用 curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl ca-certificates && rm -rf /var/lib/apt/lists/*
# モデルは配信用 public repo の Release からビルド時取得（COPY app/ より前でキャッシュを効かせる）
RUN mkdir -p models && curl -fsSL <release-url>/dinov2_vits14.onnx -o models/dinov2_vits14.onnx \
    && echo "<sha256>  models/dinov2_vits14.onnx" | sha256sum -c -
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .   # or uv
COPY app/ app/
ENV DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- 本番ランタイムに `torch` を入れない（onnxruntime だけ）。イメージを軽く保つ。
- モデルはビルド時にイメージへ焼くので、コールドスタートでモデル DL を待たない。

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
