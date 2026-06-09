"""画像入力の3通り（multipart / image_base64 / image_url）を1箇所で解く（docs/api.md）。"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import Request

from .config import Settings
from .errors import bad_request
from .images import fetch_image_url

_IMAGE_KEYS = {"image_base64", "image_url", "file"}


async def extract_image_and_fields(request: Request, settings: Settings) -> tuple[bytes, dict[str, Any]]:
    """画像バイト列と、それ以外のフィールド（facing 等）を返す。"""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise bad_request("multipart には file フィールドが必要です")
        data = await upload.read()
        fields = {k: v for k, v in form.items() if k not in _IMAGE_KEYS}
        return data, fields

    # それ以外は JSON として扱う
    try:
        body = await request.json()
    except Exception as exc:
        raise bad_request("リクエストボディが JSON ではありません") from exc
    if not isinstance(body, dict):
        raise bad_request("リクエストボディは JSON オブジェクトである必要があります")

    if body.get("image_base64"):
        raw = body["image_base64"]
        # data URL プレフィックス（data:image/png;base64,...）を許容
        if isinstance(raw, str) and "," in raw and raw.strip().startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise bad_request("image_base64 を base64 デコードできません") from exc
    elif body.get("image_url"):
        if not settings.allow_image_url:
            raise bad_request("image_url は無効化されています（ALLOW_IMAGE_URL=false）")
        data = fetch_image_url(str(body["image_url"]), settings.max_image_bytes)
    else:
        raise bad_request("image_base64 / image_url / multipart file のいずれかが必要です")

    fields = {k: v for k, v in body.items() if k not in _IMAGE_KEYS}
    return data, fields
