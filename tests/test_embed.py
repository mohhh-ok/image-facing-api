"""前処理と埋め込みスタブの基本性質（docs/roadmap.md フェーズ1の確認）。"""

from __future__ import annotations

import numpy as np

from app.embed import preprocess
from tests.conftest import StubEmbedder, make_image


def test_preprocess_shape_and_dtype():
    tensor = preprocess(make_image("left"))
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == np.float32


def test_image_and_flip_are_different_vectors():
    """同じ画像とその水平反転が別ベクトルになる（向き情報を保持している証拠）。"""
    emb = StubEmbedder()
    left = make_image("left")
    flipped = left.transpose(0)  # PIL.Image.FLIP_LEFT_RIGHT == 0
    v1 = emb.embed(left)
    v2 = emb.embed(flipped)
    assert v1.shape == (384,)
    # L2 正規化済み
    assert abs(float(np.linalg.norm(v1)) - 1.0) < 1e-5
    # 反転で別ベクトル（cosine が 1 ではない）
    assert float(v1 @ v2) < 0.99


def test_left_right_images_separate():
    emb = StubEmbedder()
    vl = emb.embed(make_image("left"))
    vr = emb.embed(make_image("right"))
    # left と right は明確に異なる方向
    assert float(vl @ vr) < 0.5
