"""Разбор реплик второй версии."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from nko2.models import Incoming

WEEKDAYS = (
    ("понедельник", 0),
    ("вторник", 1),
    ("сред", 2),
    ("четверг", 3),
    ("пятниц", 4),
    ("суббот", 5),
    ("воскресень", 6),
)
WEEKDAY_NAMES = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def compose(message: Incoming) -> str:
    parts = [message.text, message.voice_transcript, message.image_note, message.document_text]
    return "\n".join(part.strip() for part in parts if part and part.strip())


def is_cancel(text: str) -> bool:
    return normalize(text) in {"стоп", "отмена", "/cancel", "останови", "остановись"}


def is_yes(text: str) -> bool:
    value = normalize(text)
    if value in {"да", "ок", "окей", "хорошо", "подтверждаю", "yes"}:
        return True
    return value.startswith("да,") or value.startswith("да ")


def is_no(text: str) -> bool:
    value = normalize(text)
    if value.startswith("да"):
        return False
    return value in {"нет", "не надо", "отмена отправки"} or value.startswith("нет")


def detect_skill(text: str) -> str:
    value = normalize(text)
    if any(word in value for word in ("еженедел", "что сделано", "что в планах")):
        return "weekly"
    if any(word in value for word in ("анонс", "совет", "истори", "пост ", "пост,", "для vk", "для вк", "для telegram", "для телеграм")):
        return "post"
    if value.startswith("пост") or " напиши пост" in f" {value}":
        return "post"
    if "напомни" in value:
        return "reminder"
    if any(word in value for word in ("грант", "мероприят", "партнер", "возможност", "по словам", "ключев")):
        return "opportunities"
    if "http://" in value or "https://" in value:
        return "page"
    if any(word in value for word in ("сводк", "входящ", "что нового", "рутин", "разбери", "собери")):
        return "digest"
    return "general"


def post_kind(text: str) -> str:
    value = normalize(text)
    if "истори" in value:
        return "story"
    if "совет" in value:
        return "tip"
    return "announce"


def parse_keywords(text: str, default: str) -> list[str]:
    value = normalize(text)
    match = re.search(r"по словам (.+)$", value)
    if match is None:
        match = re.search(r"ключевые слова[: ](.+)$", value)
    raw = match.group(1) if match else default
    parts = re.split(r",| и ", normalize(raw))
    words = []
    for part in parts:
        word = part.strip(" .")
        if word and word not in words:
            words.append(word)
    return words or [normalize(default)]


def parse_hour(text: str) -> int | None:
    match = re.search(r"\bв\s+(\d{1,2})(?!\d)", normalize(text))
    if match is None:
        return None
    hour = int(match.group(1))
    return hour if 0 <= hour <= 23 else None


def parse_weekday(text: str) -> int | None:
    value = normalize(text)
    for needle, index in WEEKDAYS:
        if needle in value:
            return index
    return None


def next_weekday(today: date, weekday: int) -> date:
    return today + timedelta(days=(weekday - today.weekday()) % 7)


def parse_reminder(text: str, today: date) -> tuple[str, str] | None:
    value = normalize(text)
    if "напомни" not in value:
        return None
    if "завтра" in value:
        day = today + timedelta(days=1)
    elif parse_weekday(text) is not None:
        day = next_weekday(today, parse_weekday(text) or 0)
    else:
        return None
    hour = parse_hour(text)
    if hour is None:
        hour = 9
    note = re.sub(r"(?i)^напомни(те)?", "", text.strip()).strip(" ,.")
    note = re.sub(r"(?i)^(завтра|в\s+\S+|в\s+\d{1,2})", "", note).strip(" ,.")
    note = re.sub(r"(?i)^в\s+\d{1,2}", "", note).strip(" ,.")
    due = datetime.combine(day, time(hour, 0)).isoformat(timespec="seconds")
    return due, note or text.strip()


def find_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>]+", text)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def ru_date(iso_date: str) -> str:
    year, month, day = iso_date[:10].split("-")
    return f"{day}.{month}.{year}"


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def esc(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
