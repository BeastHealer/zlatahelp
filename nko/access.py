"""Доступ к боту только у одного владельца."""

from __future__ import annotations

from nko.config import Settings


def allowed_chat(chat_id: object, settings: Settings) -> bool:
    if not settings.telegram_chat_id:
        return False
    return str(chat_id) == str(settings.telegram_chat_id)
