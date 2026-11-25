"""Экспорт календаря в ICS, чтобы файл можно было открыть отдельно от панели."""

from __future__ import annotations

from nko.policy import esc


def render_ics(events: list[dict], org_name: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Zlatahelp//NKO//RU",
        f"X-WR-CALNAME:{_ics(org_name)}",
    ]
    for event in events:
        if event.get("status") == "cancelled":
            continue
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event['id']}@zlatahelp",
                f"DTSTART:{_stamp(event['start_at'])}",
                f"DTEND:{_stamp(event['end_at'])}",
                f"SUMMARY:{_ics(event['title'])}",
                f"LOCATION:{_ics(event.get('place') or '')}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def render_ics_html(events: list[dict]) -> str:
    rows = "".join(
        f"<li>{esc(event['start_at'])} — {esc(event['title'])}</li>"
        for event in events
        if event.get("status") != "cancelled"
    )
    return f"<!DOCTYPE html><html lang='ru'><meta charset='utf-8'><title>Календарь</title><h1>Календарь</h1><ul>{rows}</ul></html>"


def _stamp(value: str) -> str:
    return value.replace("-", "").replace(":", "")[:15]


def _ics(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", " ").replace(",", "\\,").replace(";", "\\;")
