"""Панель руководителя и учебные страницы источников."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from nko.assistant import Assistant
from nko.calendar_io import render_ics_html
from nko.catalog import notion_html, notion_index_html, outbox_html, page_html, resolve
from nko.models import Incoming

DASHBOARD = Path(__file__).resolve().parent / "static" / "dashboard.html"


class MessageIn(BaseModel):
    text: str = ""
    voice_transcript: str = ""
    image_note: str = ""
    document_name: str = ""
    document_text: str = ""


class MessageOut(BaseModel):
    replies: list[dict] = Field(default_factory=list)
    state: dict


def create_app(assistant: Assistant) -> FastAPI:
    app = FastAPI(title="Zlatahelp", version="1.0.0")

    @app.get("/health")
    def health() -> dict:
        return {
            "ok": True,
            "provider": assistant.settings.llm_provider,
            "notion": assistant.settings.notion_mode,
            "search": assistant.settings.search_engine,
        }

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD.read_text(encoding="utf-8")

    @app.get("/api/state")
    def state() -> dict:
        return assistant.snapshot()

    @app.post("/api/message", response_model=MessageOut)
    def message(body: MessageIn) -> MessageOut:
        incoming = Incoming(
            user_id=assistant.settings.owner_id,
            text=body.text,
            voice_transcript=body.voice_transcript,
            image_note=body.image_note,
            document_name=body.document_name,
            document_text=body.document_text,
            source="dashboard",
        )
        replies = assistant.handle(incoming)
        return MessageOut(
            replies=[{"kind": item.kind, "text": item.text, "task_id": item.task_id} for item in replies],
            state=assistant.snapshot(),
        )

    @app.post("/api/cancel", response_model=MessageOut)
    def cancel() -> MessageOut:
        replies = assistant.cancel()
        return MessageOut(
            replies=[{"kind": item.kind, "text": item.text, "task_id": item.task_id} for item in replies],
            state=assistant.snapshot(),
        )

    @app.get("/sources/{source}", response_class=HTMLResponse)
    def source(source: str) -> str:
        return _source(f"/sources/{source}")

    @app.get("/sources/{source}/{slug}", response_class=HTMLResponse)
    def source_page(source: str, slug: str) -> str:
        return _source(f"/sources/{source}/{slug}")

    @app.get("/notion", response_class=HTMLResponse)
    def notion_index() -> str:
        return notion_index_html(assistant.db.notion_pages())

    @app.get("/notion/{page_id}", response_class=HTMLResponse)
    def notion_page(page_id: str) -> str:
        page = assistant.db.notion_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="Страницы нет")
        return notion_html(page)

    @app.get("/outbox/{approval_id}", response_class=HTMLResponse)
    def outbox(approval_id: str) -> str:
        try:
            approval = assistant.db.get_approval(approval_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Письма нет") from exc
        return outbox_html(approval)

    @app.get("/calendar", response_class=HTMLResponse)
    def calendar() -> str:
        return render_ics_html(assistant.db.calendar_events())

    @app.get("/calendar.ics")
    def calendar_file() -> Response:
        assistant._write_ics()
        return Response(assistant.settings.ics_path.read_text(encoding="utf-8"), media_type="text/calendar; charset=utf-8")

    return app


def _source(path: str) -> str:
    page = resolve(path)
    if page is None:
        raise HTTPException(status_code=404, detail="Источник не найден")
    return page_html(page)
