FROM python:3.12-slim

WORKDIR /app

# onnxruntime / Pillow のための最小限のシステム依存だけ入れる
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 依存だけ先に入れてレイヤキャッシュを効かせる
COPY pyproject.toml README.md ./
COPY app/ app/
RUN pip install --no-cache-dir .

# 埋め込みモデルを同梱（起動時にネット取得しない・docs/deploy.md）
COPY models/ models/

ENV DATA_DIR=/data \
    MODEL_PATH=models/dinov2_vits14.onnx \
    PORT=8000

EXPOSE 8000

# 単一プロセス・単一ワーカー（CPU 推論・SQLite のため）
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
