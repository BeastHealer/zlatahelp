"""Панель второй версии."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from nko2.assistant import Assistant
from nko2.models import Incoming
from nko2.textutil import esc

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
    app = FastAPI(title="Zlatahelp 2", version="2.0.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "version": "2", "yonote": assistant.settings.yonote_mode, "provider": assistant.settings.llm_provider}

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD.read_text(encoding="utf-8")

    @app.get("/api/state")
    def state() -> dict:
        return assistant.snapshot()

    @app.post("/api/message", response_model=MessageOut)
    def message(body: MessageIn) -> MessageOut:
        replies = assistant.handle(
            Incoming(
                user_id=assistant.settings.owner_id,
                text=body.text,
                voice_transcript=body.voice_transcript,
                image_note=body.image_note,
                document_name=body.document_name,
                document_text=body.document_text,
                source="dashboard",
            )
        )
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

    @app.get("/yonote", response_class=HTMLResponse)
    def yonote_index() -> str:
        pages = assistant.db.yonote_pages()
        if not pages:
            items = "<li>Пока пусто</li>"
        else:
            items = "".join(f"<li><a href='/yonote/{esc(item['id'])}'>{esc(item['title'])}</a></li>" for item in pages)
        return f"<!DOCTYPE html><html lang='ru'><meta charset='utf-8'><title>Yonote</title><h1>Зеркало Yonote</h1><ul>{items}</ul></html>"

    @app.get("/yonote/{page_id}", response_class=HTMLResponse)
    def yonote_page(page_id: str) -> str:
        page = assistant.db.yonote_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="Страницы нет")
        return (
            "<!DOCTYPE html><html lang='ru'><meta charset='utf-8'>"
            f"<title>{esc(page['title'])}</title><h1>{esc(page['title'])}</h1>"
            f"<p>Квитанция: {esc(page['id'])}. Yonote id: {esc(page.get('remote_id') or 'локальное зеркало')}.</p>"
            f"<pre>{esc(page['body'])}</pre></html>"
        )

    @app.get("/outbox/{approval_id}", response_class=HTMLResponse)
    def outbox(approval_id: str) -> str:
        try:
            approval = assistant.db.get_approval(approval_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Публикации нет") from exc
        payload = approval.get("payload") or {}
        body = payload.get("body") or ""
        return (
            "<!DOCTYPE html><html lang='ru'><meta charset='utf-8'>"
            f"<title>{esc(payload.get('subject') or 'Публикация')}</title>"
            f"<h1>{esc(payload.get('subject') or 'Публикация')}</h1>"
            f"<p>Статус: {esc(approval.get('status') or '')}. Квитанция: {esc(approval.get('receipt') or '')}.</p>"
            f"<pre>{esc(body)}</pre></html>"
        )

    return app
