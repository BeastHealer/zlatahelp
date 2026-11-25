"""Сообщения владельца и результат открытия страницы."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Incoming:
    user_id: str
    text: str = ""
    voice_transcript: str = ""
    image_note: str = ""
    document_name: str = ""
    document_text: str = ""
    source: str = "api"


@dataclass
class Outbound:
    kind: str
    text: str
    task_id: str = ""


@dataclass
class PageResult:
    ok: bool
    url: str
    title: str = ""
    text: str = ""
    needs_user: bool = False
    reason: str = ""
    facts: list[dict] = field(default_factory=list)
