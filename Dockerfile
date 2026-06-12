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
RUN mkdir -p models && \
    curl -fsSL https://github.com/mohhh-ok/image-facing-api/releases/download/v1/dinov2_vits14.onnx \
      -o models/dinov2_vits14.onnx && \
    echo "b43bd497e2d9f79722371c3177fb2f92917da84df1db9aece9cdce03abfeea1b  models/dinov2_vits14.onnx" \
      | sha256sum -c -

# 依存だけ先に入れてレイヤキャッシュを効かせる
COPY pyproject.toml README.md ./
COPY app/ app/
RUN pip install --no-cache-dir .

ENV DATA_DIR=/data \
    MODEL_PATH=models/dinov2_vits14.onnx \
    PORT=8000

EXPOSE 8000

# 単一プロセス・単一ワーカー（CPU 推論・SQLite のため）
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
