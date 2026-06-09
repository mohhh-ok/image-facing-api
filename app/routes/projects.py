"""POST /v1/projects（作成・キー発行）/ GET /v1/projects（一覧）。いずれも admin 認証。"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from ..auth import generate_api_key, hash_api_key, require_admin, verify_same_origin
from ..errors import bad_request
from ..models import ProjectCreate, ProjectCreated, ProjectSummary

router = APIRouter(prefix="/v1/projects")


@router.post(
    "",
    response_model=ProjectCreated,
    dependencies=[Depends(require_admin), Depends(verify_same_origin)],
)
def create_project(body: ProjectCreate, request: Request) -> ProjectCreated:
    db = request.app.state.db
    if db.get_project(body.name) is not None:
        raise bad_request(f"project '{body.name}' は既に存在します")

    api_key = generate_api_key()
    try:
        row = db.create_project(body.name, body.description, hash_api_key(api_key))
    except sqlite3.IntegrityError as exc:  # name UNIQUE 競合
        raise bad_request(f"project '{body.name}' は既に存在します") from exc

    return ProjectCreated(project=row["name"], api_key=api_key, created_at=row["created_at"])


@router.post(
    "/{name}/rotate_key",
    response_model=ProjectCreated,
    dependencies=[Depends(require_admin), Depends(verify_same_origin)],
)
def rotate_key(name: str, request: Request) -> ProjectCreated:
    """既存 project の API キーを再発行する（旧キーは即無効・admin 認証）。"""
    db = request.app.state.db
    row = db.get_project(name)
    if row is None:
        raise bad_request(f"project '{name}' は存在しません")
    api_key = generate_api_key()
    db.update_project_api_key(name, hash_api_key(api_key))
    return ProjectCreated(project=name, api_key=api_key, created_at=row["created_at"])


@router.get("", response_model=list[ProjectSummary], dependencies=[Depends(require_admin)])
def list_projects(request: Request) -> list[ProjectSummary]:
    db = request.app.state.db
    out: list[ProjectSummary] = []
    for row in db.list_projects():
        name = row["name"]
        out.append(
            ProjectSummary(
                project=name,
                description=row["description"],
                sample_count=db.count_samples(name, include_flip=True),
                label_count=db.count_samples(name, include_flip=False),
                k=row["k"],
                created_at=row["created_at"],
            )
        )
    return out
