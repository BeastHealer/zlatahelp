"""Короткий прогон поручений руководителя. Печатает ленту, как её увидят в Telegram."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

from nko.assistant import Assistant
from nko.browser import Browser
from nko.catalog import LETTER_SAMPLE
from nko.config import Settings
from nko.db import Database
from nko.models import Incoming


def say(title: str, replies) -> None:
    print(f"\n== {title}")
    for item in replies:
        label = {"progress": "ход", "waiting": "жду вас", "result": "итог", "error": "сбой", "user": "вы"}.get(item.kind, item.kind)
        print(f"[{label}] {item.text}\n")


def main() -> None:
    # Один и тот же файл базы: иначе календарь и Notion живут в двух копиях.
    root = Path(mkdtemp(prefix="zlata-demo-"))
    database = Database(root / "demo.db")
    settings = Settings(
        data_dir=root,
        host="127.0.0.1",
        port=8090,
        public_base_url="http://127.0.0.1:8090",
        owner_id="owner",
        org_name="АНО «Злата»",
        today="2026-11-25",
        telegram_token="",
        telegram_chat_id="",
        llm_provider="demo",
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        llm_model="gpt-4o-mini",
        notion_mode="mirror",
        notion_token="",
        notion_database_id="",
        search_engine="catalog",
    )
    assistant = Assistant(settings, database, Browser(database, settings.public_base_url))
    say("гранты", assistant.handle(Incoming(user_id="owner", text="Найди гранты на цифровизацию до 500000 и запиши подборку в Notion. Я в Казани.")))
    say("подтверждение Notion", assistant.handle(Incoming(user_id="owner", text="да")))
    say("календарь", assistant.handle(Incoming(user_id="owner", text="Поставь встречу правления в четверг в 11.")))
    say("подтверждение календаря", assistant.handle(Incoming(user_id="owner", text="да")))
    say("письмо", assistant.handle(Incoming(user_id="owner", text="Разбери письмо и подготовь ответ", document_text=LETTER_SAMPLE)))
    say("письмо не отправляем", assistant.handle(Incoming(user_id="owner", text="нет")))
    say("отчётность", assistant.handle(Incoming(user_id="owner", text="Что изменилось в отчётности НКО в 2026?")))
    say("база", assistant.handle(Incoming(user_id="owner", text="Кто ведёт волонтёров в Казани?")))
    print(f"\nБаза показа: {root}")


if __name__ == "__main__":
    main()
