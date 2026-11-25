"""Сообщения владельца."""

from __future__ import annotations

from dataclasses import dataclass


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
