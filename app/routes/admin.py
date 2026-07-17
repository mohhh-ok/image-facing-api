"""admin UI。facing / zoom_up の手修正。"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_admin, verify_same_origin
from ..deps import get_service
from ..errors import bad_request
from ..params import parse_zoom_up

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


@router.get("", response_class=HTMLResponse)
def admin_home(request: Request, project: str | None = None, show_flip: bool = False):
    db = request.app.state.db
    projects = db.list_projects()

    samples = []
    selected = None
    if project:
        if db.get_project(project) is None:
            raise bad_request(f"project '{project}' は存在しません")
        selected = project
        rows = db.list_samples(project, include_flip=show_flip, limit=500)
        samples = [dict(r) for r in rows]

    return _TEMPLATES.TemplateResponse(
        request,
        "admin.html",
        {
            "projects": [dict(p) for p in projects],
            "selected": selected,
            "samples": samples,
            "show_flip": show_flip,
        },
    )


@router.post("/correct", dependencies=[Depends(verify_same_origin)])
def admin_correct(
    request: Request,
    project: str = Form(...),
    sample_id: int = Form(...),
    facing: str = Form(...),
    zoom_up: str = Form("false"),
    show_flip: bool = Form(False),
):
    try:
        zoom_up_b = parse_zoom_up(zoom_up)
    except ValueError as e:
        raise bad_request(str(e)) from e
    svc = get_service(request)
    svc.correct_label(project, sample_id, facing, zoom_up_b)
    url = f"/admin?project={project}"
    if show_flip:
        url += "&show_flip=true"
    return RedirectResponse(url=url, status_code=303)


@router.post("/delete", dependencies=[Depends(verify_same_origin)])
def admin_delete(
    request: Request,
    project: str = Form(...),
    sample_id: int = Form(...),
    show_flip: bool = Form(False),
):
    svc = get_service(request)
    svc.delete_label(project, sample_id)
    url = f"/admin?project={project}"
    if show_flip:
        url += "&show_flip=true"
    return RedirectResponse(url=url, status_code=303)


@router.get("/image/{sha}")
def admin_image(request: Request, sha: str):
    if not _SHA_RE.match(sha):
        raise bad_request("不正な画像 ID です")
    images_dir = request.app.state.settings.images_dir
    jpg = images_dir / f"{sha}.jpg"
    if jpg.exists():
        return FileResponse(str(jpg), media_type="image/jpeg")
    png = images_dir / f"{sha}.png"
    if png.exists():
        return FileResponse(str(png), media_type="image/png")
    raise bad_request("画像が見つかりません")
