"""画像の取り込み・検疫（docs/security.md の untrusted input 対策）。

- サイズ上限・decompression bomb 対策・デコード失敗を弾く。
- sha256 で重複検出、元画像を data/images/<sha>.png に保存。
- flip 拡張用の水平反転もここで行う。
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageFile

from .errors import bad_image, bad_request, payload_too_large

# decompression bomb 対策: 画素数の上限（約 8900 万画素 = 一般的な上限）
Image.MAX_IMAGE_PIXELS = 89_478_485
# 壊れた画像で無限に読み続けないように truncated を許さない
ImageFile.LOAD_TRUNCATED_IMAGES = False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_image(data: bytes, max_bytes: int) -> Image.Image:
    """バイト列を検証付きでデコードして PIL 画像を返す。"""
    if len(data) == 0:
        raise bad_image("画像が空です")
    if len(data) > max_bytes:
        raise payload_too_large(f"画像が {max_bytes} バイトの上限を超えています")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # ここで実デコード（遅延ロードを確定させ、壊れた画像を弾く）
    except Image.DecompressionBombError as exc:  # pragma: no cover - 入力依存
        raise bad_image("画像の画素数が大きすぎます") from exc
    except Exception as exc:
        raise bad_image("画像をデコードできません") from exc
    return img


def save_original(images_dir: Path, data: bytes, sha: str) -> Path:
    """元画像を data/images/<sha>.png に保存（既にあれば何もしない）。"""
    images_dir.mkdir(parents=True, exist_ok=True)
    path = images_dir / f"{sha}.png"
    if not path.exists():
        img = Image.open(io.BytesIO(data))
        img.save(path, format="PNG")
    return path


def horizontal_flip(image: Image.Image) -> Image.Image:
    return image.transpose(Image.FLIP_LEFT_RIGHT)


# --- image_url（SSRF 対策・既定オフ）-------------------------------------


def _is_blocked_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local  # 169.254.0.0/16（クラウドメタデータ含む）
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
    return False


def fetch_image_url(url: str, max_bytes: int, timeout: float = 5.0) -> bytes:
    """https のみ・内部 IP ブロック・サイズ制限付きで画像を取得する。

    DoS 対策として本文はストリーミングし、累積バイトが上限を超えた時点で打ち切る
    （`resp.content` で一括読み込みしない）。Content-Length があれば事前に拒否する。

    注意（docs/security.md）: ホスト検証は「名前解決 → 接続」の間に再解決が入るため、
    DNS リバインディングを完全には防げない。`ALLOW_IMAGE_URL` は既定 false。本番で有効化する
    場合は egress プロキシ / 許可リストの併用を前提とする。
    """
    import httpx

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise bad_request("image_url は https のみ対応です")
    if not parsed.hostname or _is_blocked_ip(parsed.hostname):
        raise bad_request("image_url のホストは許可されていません")

    chunks: list[bytes] = []
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                cl = resp.headers.get("content-length")
                if cl is not None and cl.isdigit() and int(cl) > max_bytes:
                    raise payload_too_large("画像が上限を超えています")
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise payload_too_large("画像が上限を超えています")
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise bad_request("image_url を取得できません") from exc

    return b"".join(chunks)
