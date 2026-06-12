"""簡易 Playground UI（GET /playground）。

依存ゼロで「画像を投げて facing を見る → 間違いを label として登録」までを
ブラウザ単体で試すための一枚 HTML。認証は不要だが、API 呼び出しには
画面上で入力した project / API キーが使われる（X-API-Key ヘッダ）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

_TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/playground", response_class=HTMLResponse)
def playground_home(request: Request):
    return _TEMPLATES.TemplateResponse(request, "playground.html", {})
