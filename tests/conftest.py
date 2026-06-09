"""テスト共通フィクスチャ。

埋め込みは決定的なスタブに差し替える（80MB の ONNX を要らずに k-NN/API ロジックを検証）。
スタブはグレースケールの列方向プロファイルを特徴にするので、左右で別ベクトル・
水平反転で別ベクトルになり、向きの対称性を実際に検証できる。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.embed import l2_normalize
from app.main import create_app

_DIM = 384
_GRID = (24, 16)  # 24*16 = 384


class StubEmbedder:
    model_name = "stub"
    dim = _DIM

    def embed(self, image: Image.Image) -> np.ndarray:
        small = image.convert("L").resize(_GRID, Image.BILINEAR)
        vec = np.asarray(small, dtype=np.float32).reshape(-1) / 255.0
        # 全体が一様だと L2 正規化でゼロ割れになるので中心化してから正規化
        vec = vec - vec.mean()
        return l2_normalize(vec)


def make_settings(tmp_path: Path, *, auth_disabled: bool = False) -> Settings:
    return Settings(
        port=8000,
        data_dir=tmp_path,
        model_path=tmp_path / "nope.onnx",
        model_name="stub",
        embed_version=1,
        knn_k=9,
        uncertain_threshold=0.55,
        max_image_bytes=10 * 1024 * 1024,
        allow_image_url=False,
        admin_user="admin",
        admin_pass="secret",
        auth_disabled=auth_disabled,
        default_project=None,
        log_level="warning",
    )


def make_image(side: str, size: int = 96) -> Image.Image:
    """side='left' なら左側、'right' なら右側に黒帯を置いた画像。向きが明確に異なる。"""
    img = Image.new("RGB", (size, size), (255, 255, 255))
    px = img.load()
    band = size // 3
    xs = range(0, band) if side == "left" else range(size - band, size)
    for x in xs:
        for y in range(size):
            px[x, y] = (0, 0, 0)
    return img


def image_bytes(img: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def app_factory(tmp_path):
    def _make(auth_disabled: bool = False):
        settings = make_settings(tmp_path, auth_disabled=auth_disabled)
        return create_app(settings=settings, embedder_factory=lambda _s: StubEmbedder())

    return _make


@pytest.fixture
def client(app_factory):
    from fastapi.testclient import TestClient

    with TestClient(app_factory(False)) as c:
        yield c


@pytest.fixture
def admin_auth():
    return ("admin", "secret")


def create_project(client, admin_auth, name="proj"):
    resp = client.post("/v1/projects", json={"name": name}, auth=admin_auth)
    assert resp.status_code == 200, resp.text
    return resp.json()["api_key"]
