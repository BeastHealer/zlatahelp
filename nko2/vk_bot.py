"""Чат сообщества VK. Тот же ассистент, что и панель. Сеть VK не обязательна для страницы /vk."""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

from nko2.assistant import Assistant
from nko2.config import Settings
from nko2.models import Incoming, Outbound

logger = logging.getLogger(__name__)

API = "https://api.vk.com/method/"


def vk_call(settings: Settings, method: str, **params: object) -> dict:
    payload = {key: value for key, value in params.items() if value is not None}
    payload["access_token"] = settings.vk_token
    payload["v"] = "5.199"
    response = httpx.post(f"{API}{method}", data=payload, timeout=25)
    response.raise_for_status()
    body = response.json()
    error = body.get("error")
    if error:
        raise ValueError(str(error.get("error_code") or "vk"))
    data = body.get("response")
    return data if isinstance(data, dict) else {"value": data}


def long_poll_server(settings: Settings) -> dict:
    group_id = str(settings.vk_group_id).lstrip("-")
    return vk_call(settings, "groups.getLongPollServer", group_id=group_id)


def long_poll_check(server: str, key: str, ts: str) -> dict:
    response = httpx.get(server, params={"act": "a_check", "key": key, "ts": ts, "wait": 25}, timeout=35)
    response.raise_for_status()
    body = response.json()
    return body if isinstance(body, dict) else {}


def send_message(settings: Settings, peer_id: int, text: str) -> None:
    for start in range(0, max(len(text), 1), 3500):
        chunk = text[start : start + 3500]
        vk_call(
            settings,
            "messages.send",
            peer_id=peer_id,
            message=chunk,
            random_id=random.randint(1, 2_000_000_000),
        )


def format_reply(item: Outbound) -> str:
    prefix = {"progress": "▶ ", "waiting": "⏸ ", "error": "⚠ ", "result": ""}.get(item.kind, "")
    return (prefix + item.text).strip()


def handle_vk_message(settings: Settings, assistant: Assistant, from_id: int, text: str) -> list[str]:
    if not settings.vk_user_id or str(from_id) != str(settings.vk_user_id):
        return [f"Доступ только у руководителя. Идентификатор VK: {from_id}."]
    replies = assistant.handle(Incoming(user_id=settings.owner_id, text=text, source="vk"))
    return [format_reply(item) for item in replies if item.text.strip()]


def apply_updates(settings: Settings, assistant: Assistant, updates: list) -> None:
    for update in updates:
        if not isinstance(update, dict) or update.get("type") != "message_new":
            continue
        message = (update.get("object") or {}).get("message") or {}
        if not isinstance(message, dict):
            continue
        from_id = int(message.get("from_id") or 0)
        if from_id <= 0:
            continue
        peer_id = int(message.get("peer_id") or from_id)
        for reply in handle_vk_message(settings, assistant, from_id, str(message.get("text") or "")):
            send_message(settings, peer_id, reply)


async def polling_loop(settings: Settings, assistant: Assistant, stop: asyncio.Event | None = None) -> None:
    """Long Poll сообщества. Если VK молчит, панель и страница /vk продолжают работать."""
    stop = stop or asyncio.Event()
    delay = 5
    server = ""
    key = ""
    ts = ""
    while not stop.is_set():
        try:
            if not server:
                info = await asyncio.to_thread(long_poll_server, settings)
                server = str(info.get("server") or "")
                key = str(info.get("key") or "")
                ts = str(info.get("ts") or "")
                if not server or not key:
                    raise ValueError("vk-long-poll")
            payload = await asyncio.to_thread(long_poll_check, server, key, ts)
            failed = payload.get("failed")
            if failed == 1:
                ts = str(payload.get("ts") or ts)
                continue
            if failed in (2, 3):
                server = ""
                continue
            ts = str(payload.get("ts") or ts)
            await asyncio.to_thread(apply_updates, settings, assistant, payload.get("updates") or [])
            delay = 5
        except asyncio.CancelledError:
            raise
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("VK недоступен (%s). Панель и чат на /vk продолжают работу.", exc.__class__.__name__)
            server = ""
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                delay = min(delay * 2, 60)
