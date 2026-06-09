"""POST /v1/{project}/predict（判定・学習データには加えない）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..auth import require_project
from ..deps import get_service
from ..models import NeighborOut, PredictResponse
from ..request_input import extract_image_and_fields

router = APIRouter(prefix="/v1")


def _as_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@router.post("/{project}/predict", response_model=PredictResponse)
async def predict(project: str, request: Request) -> PredictResponse:
    project_row = require_project(request, project)
    settings = request.app.state.settings
    data, fields = await extract_image_and_fields(request, settings)
    include_neighbors = _as_bool(
        fields.get("include_neighbors", request.query_params.get("include_neighbors")),
        default=True,
    )

    svc = get_service(request)
    result = svc.predict(project, data, project_row)

    # 監査ログ（任意）。画像本体は保存せずハッシュのみ。
    from ..images import sha256_hex

    request.app.state.db.insert_prediction(
        project, sha256_hex(data), result.facing, result.confidence, result.uncertain
    )

    neighbors = None
    if include_neighbors:
        neighbors = [
            NeighborOut(sample_id=n.sample_id, facing=n.facing, similarity=n.similarity)
            for n in result.neighbors
        ]

    return PredictResponse(
        facing=result.facing,
        confidence=result.confidence,
        uncertain=result.uncertain,
        neighbors=neighbors,
        model=result.model,
        k=result.k,
    )
