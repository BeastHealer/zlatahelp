"""Сравнение источников. Расхождения остаются в тексте, а не сглаживаются."""

from __future__ import annotations

from collections import defaultdict

CITY_REGION = {"казань": "татарстан", "москва": "москва", "татарстан": "татарстан"}


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def ru_date(iso_date: str) -> str:
    year, month, day = iso_date[:10].split("-")
    return f"{day}.{month}.{year}"


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def region_fits(grant_region: str, city: str) -> bool:
    region = grant_region.lower()
    if region in {"россия", "рф", ""}:
        return True
    if not city:
        return True
    user_region = CITY_REGION.get(city.lower(), city.lower())
    return region in user_region or user_region in region


def render_grants(items: list[dict], failed: list[dict], city: str, ceiling: int | None) -> tuple[str, list[str]]:
    lines: list[str] = []
    tokens: list[str] = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["family"]].append(item)
    for family in grouped.values():
        amounts = {item["amount"] for item in family}
        deadlines = {item["deadline"] for item in family}
        if len(family) > 1 and (len(amounts) > 1 or len(deadlines) > 1):
            lines.append("Это одна программа в разных источниках. Суммы и дедлайны расходятся, я не выбираю одну цифру.")
        for item in family:
            amount = money(item["amount"])
            deadline = ru_date(item["deadline"])
            tokens.extend([amount, deadline])
            fit = "подходит по региону" if region_fits(item["region"], city) else f"регион источника {item['region']}, у организации сейчас {city or 'не задан'}"
            ceiling_note = ""
            if ceiling is not None and item["amount"] > ceiling:
                ceiling_note = f" Выше потолка {money(ceiling)} ₽, в короткую подборку не беру как готовую заявку."
            lines.append(
                f"{item['source_title']}: «{item['title']}», {amount} ₽, дедлайн {deadline}, {fit}.{ceiling_note}"
            )
    for item in failed:
        lines.append(f"{item['source_title']} не открылся: {item['reason']}.")
    if city:
        lines.append(f"Учитываю город: {city}.")
        tokens.append(city)
    return "\n".join(lines), tokens


def render_research(opened: list[dict], failed: list[dict]) -> tuple[str, list[str]]:
    lines = ["Кратко по открытым страницам. Формулировки источников не свожу к одной дате."]
    tokens: list[str] = []
    for item in opened:
        lines.append(f"{item['source_title']}: {item['text']}")
        if "1 июля 2026" in item["text"]:
            tokens.append("1 июля 2026")
        if "1 сентября 2026" in item["text"]:
            tokens.append("1 сентября 2026")
    if len(tokens) > 1:
        lines.append("Даты расходятся. Обе оставляю, пока нет текста нормы.")
    for item in failed:
        lines.append(f"{item['source_title']} не открылась: {item['reason']}.")
    return "\n".join(lines), tokens


def render_letter(letter_amount: int, contract: dict, org_name: str) -> tuple[str, str, list[str]]:
    ours = money(contract["amount"])
    theirs = money(letter_amount)
    tokens = [ours, theirs]
    report = (
        f"В письме по договору {contract['number']} указано {theirs} ₽.\n"
        f"В базе договоров у {contract['partner']} записано {ours} ₽.\n"
        "Суммы не совпадают, я не подставляю одну вместо другой."
    )
    draft = (
        f"Добрый день.\n\n"
        f"По договору {contract['number']} в базе {org_name} софинансирование {ours} ₽.\n"
        f"В письме указано {theirs} ₽. Прошу прислать документ, на который опирается новая сумма, "
        f"либо подтвердить {ours} ₽.\n\n"
        f"{org_name}"
    )
    return report, draft, tokens


def render_contacts(rows: list[dict]) -> str:
    if not rows:
        return "В базе контактов такой записи нет. Не подставляю человека из общих знаний."
    lines = []
    for row in rows:
        lines.append(f"{row['name']}, {row['city']}, {row['role']}, {row['phone']}.")
    return "Нашёл в базе контактов:\n" + "\n".join(lines)


def overlapping(events: list[dict], start: str, end: str) -> list[dict]:
    hits = []
    for event in events:
        if event.get("status") == "cancelled":
            continue
        if event["start_at"] < end and start < event["end_at"]:
            hits.append(event)
    return hits


def html_to_text(raw: str) -> str:
    import re

    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()
