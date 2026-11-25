"""Тексты отчёта, поиска и постов. Расхождения источников не сглаживаются."""

from __future__ import annotations

from nko2.textutil import money, ru_date

SOURCE_LABEL = {"yonote": "Yonote", "telegram": "Telegram", "vk": "VK", "mail": "Почта"}


def render_digest(items: list[dict]) -> str:
    lines = ["Сводка входящих. Публикации и записи в Yonote отсюда сами не уходят."]
    for item in items:
        label = SOURCE_LABEL.get(item["source"], item["source"])
        if not item["ok"]:
            lines.append(f"{label}, {item['title'] or 'источник'}: не открылось, {item['reason']}.")
            continue
        lines.append(f"{label}, {item['title']}: {item['body']}")
    return "\n".join(lines)


def render_weekly(done: list[dict], planned: list[dict]) -> str:
    lines = ["Что сделано?"]
    for item in done:
        lines.append(f"- {ru_date(item['when_on'])} {item['title']}. {item['detail']}")
    lines.append("Что в планах?")
    for item in planned:
        lines.append(f"- {_when(item['when_on'])} {item['title']}. {item['detail']}")
    return "\n".join(lines)


def _when(value: str) -> str:
    if "T" not in value:
        return ru_date(value)
    day, clock = value.split("T", 1)
    return f"{ru_date(day)} {clock[:5]}"


def render_opportunities(items: list[dict], keywords: list[str]) -> tuple[str, list[str]]:
    lines = [f"Ищу по словам: {', '.join(keywords)}. Одну цифру вместо двух не выбираю."]
    tokens: list[str] = []
    opened = [item for item in items if item["ok"]]
    failed = [item for item in items if not item["ok"]]
    families: dict[str, list[dict]] = {}
    for item in opened:
        families.setdefault(item["title"] or item["source"], []).append(item)
    for group in families.values():
        amounts = {item["amount"] for item in group if item["amount"]}
        deadlines = {item["deadline"] for item in group if item["deadline"]}
        if len(group) > 1 and (len(amounts) > 1 or len(deadlines) > 1):
            lines.append("Это одна возможность в разных источниках. Суммы и дедлайны расходятся, я не выбираю одну цифру.")
        for item in group:
            if item["amount"]:
                amount = money(item["amount"])
                tokens.append(amount)
                lines.append(f"{item['source']}: «{item['title']}», {amount} ₽, дедлайн {ru_date(item['deadline'])}.")
            else:
                lines.append(f"{item['source']}: «{item['title']}», дедлайн {ru_date(item['deadline'])}.")
    for item in failed:
        lines.append(f"{item['source']} не открылся: {item['reason']}.")
    if not opened and not failed:
        lines.append("По этим словам в источниках пусто. Не подставляю грант из общих знаний.")
    return "\n".join(lines), tokens


def render_post(kind: str, fact: dict, leader: str, org: str) -> tuple[str, str]:
    sign = f"{leader}, {org}"
    if kind == "tip":
        telegram = (
            f"Коллеги, короткий совет.\n{fact['title']}: {fact['tip']}.\n{fact['line']}.\n{sign}"
        )
    elif kind == "story":
        telegram = (
            f"Коллеги, история с площадки.\n{fact['title']}: {fact['story']}.\n{fact['line']}.\n{sign}"
        )
    else:
        telegram = (
            f"Коллеги, анонс.\n{fact['when']}, {fact['place']}: «{fact['title']}».\n{fact['line']}.\n{sign}"
        )
    vk = "\n".join(telegram.split("\n")[:2] + [sign])
    return telegram, vk
