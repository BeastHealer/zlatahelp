"""Панель, восстановление незавершённых задач и Telegram, если задан токен."""

from __future__ import annotations

import asyncio

import uvicorn

from nko.api import create_app
from nko.assistant import Assistant
from nko.browser import Browser
from nko.config import load_settings
from nko.db import Database
from nko.llm import LlmClient


def build() -> tuple[object, Assistant]:
    settings = load_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    database = Database(settings.db_path)
    browser = Browser(database, settings.public_base_url)
    llm = LlmClient(settings) if settings.llm_provider != "demo" and settings.llm_api_key else None
    assistant = Assistant(settings, database, browser, llm)
    assistant.recover()
    return settings, assistant


def main() -> None:
    settings, assistant = build()
    app = create_app(assistant)
    if settings.telegram_token:
        from nko.telegram_bot import serve

        asyncio.run(serve(app, settings, assistant))
        return
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
