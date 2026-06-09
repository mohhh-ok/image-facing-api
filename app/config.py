"""環境変数の読み込み（docs/env.md と対応）。

設定はプロセス起動時に1度だけ読む。`get_settings()` で取得し、テストでは
環境変数を差し替えて `get_settings.cache_clear()` で読み直せる。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    port: int
    data_dir: Path
    model_path: Path
    model_name: str
    embed_version: int
    knn_k: int
    uncertain_threshold: float
    max_image_bytes: int
    allow_image_url: bool
    admin_user: str
    admin_pass: str
    auth_disabled: bool
    default_project: str | None
    log_level: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "facing.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.environ.get("DATA_DIR", "./data")).expanduser()
    return Settings(
        port=_int("PORT", 8000),
        data_dir=data_dir,
        model_path=Path(os.environ.get("MODEL_PATH", "models/dinov2_vits14.onnx")),
        model_name=os.environ.get("MODEL_NAME", "dinov2_vits14"),
        embed_version=_int("EMBED_VERSION", 1),
        knn_k=_int("KNN_K", 9),
        uncertain_threshold=_float("UNCERTAIN_THRESHOLD", 0.55),
        max_image_bytes=_int("MAX_IMAGE_BYTES", 10 * 1024 * 1024),
        allow_image_url=_bool("ALLOW_IMAGE_URL", False),
        admin_user=os.environ.get("ADMIN_USER", ""),
        admin_pass=os.environ.get("ADMIN_PASS", ""),
        auth_disabled=_bool("AUTH_DISABLED", False),
        default_project=os.environ.get("DEFAULT_PROJECT") or None,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
