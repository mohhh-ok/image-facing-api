"""ルートから app.state を取り出す小さなヘルパ。"""

from __future__ import annotations

from fastapi import Request

from .service import FacingService


def get_service(request: Request) -> FacingService:
    state = request.app.state
    return FacingService(state.db, state.store, state.embedder, state.settings)
