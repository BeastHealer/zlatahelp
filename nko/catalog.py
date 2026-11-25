"""Учебные источники НКО. Цифры зафиксированы, чтобы расхождения не зависели от вёрстки живых сайтов."""

from __future__ import annotations

from nko.policy import esc, money, ru_date

GRANTS: list[dict] = [
    {
        "id": "presidential-digital",
        "family": "presidential-digital",
        "source": "president-grants",
        "source_title": "Фонд президентских грантов",
        "title": "Цифровые сервисы НКО",
        "amount": 500_000,
        "deadline": "2026-03-15",
        "region": "Россия",
        "fit": "цифровизация",
        "path": "/sources/president-grants/presidential-digital",
    },
    {
        "id": "presidential-digital-agg",
        "family": "presidential-digital",
        "source": "grants-aggregator",
        "source_title": "Агрегатор грантов",
        "title": "Цифровые сервисы НКО",
        "amount": 450_000,
        "deadline": "2026-03-01",
        "region": "Россия",
        "fit": "цифровизация",
        "path": "/sources/grants-aggregator/presidential-digital",
    },
    {
        "id": "rt-digital",
        "family": "rt-digital",
        "source": "tatarstan-nko",
        "source_title": "Портал НКО Татарстана",
        "title": "Субсидия на цифровизацию",
        "amount": 300_000,
        "deadline": "2026-02-20",
        "region": "Татарстан",
        "fit": "цифровизация",
        "path": "/sources/tatarstan-nko/rt-digital",
    },
    {
        "id": "kids-moscow",
        "family": "kids-moscow",
        "source": "president-grants",
        "source_title": "Фонд президентских грантов",
        "title": "Детские дворы",
        "amount": 800_000,
        "deadline": "2026-04-01",
        "region": "Москва",
        "fit": "дети",
        "path": "/sources/president-grants/kids-moscow",
    },
]

FAILED_GRANT = {
    "source_title": "Региональный фонд поддержки",
    "path": "/sources/regional-fund",
    "reason": "сайт вернул 503",
}

ARTICLES: list[dict] = [
    {
        "id": "minjust-2026",
        "source_title": "Минюст",
        "claim": "С 1 июля 2026 года форма ОН0001 принимается только в электронном виде.",
        "path": "/sources/minjust/on0001",
        "ok": True,
    },
    {
        "id": "consultant-2026",
        "source_title": "КонсультантПлюс, обзор",
        "claim": "С 1 сентября 2026 года форма ОН0001 принимается только в электронном виде.",
        "path": "/sources/consultant/on0001",
        "ok": True,
    },
    {
        "id": "digest-down",
        "source_title": "Сводка НКО",
        "claim": "",
        "path": "/sources/nko-digest",
        "ok": False,
        "reason": "шлюз не ответил за 15 секунд",
    },
]

LETTER_SAMPLE = (
    "Тема: Софинансирование по договору 14\n"
    "Просим подтвердить софинансирование 180000 рублей по договору 14 до пятницы.\n"
)

CONTACTS: list[dict] = [
    {"name": "Айгуль Сафина", "city": "Казань", "role": "волонтёры", "phone": "+7 900 000-00-01"},
    {"name": "Игорь Петров", "city": "Москва", "role": "гранты", "phone": "+7 900 000-00-02"},
    {"name": "Мария Лебедева", "city": "Казань", "role": "бухгалтерия", "phone": "+7 900 000-00-03"},
]

CONTRACT = {
    "number": "14",
    "partner": "Фонд «Город»",
    "amount": 120_000,
    "title": "Договор 14 с фондом «Город»",
}

WORKSPACE_TEXT = (
    "Рабочее пространство АНО «Злата». "
    "Базы: Гранты, Контакты, Календарь, Протоколы. Сессия открыта в этом профиле."
)


def grants_for(focus: str) -> list[dict]:
    return [item for item in GRANTS if item["fit"] == focus]


def _grant_text(item: dict) -> str:
    return (
        f"{item['source_title']}. {item['title']}. "
        f"Сумма {money(item['amount'])} ₽. Дедлайн {ru_date(item['deadline'])}. "
        f"Регион: {item['region']}."
    )


def resolve(path: str) -> dict | None:
    for item in GRANTS:
        if item["path"] == path:
            return {"ok": True, "title": item["title"], "text": _grant_text(item), "facts": [item]}
    if path == FAILED_GRANT["path"]:
        return {
            "ok": False,
            "title": FAILED_GRANT["source_title"],
            "text": "",
            "reason": FAILED_GRANT["reason"],
            "facts": [],
        }
    for item in ARTICLES:
        if item["path"] == path:
            if not item["ok"]:
                return {"ok": False, "title": item["source_title"], "text": "", "reason": item["reason"], "facts": []}
            return {"ok": True, "title": item["source_title"], "text": item["claim"], "facts": [item]}
    if path == "/sources/notion/login":
        return {
            "ok": False,
            "title": "Вход в Notion",
            "text": "",
            "reason": "Страница просит вход. Сессию может открыть только владелец.",
            "needs_user": True,
            "facts": [],
        }
    if path == "/sources/notion/workspace":
        return {"ok": True, "title": "Notion", "text": WORKSPACE_TEXT, "facts": []}
    return None


def page_html(page: dict) -> str:
    title = esc(page.get("title") or "Источник")
    if not page.get("ok", True):
        reason = esc(page.get("reason") or "Страница не открылась")
        return f"<!DOCTYPE html><html lang='ru'><meta charset='utf-8'><title>{title}</title><h1>{title}</h1><p>{reason}</p></html>"
    body = esc(page.get("text") or "")
    return f"<!DOCTYPE html><html lang='ru'><meta charset='utf-8'><title>{title}</title><h1>{title}</h1><p>{body}</p></html>"


def notion_html(page: dict) -> str:
    title = esc(page["title"])
    body = esc(page["body"])
    remote = esc(page.get("remote_id") or "локальное зеркало")
    return (
        "<!DOCTYPE html><html lang='ru'><meta charset='utf-8'>"
        f"<title>{title}</title><h1>{title}</h1>"
        f"<p>Квитанция зеркала: {esc(page['id'])}. Notion id: {remote}.</p>"
        f"<pre>{body}</pre></html>"
    )


def notion_index_html(pages: list[dict]) -> str:
    if not pages:
        items = "<li>Пока пусто</li>"
    else:
        items = "".join(f"<li><a href='/notion/{esc(item['id'])}'>{esc(item['title'])}</a></li>" for item in pages)
    return f"<!DOCTYPE html><html lang='ru'><meta charset='utf-8'><title>Notion</title><h1>Зеркало Notion</h1><ul>{items}</ul></html>"


def outbox_html(approval: dict) -> str:
    payload = approval.get("payload") or {}
    title = esc(payload.get("subject") or approval.get("kind") or "Исходящее")
    body = esc(payload.get("body") or "")
    receipt = esc(approval.get("receipt") or "")
    status = esc(approval.get("status") or "")
    return (
        "<!DOCTYPE html><html lang='ru'><meta charset='utf-8'>"
        f"<title>{title}</title><h1>{title}</h1>"
        f"<p>Статус: {status}. Квитанция: {receipt}.</p><pre>{body}</pre></html>"
    )
