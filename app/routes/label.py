"""POST /v1/{project}/label（正解ラベル登録・即時反映）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..auth import require_project
from ..deps import get_service
from ..errors import bad_request
from ..models import LabelResponse
from ..request_input import extract_image_and_fields

router = APIRouter(prefix="/v1")


@router.post("/{project}/label", response_model=LabelResponse)
async def label(project: str, request: Request) -> LabelResponse:
    require_project(request, project)
    settings = request.app.state.settings
    data, fields = await extract_image_and_fields(request, settings)

    facing = fields.get("facing")
    if facing is None:
        raise bad_request("facing は必須です（'left' | 'right'）")
    source = fields.get("source") or "human"
    external_id = fields.get("external_id")

    svc = get_service(request)
    result = svc.add_label(
        project,
        data,
        str(facing),
        source=str(source),
        external_id=str(external_id) if external_id is not None else None,
    )
    return LabelResponse(
        sample_id=result.sample_id,
        facing=result.facing,
        deduped=result.deduped,
        flip_added=result.flip_added,
        project_size=result.project_size,
    )
