"""DINOv2 ONNX の embed 速度を測る（HTTP / DB なし）。

使い方（リポジトリルートで）:
    .venv/bin/python scripts/bench_embed.py
    .venv/bin/python scripts/bench_embed.py --models models/dinov2_vits14.onnx models/dinov2_vitb14.onnx
    .venv/bin/python scripts/bench_embed.py --image /path/to.png --warmup 3 --runs 20

出力: モデルごとの load ms / dim / warm embed p50・p95・mean。
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

# リポジトリルートを path に
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PIL import Image  # noqa: E402

from app.embed import Dinov2OnnxEmbedder  # noqa: E402


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _load_image(path: Path | None) -> Image.Image:
    if path is not None:
        return Image.open(path).convert("RGBA")
    # 透過キャラっぽいダミー（前処理経路を本番に近づける）
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    # 中央に不透明な色塊
    for y in range(200, 800):
        for x in range(300, 700):
            img.putpixel((x, y), (200, 80, 60, 255))
    return img


def bench_one(
    model_path: Path,
    image: Image.Image,
    warmup: int,
    runs: int,
) -> None:
    if not model_path.exists():
        print(f"SKIP  {model_path} (missing)")
        return

    t0 = time.perf_counter()
    emb = Dinov2OnnxEmbedder(model_path, model_name=model_path.stem)
    load_ms = (time.perf_counter() - t0) * 1000

    for _ in range(warmup):
        emb.embed(image)

    times: list[float] = []
    for _ in range(runs):
        t1 = time.perf_counter()
        vec = emb.embed(image)
        times.append((time.perf_counter() - t1) * 1000)

    print(
        f"{model_path.name:28s}  dim={emb.dim:4d}  load={load_ms:7.1f}ms  "
        f"embed mean={statistics.mean(times):7.1f}ms  "
        f"p50={_percentile(times, 50):7.1f}ms  "
        f"p95={_percentile(times, 95):7.1f}ms  "
        f"min={min(times):7.1f}ms  max={max(times):7.1f}ms  "
        f"(warmup={warmup}, runs={runs}, out_norm≈{float((vec**2).sum())**0.5:.3f})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bench DINOv2 ONNX embed latency")
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "models/dinov2_vits14.onnx",
            "models/dinov2_vitb14.onnx",
        ],
    )
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()

    image = _load_image(args.image)
    print(f"image={args.image or 'synthetic RGBA 1024'} size={image.size}")
    for m in args.models:
        bench_one(Path(m), image, args.warmup, args.runs)


if __name__ == "__main__":
    main()
