"""DINOv2 ViT-S/14 を ONNX に変換する（ビルド時 or 事前に1回だけ実行）。

本番ランタイムには torch を入れない。これは変換専用スクリプト。

使い方:
    pip install -e ".[export]"
    python scripts/export_dinov2_onnx.py --out models/dinov2_vits14.onnx

出力 ONNX は入力 (N, 3, 224, 224) float32 を受け、CLS トークンの 384 次元埋め込みを返す。
前処理（リサイズ・正規化）は app/embed.py 側で行うので、ここではモデル本体のみを焼く。
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DINOv2 ViT-S/14 to ONNX")
    parser.add_argument("--out", default="models/dinov2_vits14.onnx")
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()

    import torch  # 遅延 import（export extra でのみ入る）

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # facebookresearch/dinov2 の小型モデル。forward は CLS 埋め込み（384 次元）を返す。
    base = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14").eval()

    # DINOv2 の forward は masks 引数を持ち、素の export だと未使用の 'masks' 入力が
    # ONNX グラフに混入する（onnxruntime が必須入力として要求してしまう）。
    # x だけを受けるラッパで包み、単一入力 'input' に固定する。
    class _SingleInput(torch.nn.Module):
        def __init__(self, m: torch.nn.Module) -> None:
            super().__init__()
            self.m = m

        def forward(self, x):
            return self.m(x)

    model = _SingleInput(base).eval()

    dummy = torch.randn(1, 3, 224, 224, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        str(out),
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=args.opset,
        do_constant_folding=True,
        # 従来の TorchScript エクスポータを使う（dynamo=True の新経路は dynamic_axes を
        # 解釈できず失敗するため）。本サービスは batch=1 固定なので legacy で十分。
        dynamo=False,
    )
    print(f"ONNX を書き出しました: {out}")


if __name__ == "__main__":
    main()
