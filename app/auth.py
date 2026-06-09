"""認証（docs/security.md, docs/multi-tenant.md）。

- サービス間（predict/label）: X-API-Key を sha256 照合し、URL の project と一致を確認。
- admin / project 作成: Basic 認証（ADMIN_USER / ADMIN_PASS）。
- AUTH_DISABLED=1 はローカル開発専用のバイパス。本番では立てない。
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import sqlite3
from urllib.parse import urlparse

from fastapi import Request

from .config import Settings
from .db import Database
from .errors import forbidden, no_such_project, unauthorized

_API_KEY_PREFIX = "fk_live_"


def generate_api_key() -> str:
    return _API_KEY_PREFIX + secrets.token_hex(16)  # 32 桁


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _db(request: Request) -> Database:
    return request.app.state.db


def require_admin(request: Request) -> None:
    """admin / project 作成用の Basic 認証。"""
    settings = _settings(request)
    if settings.auth_disabled:
        return
    if not settings.admin_user or not settings.admin_pass:
        # 認証情報が未設定なら開けない（安全側）。
        raise unauthorized("admin 認証が構成されていません")

    # ブラウザに Basic 認証ダイアログを出させるためのヘッダ。
    # これが無いと 401 でも資格情報の入力プロンプトが表示されない。
    challenge = {"WWW-Authenticate": 'Basic realm="admin"'}

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        raise unauthorized("Basic 認証が必要です", headers=challenge)
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        user, _, password = decoded.partition(":")
    except Exception as exc:
        raise unauthorized("Basic 認証ヘッダが不正です", headers=challenge) from exc

    ok_user = secrets.compare_digest(user, settings.admin_user)
    ok_pass = secrets.compare_digest(password, settings.admin_pass)
    if not (ok_user and ok_pass):
        raise unauthorized("admin 認証に失敗しました", headers=challenge)


def verify_same_origin(request: Request) -> None:
    """ブラウザ起点の状態変更に対する CSRF 対策（docs/security.md）。

    Basic 認証はブラウザが資格情報を自動送信するため、悪意あるサイトのフォームから
    admin の状態変更を誘発できる。Origin/Referer があれば**同一オリジン**を要求する。
    これらが無いリクエスト（curl 等のサービス間呼び出し）は CSRF の文脈ではないので素通し
    （認証自体は require_admin / require_project が別途担う）。
    """
    source = request.headers.get("origin") or request.headers.get("referer")
    if source is None:
        return
    host = request.headers.get("host", "")
    if urlparse(source).netloc != host:
        raise forbidden("クロスオリジンからの状態変更は拒否されます")


def require_project(request: Request, project: str) -> sqlite3.Row:
    """project の存在と API キー一致を確認し、project 行を返す。"""
    db = _db(request)
    settings = _settings(request)

    row = db.get_project(project)
    if row is None:
        raise no_such_project(project)

    if settings.auth_disabled:
        return row

    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise unauthorized("X-API-Key が必要です")

    if not secrets.compare_digest(hash_api_key(api_key), row["api_key_hash"]):
        # キーが他 project のものか不正。情報を絞って 403。
        raise forbidden("API キーがこの project と一致しません")

    return row
