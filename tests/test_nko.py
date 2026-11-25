"""Сквозные поручения руководителя НКО без сети и без ключей."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from nko.access import allowed_chat
from nko.api import create_app
from nko.assistant import Assistant
from nko.browser import Browser
from nko.catalog import LETTER_SAMPLE
from nko.config import Settings
from nko.db import Database
from nko.models import Incoming


def make(tmp_path: Path, llm=None, **overrides) -> Assistant:
    settings = Settings(
        data_dir=tmp_path,
        host="127.0.0.1",
        port=8090,
        public_base_url="http://127.0.0.1:8090",
        owner_id="owner",
        org_name="АНО «Злата»",
        today="2026-11-25",
        telegram_token="",
        telegram_chat_id="100",
        llm_provider="demo",
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        llm_model="gpt-4o-mini",
        notion_mode="mirror",
        notion_token="",
        notion_database_id="",
        search_engine="catalog",
    )
    for key, value in overrides.items():
        object.__setattr__(settings, key, value)
    database = Database(tmp_path / "zlata.db")
    return Assistant(settings, database, Browser(database, settings.public_base_url), llm)


def text_of(replies) -> str:
    return "\n".join(item.text for item in replies)


def test_grant_keeps_conflict_and_waits_for_notion(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(
        assistant.handle(
            Incoming(
                user_id="x",
                voice_transcript="Найди гранты на цифровизацию до 500000 и запиши подборку в Notion.",
                image_note="афиша конкурса, Казань",
            )
        )
    )
    assert "500 000" in report
    assert "450 000" in report
    assert "300 000" in report
    assert "не выбираю одну цифру" in report
    assert "Региональный фонд поддержки не открылся" in report
    assert "ещё не создана" in report
    assert "Казань" in report
    assert "афиша" in report
    assert "800 000" not in report
    assert "Детские дворы" not in report
    assert assistant.db.count_approvals("sent") == 0
    assert assistant.db.notion_pages() == []
    assert assistant.db.memory_get("owner", "city") == "Казань"


def test_notion_page_is_written_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    client = TestClient(create_app(assistant))
    assistant.handle(Incoming(user_id="owner", text="Найди гранты на цифровизацию до 500000. Я в Казани."))
    assert "Пока пусто" in client.get("/notion").text
    sent = assistant.handle(Incoming(user_id="owner", text="да"))
    assert "один раз" in text_of(sent).lower()
    assert assistant.db.count_approvals("sent") == 1
    page = assistant.db.notion_pages()[0]
    body = client.get(f"/notion/{page['id']}")
    assert body.status_code == 200
    assert body.text.count("450 000") == 1
    assert body.text.count("500 000") == 1

    task = assistant.db.recent_tasks("owner")[0]
    approval = assistant.db.approvals_with_status("sent")[0]
    assistant._commit(task, approval)
    assert assistant.db.count_approvals("sent") == 1
    assert len(assistant.db.notion_pages()) == 1

    again = assistant.handle(Incoming(user_id="owner", text="Найди гранты на цифровизацию до 500000"))
    assert "уже есть" in text_of(again)
    assert len(assistant.db.notion_pages()) == 1


def test_calendar_conflict_is_written_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Поставь встречу правления в четверг в 11.")))
    assert "Попечительский совет" in report
    assert "27.11.2026" in report
    assert "ещё не записал" in report
    assert assistant.db.count_approvals("sent") == 0
    assistant.handle(Incoming(user_id="owner", text="да"))
    titles = [event["title"] for event in assistant.db.calendar_events()]
    assert titles.count("Встреча правления") == 1
    ics = assistant.settings.ics_path.read_text(encoding="utf-8")
    assert ics.count("SUMMARY:Встреча правления") == 1
    task = assistant.db.recent_tasks("owner")[0]
    assistant._commit(task, assistant.db.approvals_with_status("sent")[0])
    assert [event["title"] for event in assistant.db.calendar_events()].count("Встреча правления") == 1


def test_letter_amounts_stay_split_and_send_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    client = TestClient(create_app(assistant))
    report = text_of(
        assistant.handle(
            Incoming(user_id="owner", text="Разбери письмо и подготовь ответ", document_text=LETTER_SAMPLE)
        )
    )
    assert "180 000" in report
    assert "120 000" in report
    assert "не подставляю одну вместо другой" in report
    assert "ещё не отправлено" in report
    assistant.handle(Incoming(user_id="owner", text="да, отправить"))
    approval = assistant.db.approvals_with_status("sent")[0]
    page = client.get(f"/outbox/{approval['id']}")
    assert page.status_code == 200
    assert page.text.count("180 000") == 1
    assert assistant.db.count_approvals("sent") == 1
    again = assistant.handle(Incoming(user_id="owner", text="Разбери письмо и подготовь ответ", document_text=LETTER_SAMPLE))
    assert "уже уходил" in text_of(again)
    assert assistant.db.count_approvals("sent") == 1


def test_research_keeps_both_dates_and_failed_source(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Что изменилось в отчётности НКО в 2026?")))
    assert "1 июля 2026" in report
    assert "1 сентября 2026" in report
    assert "Сводка НКО не открылась" in report
    assert assistant.db.count_approvals("sent") == 0
    assert assistant.db.notion_pages() == []


def test_contacts_come_from_database(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Кто ведёт волонтёров в Казани?")))
    assert "Айгуль Сафина" in report
    assert "+7 900 000-00-01" in report
    assert "Игорь Петров" not in report


def test_external_page_is_not_invented(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Открой https://example.com/nko и кратко перескажи")))
    assert "example.com/nko" in report
    assert "не открывал" in report


def test_cancel_rejects_pending_write(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assistant.handle(Incoming(user_id="owner", text="Найди гранты на цифровизацию до 500000"))
    assistant.cancel()
    assert assistant.db.count_approvals("pending") == 0
    assert assistant.db.count_approvals("rejected") == 1
    assert assistant.db.notion_pages() == []


def test_recover_does_not_send(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assistant.handle(Incoming(user_id="owner", text="Найди гранты на цифровизацию до 500000"))
    task = assistant.db.recent_tasks("owner")[0]
    assistant.db.update_task(task["id"], status="running", phase="browse", wait_reason="")
    recovered = text_of(assistant.recover())
    assert "ещё не выполнялась" in recovered
    assert assistant.db.count_approvals("sent") == 0
    assert assistant.db.get_task(task["id"])["status"] == "waiting_user"


def test_login_waits_for_owner(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    first = text_of(assistant.handle(Incoming(user_id="owner", text="Открой кабинет Notion")))
    assert "не читаю" in first
    assert assistant.browser.state()["needs_user"] is True
    second = text_of(assistant.handle(Incoming(user_id="owner", text="готово")))
    assert "АНО «Злата»" in second
    assert assistant.browser.state()["needs_user"] is False


def test_reminder_fires_once(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    assistant.handle(Incoming(user_id="owner", text="напомни завтра в 9 проверить дедлайн"))
    pending = assistant.db.pending_reminders("owner")
    assert len(pending) == 1
    assistant.db.force_reminder_due(pending[0]["id"], "2000-01-01T00:00:00")
    first = text_of(assistant.poll())
    assert "проверить дедлайн" in first
    assert assistant.poll() == []


def test_model_cannot_drop_source_figures(tmp_path: Path) -> None:
    class FakeLlm:
        def rewrite(self, report: str, must_keep: list[str]) -> str:
            return "Коротко: грант подходящий, цифры опускаю."

    assistant = make(tmp_path, llm=FakeLlm(), llm_provider="openai", llm_api_key="test-key")
    report = text_of(assistant.handle(Incoming(user_id="owner", text="Найди гранты на цифровизацию до 500000")))
    assert "450 000" in report
    assert "500 000" in report
    assert "цифры опускаю" not in report


def test_owner_chat_only() -> None:
    settings = Settings(
        data_dir=Path("."),
        host="127.0.0.1",
        port=8090,
        public_base_url="http://127.0.0.1:8090",
        owner_id="owner",
        org_name="АНО «Злата»",
        today="2026-11-25",
        telegram_token="",
        telegram_chat_id="100",
        llm_provider="demo",
        llm_api_key="",
        llm_base_url="https://api.openai.com/v1",
        llm_model="gpt-4o-mini",
        notion_mode="mirror",
        notion_token="",
        notion_database_id="",
        search_engine="catalog",
    )
    assert allowed_chat(100, settings) is True
    assert allowed_chat(5, settings) is False
    assert allowed_chat(SimpleNamespace(id=100), Settings(**{**settings.__dict__, "telegram_chat_id": ""})) is False


def test_dashboard_grant_scenario(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    client = TestClient(create_app(assistant))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["provider"] == "demo"
    page = client.get("/")
    assert page.status_code == 200
    assert "Zlatahelp" in page.text
    response = client.post(
        "/api/message",
        json={"text": "Найди гранты на цифровизацию до 500000. Я в Казани."},
    )
    assert response.status_code == 200
    blob = " ".join(item["text"] for item in response.json()["replies"])
    assert "450 000" in blob
    assert response.json()["state"]["notion"] == []
