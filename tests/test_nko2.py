"""Вторая версия: Yonote, сводка, отчёт, поиск и публикация после «да»."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nko.access import allowed_chat
from nko2.api import create_app
from nko2.assistant import Assistant
from nko2.config import Settings
from nko2.db import Database
from nko2.models import Incoming


def make(tmp_path: Path, llm=None, **overrides) -> Assistant:
    settings = Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        port=8091,
        public_base_url="http://127.0.0.1:8091",
        owner_id="owner",
        org_name="АНО «Злата»",
        leader_name="Злата",
        today="2026-11-25",
        telegram_token="",
        telegram_chat_id="100",
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
    for key, value in overrides.items():
        object.__setattr__(settings, key, value)
    return Assistant(settings, Database(tmp_path / "zlata2.db"), llm)


def text_of(replies) -> str:
    return "\n".join(item.text for item in replies)


def test_digest_reads_sources_and_names_the_failed_one(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="x", text="Собери, что нового в Yonote, Telegram, VK и почте")))
    assert "Yonote" in report
    assert "Telegram" in report
    assert "Почта" in report
    assert "группа не ответила" in report
    assert "ещё не создана" not in report
    assert assistant.db.yonote_pages() == []
    assert assistant.db.count_approvals("sent") == 0


def test_weekly_report_is_saved_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    client = TestClient(create_app(assistant))
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Собери еженедельный отчёт: что сделано и что в планах")))
    assert "Что сделано?" in report
    assert "Что в планах?" in report
    assert "Встреча волонтёров" in report
    assert "Вебинар" in report
    assert "ещё не создана" in report
    assert assistant.db.yonote_pages() == []
    saved = assistant.handle(Incoming(user_id="owner", text="да"))
    assert "один раз" in text_of(saved).lower()
    page = assistant.db.yonote_pages()[0]
    body = client.get(f"/yonote/{page['id']}")
    assert body.status_code == 200
    assert body.text.count("Что сделано?") == 1
    again = assistant.handle(Incoming(user_id="owner", text="Собери еженедельный отчёт: что сделано и что в планах"))
    assert "уже есть" in text_of(again)
    assert len(assistant.db.yonote_pages()) == 1


def test_search_keeps_both_grant_figures(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Найди гранты и мероприятия по словам цифровизация и партнёрство")))
    assert "500 000" in report
    assert "450 000" in report
    assert "не выбираю одну цифру" in report
    assert "Портал субсидий не открылся" in report
    assert "Город" in report
    assert "ещё не создана" in report
    assert assistant.db.count_approvals("sent") == 0


def test_empty_keyword_is_not_invented(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Найди гранты по словам экология")))
    assert "пусто" in report
    assert "500 000" not in report


def test_posts_wait_for_approval_and_publish_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    client = TestClient(create_app(assistant))
    draft = text_of(assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK")))
    assert "Коллеги" in draft
    assert "02.12.2026" in draft
    assert "Буду рада видеть вас на вебинаре" in draft
    assert "осуществить" not in draft.lower()
    assert "ещё не ушла" in draft
    assert assistant.db.count_approvals("sent") == 0
    published = assistant.handle(Incoming(user_id="owner", text="да"))
    assert "один раз" in text_of(published).lower()
    approval = assistant.db.approvals_with_status("sent")[0]
    page = client.get(f"/outbox/{approval['id']}")
    assert page.text.count("Буду рада видеть вас на вебинаре") == 1
    again = assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK"))
    assert "уже опубликовано" in text_of(again).lower()
    assert assistant.db.count_approvals("sent") == 1


def test_story_and_tip_are_different_posts(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    story = text_of(assistant.handle(Incoming(user_id="owner", text="Напиши историю про волонтёров для Telegram и VK")))
    assert "40 семей" in story
    assert "ещё не ушла" in story
    assistant.handle(Incoming(user_id="owner", text="нет"))
    tip = text_of(assistant.handle(Incoming(user_id="owner", text="Напиши совет для Telegram и VK")))
    assert "короткий совет" in tip.lower()
    assert "40 семей" not in tip


def test_reminder_fires_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assistant.handle(Incoming(user_id="owner", text="напомни завтра в 10 о вебинаре"))
    pending = assistant.db.pending_reminders("owner")
    assert len(pending) == 1
    assert pending[0]["due_at"].startswith("2026-11-26T10:00:00")
    assistant.db.force_reminder_due(pending[0]["id"], "2000-01-01T00:00:00")
    assert "вебинар" in text_of(assistant.poll()).lower()
    assert assistant.poll() == []


def test_inbox_routine_sets_nearest_reminder(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Разбери входящие")))
    assert "Встреча правления" in report
    assert assistant.db.pending_reminders("owner")


def test_recover_does_not_publish(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK"))
    task = assistant.db.recent_tasks("owner")[0]
    assistant.db.update_task(task["id"], status="running", phase="work", wait_reason="")
    recovered = text_of(assistant.recover())
    assert "ещё не выполнялось" in recovered
    assert assistant.db.count_approvals("sent") == 0


def test_cancel_rejects_pending_post(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assistant.handle(Incoming(user_id="owner", text="Напиши совет для Telegram и VK"))
    assistant.cancel()
    assert assistant.db.count_approvals("pending") == 0
    assert assistant.db.count_approvals("rejected") == 1


def test_model_cannot_drop_grant_figures(tmp_path: Path) -> None:
    class FakeLlm:
        def rewrite(self, report: str, must_keep: list[str]) -> str:
            return "Коротко, без цифр."

    assistant = make(tmp_path, llm=FakeLlm(), llm_provider="gigachat", llm_api_key="test")
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Найди гранты по словам цифровизация")))
    assert "450 000" in report
    assert "без цифр" not in report


def test_external_page_is_not_opened_in_catalog(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Открой https://example.com/grant")))
    assert "example.com/grant" in report
    assert "не открывала" in report


def test_owner_only_and_dashboard(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assert allowed_chat(100, assistant.settings) is True
    assert allowed_chat(5, assistant.settings) is False
    client = TestClient(create_app(assistant))
    assert client.get("/health").json()["version"] == "2"
    page = client.get("/")
    assert "Yonote" in page.text
    response = client.post("/api/message", json={"text": "Собери, что нового в Yonote, Telegram, VK и почте"})
    assert "группа не ответила" in " ".join(item["text"] for item in response.json()["replies"])
