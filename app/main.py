"""FastAPI エントリ（docs/architecture.md）。

起動時に DINOv2 ONNX をロードし、DB から全 project の埋め込みをメモリへ復元する。
モデルが無い環境でも app は起動する（predict/label は 503 を返す）。project 作成・admin・
healthz はモデル無しでも動く。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .db import Database
from .embed import Dinov2OnnxEmbedder, Embedder
from .errors import AppError
from .routes import admin, health, label, predict, projects
from .store import Store

logger = logging.getLogger("facing")

_DEFAULT_DIM = 384


def _default_embedder_factory(settings: Settings) -> Embedder | None:
    try:
        return Dinov2OnnxEmbedder(settings.model_path, settings.model_name)
    except Exception as exc:  # FileNotFoundError / onnxruntime 未導入など
        logger.error(
            "埋め込みモデルを読み込めませんでした: %s（predict/label は 503 を返します）", exc
        )
        return None


def create_app(
    settings: Settings | None = None,
    embedder_factory: Callable[[Settings], Embedder | None] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    embedder_factory = embedder_factory or _default_embedder_factory

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=settings.log_level.upper())
        settings.data_dir.mkdir(parents=True, exist_ok=True)

        db = Database(settings.db_path)
        embedder = embedder_factory(settings)
        dim = embedder.dim if embedder is not None else _DEFAULT_DIM
        store = Store(dim)
        store.warmup(db)

        app.state.settings = settings
        app.state.db = db
        app.state.embedder = embedder
        app.state.store = store
        logger.info(
            "起動完了: model_loaded=%s projects=%s", embedder is not None, store.project_count()
        )
        try:
            yield
        finally:
            db.close()

    app = FastAPI(title="ai-facing-api", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("想定外のエラー: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal", "message": "内部エラーが発生しました"}},
        )

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(predict.router)
    app.include_router(label.router)
    app.include_router(admin.router)
    return app


app = create_app()
