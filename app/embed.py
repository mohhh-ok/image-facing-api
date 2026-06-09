"""DINOv2 埋め込み（docs/model.md）。

「画像 → 384 次元 L2 正規化ベクトル」のインターフェースにモデルを閉じ込める。
前処理はここ1箇所に固定する（predict と label で食い違うと精度が崩れるため）。

- `onnxruntime` はこのモジュールのトップでは import しない（遅延 import）。
  そうすることで、埋め込みをスタブに差し替えたテストや、モデル未配置の環境でも
  app 本体・API ロジックを起動・検証できる。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from PIL import Image

# ImageNet 統計（DINOv2 標準前処理）
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_INPUT_SIZE = 224  # DINOv2 ViT-S/14: 224 = 16 * 14


@runtime_checkable
class Embedder(Protocol):
    """埋め込みの抽象。テストはこの形のスタブを差し込む。"""

    model_name: str
    dim: int

    def embed(self, image: Image.Image) -> np.ndarray:  # (dim,) float32, L2 正規化済み
        ...


def preprocess(image: Image.Image, fill_color: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """PIL 画像 → NCHW float32 テンソル（1, 3, 224, 224）。docs/model.md の前処理を固定。"""
    # 1. RGB 化（透過は指定色で合成）
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        bg = Image.new("RGB", rgba.size, fill_color)
        bg.paste(rgba, mask=rgba.split()[-1])
        image = bg
    else:
        image = image.convert("RGB")

    # 2. アスペクト比を保って短辺 224 → 中央 224x224 クロップ
    w, h = image.size
    scale = _INPUT_SIZE / min(w, h)
    new_w, new_h = round(w * scale), round(h * scale)
    image = image.resize((new_w, new_h), Image.BICUBIC)
    left = (new_w - _INPUT_SIZE) // 2
    top = (new_h - _INPUT_SIZE) // 2
    image = image.crop((left, top, left + _INPUT_SIZE, top + _INPUT_SIZE))

    # 3. [0,1] 化 → ImageNet 正規化
    arr = np.asarray(image, dtype=np.float32) / 255.0  # HWC
    arr = (arr - _IMAGENET_MEAN) / _IMAGENET_STD

    # 4. NCHW
    chw = np.transpose(arr, (2, 0, 1))
    return chw[np.newaxis, :, :, :].astype(np.float32)


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return vec.astype(np.float32)
    return (vec / norm).astype(np.float32)


class Dinov2OnnxEmbedder:
    """onnxruntime（CPU）で DINOv2 ONNX を推論する本番実装。"""

    def __init__(self, model_path: Path, model_name: str, dim: int = 384) -> None:
        import onnxruntime as ort  # 遅延 import

        if not Path(model_path).exists():
            raise FileNotFoundError(f"埋め込みモデルが見つかりません: {model_path}")

        self.model_name = model_name
        self.dim = dim
        self._session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name

    def embed(self, image: Image.Image) -> np.ndarray:
        tensor = preprocess(image)
        outputs = self._session.run(None, {self._input_name: tensor})
        vec = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
        if vec.shape[0] != self.dim:
            raise ValueError(
                f"埋め込み次元が想定と異なります: got {vec.shape[0]}, expected {self.dim}"
            )
        return l2_normalize(vec)
