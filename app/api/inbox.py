from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.db import get_connection
from app.inbox import build_inbox_view

router = APIRouter(tags=["inbox"])
DatabaseConnection = Annotated[sqlite3.Connection, Depends(get_connection)]
TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIRECTORY))


@router.get("/inbox", response_class=HTMLResponse)
def inbox(
    request: Request,
    connection: DatabaseConnection,
) -> HTMLResponse:
    view = build_inbox_view(connection)
    return templates.TemplateResponse(
        request=request,
        name="inbox.html",
        context={"view": view},
    )


@router.get("/inbox/current", response_class=HTMLResponse)
def inbox_current(
    request: Request,
    connection: DatabaseConnection,
) -> HTMLResponse:
    view = build_inbox_view(connection)
    return templates.TemplateResponse(
        request=request,
        name="partials/current_prompt.html",
        context={"request": request, "view": view},
    )


@router.get("/inbox/queue", response_class=HTMLResponse)
def inbox_queue(
    request: Request,
    connection: DatabaseConnection,
) -> HTMLResponse:
    view = build_inbox_view(connection)
    return templates.TemplateResponse(
        request=request,
        name="partials/queue_rail.html",
        context={"request": request, "view": view},
    )
