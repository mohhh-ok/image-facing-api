"""DINOv2 を ONNX に変換する（ビルド時 or 事前に1回だけ実行）。

本番ランタイムには torch を入れない。これは変換専用スクリプト。

使い方:
    pip install -e ".[export]"
    python scripts/export_dinov2_onnx.py --model dinov2_vits14
    python scripts/export_dinov2_onnx.py --model dinov2_vitb14

出力 ONNX は入力 (N, 3, 224, 224) float32 を受け、CLS トークン埋め込みを返す。
  - dinov2_vits14 → 384 dim
  - dinov2_vitb14 → 768 dim
前処理（リサイズ・正規化）は app/embed.py 側で行うので、ここではモデル本体のみを焼く。
"""

from __future__ import annotations

import argparse
from pathlib import Path

# torch.hub 名 → 既定出力パス
_MODELS: dict[str, str] = {
    "dinov2_vits14": "models/dinov2_vits14.onnx",
    "dinov2_vitb14": "models/dinov2_vitb14.onnx",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DINOv2 to ONNX")
    parser.add_argument(
        "--model",
        default="dinov2_vits14",
        choices=sorted(_MODELS),
        help="torch.hub のモデル名",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="出力パス（省略時は models/<model>.onnx）",
    )
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()

    import torch  # 遅延 import（export extra でのみ入る）

    out = Path(args.out) if args.out else Path(_MODELS[args.model])
    out.parent.mkdir(parents=True, exist_ok=True)

    # facebookresearch/dinov2。forward は CLS 埋め込みを返す。
    base = torch.hub.load("facebookresearch/dinov2", args.model).eval()

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
    with torch.no_grad():
        dim = int(model(dummy).shape[-1])
    print(f"ONNX を書き出しました: {out} (model={args.model}, dim={dim})")


if __name__ == "__main__":
    main()
