"""admin UI（Basic 認証・docs/admin.md）。

project を選び、サンプルの向きをワンクリックで修正する。修正は service.correct_facing を
通り、label と同じ経路で即インデックス反映される。flip 拡張行は既定で隠す。
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_admin, verify_same_origin
from ..deps import get_service
from ..errors import bad_request

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
    show_flip: bool = Form(False),
):
    svc = get_service(request)
    svc.correct_facing(project, sample_id, facing)
    url = f"/admin?project={project}"
    if show_flip:
        url += "&show_flip=true"
    return RedirectResponse(url=url, status_code=303)


@router.get("/image/{sha}")
def admin_image(request: Request, sha: str):
    if not _SHA_RE.match(sha):
        raise bad_request("不正な画像 ID です")
    path = request.app.state.settings.images_dir / f"{sha}.png"
    if not path.exists():
        raise bad_request("画像が見つかりません")
    return FileResponse(str(path), media_type="image/png")
