"""Лента показа второй версии."""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

from nko2.assistant import Assistant
from nko2.config import Settings
from nko2.db import Database
from nko2.models import Incoming


def say(title: str, replies) -> None:
    print(f"\n== {title}")
    for item in replies:
        label = {"waiting": "жду вас", "result": "итог", "error": "сбой", "progress": "ход"}.get(item.kind, item.kind)
        print(f"[{label}] {item.text}\n")


def main() -> None:
    root = Path(mkdtemp(prefix="zlata2-"))
    settings = Settings(
        data_dir=root,
        host="127.0.0.1",
        port=8091,
        public_base_url="http://127.0.0.1:8091",
        owner_id="owner",
        org_name="АНО «Злата»",
        leader_name="Злата",
        today="2026-11-25",
        telegram_token="",
        telegram_chat_id="",
        telegram_channel_id="",
        llm_provider="demo",
        llm_api_key="",
        llm_base_url="https://gigachat.devices.sberbank.ru/api/v1",
        llm_model="GigaChat",
        yonote_mode="mirror",
        yonote_token="",
        yonote_base_url="https://app.yonote.ru/api",
        yonote_collection_id="",
        vk_token="",
        vk_group_id="",
        imap_host="",
        imap_user="",
        imap_password="",
        search_engine="catalog",
        keywords="цифровизация, партнёрство",
    )
    assistant = Assistant(settings, Database(root / "demo.db"))
    say("сводка", assistant.handle(Incoming(user_id="owner", text="Собери, что нового в Yonote, Telegram, VK и почте")))
    say("отчёт", assistant.handle(Incoming(user_id="owner", text="Собери еженедельный отчёт: что сделано и что в планах")))
    say("запись отчёта", assistant.handle(Incoming(user_id="owner", text="да")))
    say("возможности", assistant.handle(Incoming(user_id="owner", text="Найди гранты и мероприятия по словам цифровизация и партнёрство")))
    say("не записывать подборку", assistant.handle(Incoming(user_id="owner", text="нет")))
    say("анонс", assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK")))
    say("публикация", assistant.handle(Incoming(user_id="owner", text="да")))
    say("напоминание", assistant.handle(Incoming(user_id="owner", text="напомни завтра в 10 о вебинаре")))
    print(f"\nБаза показа: {root}")


if __name__ == "__main__":
    main()
