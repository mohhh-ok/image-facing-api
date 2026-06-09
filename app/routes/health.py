"""GET /healthz（認証不要・Railway のヘルスチェック用）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..models import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz(request: Request) -> HealthResponse:
    state = request.app.state
    return HealthResponse(
        status="ok",
        model_loaded=state.embedder is not None,
        projects=len(state.db.list_projects()),
    )
