FROM python:3.12-slim

WORKDIR /app

# onnxruntime / Pillow のための最小限のシステム依存 + モデル取得用の curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 埋め込みモデルを配信用 public repo の Release アセットからビルド時に取得する。
# URL・sha256 が固定なのでこのレイヤはキャッシュされ、アプリのコード変更では再DLされない
# （COPY app/ より前に置くのがポイント）。起動時ではなくビルド時取得なので
# 「起動時にネット取得しない」方針は維持。配信元: github.com/mohhh-ok/image-facing-api
#
# ViT-B/14 ONNX（~330MB, dim=768）。Release に dinov2_vitb14.onnx を置いてから build すること。
# ローカル hash: shasum -a 256 models/dinov2_vitb14.onnx
RUN mkdir -p models && \
    curl -fsSL https://github.com/mohhh-ok/image-facing-api/releases/download/v2/dinov2_vitb14.onnx \
      -o models/dinov2_vitb14.onnx && \
    echo "b0a03bc8bb2b834f92803fc676e3486bda85a5a6897d448fb6877f3f30822af4  models/dinov2_vitb14.onnx" \
      | sha256sum -c -

# 依存だけ先に入れてレイヤキャッシュを効かせる
COPY pyproject.toml README.md ./
COPY app/ app/
RUN pip install --no-cache-dir .

ENV DATA_DIR=/data \
    MODEL_PATH=models/dinov2_vitb14.onnx \
    MODEL_NAME=dinov2_vitb14 \
    EMBED_VERSION=2 \
    PORT=8000

EXPOSE 8000

# 単一プロセス・単一ワーカー（CPU 推論・SQLite のため）
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
