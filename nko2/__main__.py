"""Панель второй версии, Telegram и чат VK, если заданы токены."""

from __future__ import annotations

import asyncio

import uvicorn

from nko2.api import create_app
from nko2.assistant import Assistant
from nko2.config import load_settings
from nko2.db import Database


def build() -> tuple[object, Assistant]:
    settings = load_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    assistant = Assistant(settings, Database(settings.db_path))
    assistant.recover()
    return settings, assistant


def main() -> None:
    settings, assistant = build()
    app = create_app(assistant)
    if settings.telegram_token or (settings.vk_token and settings.vk_group_id):
        from nko2.runtime import serve

        asyncio.run(serve(app, settings, assistant))
        return
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
