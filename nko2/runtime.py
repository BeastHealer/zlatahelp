"""Панель, Telegram и чат VK. Сбой одного канала не гасит остальные."""

from __future__ import annotations

import asyncio

import uvicorn

from nko2.assistant import Assistant
from nko2.config import Settings


async def serve(app, settings: Settings, assistant: Assistant) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host=settings.host, port=settings.port, loop="asyncio"))
    tasks: list[asyncio.Task] = []
    if settings.telegram_token:
        from nko2.telegram_bot import polling_loop

        tasks.append(asyncio.create_task(polling_loop(settings, assistant)))
    if settings.vk_token and settings.vk_group_id:
        from nko2.vk_bot import polling_loop as vk_loop

        tasks.append(asyncio.create_task(vk_loop(settings, assistant)))
    try:
        await server.serve()
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
