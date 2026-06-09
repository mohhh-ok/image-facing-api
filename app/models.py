"""Pydantic スキーマ（リクエスト/レスポンス・docs/api.md）。"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Facing = Literal["left", "right"]

PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class NeighborOut(BaseModel):
    sample_id: int
    facing: Facing
    similarity: float


class PredictResponse(BaseModel):
    facing: Facing
    confidence: float
    uncertain: bool
    neighbors: list[NeighborOut] | None = None
    model: str
    k: int


class LabelResponse(BaseModel):
    sample_id: int
    facing: Facing
    deduped: bool
    flip_added: bool
    project_size: int


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=63)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not PROJECT_NAME_RE.match(v):
            raise ValueError("project 名は英小文字・数字・ハイフンのみ（先頭は英数字）")
        return v


class ProjectCreated(BaseModel):
    project: str
    api_key: str
    created_at: str


class ProjectSummary(BaseModel):
    project: str
    description: str | None
    sample_count: int
    label_count: int  # flip 拡張を除いた人/取り込みラベル数
    k: int | None
    created_at: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    projects: int


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
