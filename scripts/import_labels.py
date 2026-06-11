"""既存ラベルを HTTP API 経由で一括投入する（docs/roadmap.md フェーズ6）。

ディレクトリ構成を前提:
    <root>/left/*.png   → facing=left で投入
    <root>/right/*.png  → facing=right で投入

使い方:
    python scripts/import_labels.py \
        --url http://localhost:8000 --project my-project --api-key fk_live_xxx \
        --root ./seed --source import
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk import labels via HTTP API")
    parser.add_argument("--url", required=True, help="ベース URL（例 http://localhost:8000）")
    parser.add_argument("--project", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--root", required=True, help="left/ right/ を含むディレクトリ")
    parser.add_argument("--source", default="import")
    args = parser.parse_args()

    import httpx

    root = Path(args.root)
    endpoint = f"{args.url.rstrip('/')}/v1/{args.project}/label"
    headers = {"X-API-Key": args.api_key}

    sent = 0
    with httpx.Client(timeout=30.0) as client:
        for facing in ("left", "right"):
            folder = root / facing
            if not folder.is_dir():
                continue
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() not in _EXTS:
                    continue
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                resp = client.post(
                    endpoint,
                    headers=headers,
                    json={
                        "image_base64": b64,
                        "facing": facing,
                        "source": args.source,
                        "external_id": path.stem,
                    },
                )
                resp.raise_for_status()
                sent += 1
                print(f"[{facing}] {path.name} -> {resp.json()}")

    print(f"投入完了: {sent} 件")


if __name__ == "__main__":
    main()
