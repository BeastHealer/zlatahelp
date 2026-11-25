"""Разбор коротких реплик владельца. Правила явные, чтобы показ не зависел от модели."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from nko.models import Incoming

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

CITIES = (
    ("казани", "Казань"),
    ("казань", "Казань"),
    ("москве", "Москва"),
    ("москва", "Москва"),
    ("татарстан", "Татарстан"),
)


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


def is_resume(text: str) -> bool:
    value = normalize(text)
    return any(word in value for word in ("готово", "вошел", "вошла", "продолжай"))


def detect_skill(text: str) -> str:
    value = normalize(text)
    if any(word in value for word in ("договор", "софинанс", "письм")):
        return "letter"
    if "напомни" in value and "встреч" not in value:
        return "reminder"
    if "грант" in value or "субсид" in value:
        return "grant"
    if any(word in value for word in ("встреч", "календар", "правлен", "созвон")):
        return "calendar"
    if "http://" in value or "https://" in value:
        return "page"
    if any(word in value for word in ("отчетн", "изменил", "новост", "суммир", "исслед")):
        return "research"
    if any(word in value for word in ("волонт", "контакт", "кто вед", "сотрудник")):
        return "base"
    if any(word in value for word in ("кабинет", "авторизац", "войти в notion")):
        return "login"
    return "general"


def parse_focus(text: str) -> str:
    value = normalize(text)
    if "цифров" in value:
        return "цифровизация"
    if "дет" in value:
        return "дети"
    if "эколог" in value:
        return "экология"
    if "образован" in value:
        return "образование"
    return ""


def parse_ceiling(text: str) -> int | None:
    match = re.search(r"до\s+(\d[\d\s]*?)(?:\s*(тыс(?:яч|\.)?))?(?=$|[^\d])", normalize(text))
    if match is None:
        return None
    number = int(match.group(1).replace(" ", ""))
    if match.group(2):
        number *= 1000
    return number


def parse_city(text: str) -> str:
    value = normalize(text)
    for needle, title in CITIES:
        if needle in value:
            return title
    return ""


def parse_weekday(text: str) -> int | None:
    value = normalize(text)
    for needle, index in WEEKDAYS:
        if needle in value:
            return index
    return None


def parse_hour(text: str) -> int | None:
    match = re.search(r"\bв\s+(\d{1,2})(?!\d)", normalize(text))
    if match is None:
        return None
    hour = int(match.group(1))
    if 0 <= hour <= 23:
        return hour
    return None


def next_weekday(today: date, weekday: int) -> date:
    delta = (weekday - today.weekday()) % 7
    return today + timedelta(days=delta)


def clock_label(moment: datetime) -> str:
    return f"{WEEKDAY_NAMES[moment.weekday()]} {moment.strftime('%d.%m.%Y %H:%M')}"


def parse_when(text: str, today: date) -> tuple[datetime, datetime] | None:
    weekday = parse_weekday(text)
    if weekday is None:
        return None
    hour = parse_hour(text)
    if hour is None:
        hour = 11
    start = datetime.combine(next_weekday(today, weekday), time(hour, 0))
    return start, start + timedelta(hours=1)


def parse_reminder(text: str, today: date) -> tuple[str, str] | None:
    value = normalize(text)
    if "напомни" not in value:
        return None
    if "завтра" not in value and parse_weekday(text) is None:
        return None
    if "завтра" in value:
        day = today + timedelta(days=1)
    else:
        day = next_weekday(today, parse_weekday(text) or 0)
    hour = parse_hour(text)
    if hour is None:
        hour = 9
    note = text.strip()
    note = re.sub(r"(?i)^напомни(те)?", "", note).strip(" ,.")
    note = re.sub(r"(?i)^завтра", "", note).strip(" ,.")
    note = re.sub(r"(?i)^в\s+\d{1,2}", "", note).strip(" ,.")
    due = datetime.combine(day, time(hour, 0)).isoformat(timespec="seconds")
    return due, note or text.strip()


def find_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>]+", text)


def find_contract_number(text: str) -> str:
    match = re.search(r"договор\w*\s+(\d+)", normalize(text))
    if match is None:
        return ""
    return match.group(1)


def find_large_amounts(text: str) -> list[int]:
    found: list[int] = []
    for match in re.finditer(r"\d[\d\s]{3,}", text):
        number = int(match.group().replace(" ", "").replace("\u00a0", ""))
        if number >= 1000:
            found.append(number)
    return found


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def iso_dt(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat(timespec="seconds")
