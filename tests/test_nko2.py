"""Вторая версия: Yonote, сводка, отчёт, поиск и публикация после «да»."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
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


def test_post_can_be_corrected_before_publish(tmp_path: Path) -> None:
    assistant = make(tmp_path)
    client = TestClient(create_app(assistant))
    assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK"))
    edited = "Коллеги, вебинар переносим на 3 декабря, 11:00."
    revised = text_of(assistant.handle(Incoming(user_id="owner", text=edited)))
    assert "Черновик заменила на ваш текст" in revised
    assert edited in revised
    assert "ещё не ушла" in revised
    assert assistant.db.count_approvals("sent") == 0
    draft = client.get("/api/state").json()["draft"]
    assert draft["text"] == edited
    published = assistant.handle(Incoming(user_id="owner", text="да"))
    assert "один раз" in text_of(published).lower()
    approval = assistant.db.approvals_with_status("sent")[0]
    page = client.get(f"/outbox/{approval['id']}")
    assert edited in page.text
    assert "Буду рада видеть вас на вебинаре" not in page.text
    assert client.get("/api/state").json()["draft"] is None


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
    chat = client.get("/vk")
    assert chat.status_code == 200
    assert "Отправить" in chat.text
    assert "/api/message" in chat.text


def test_vk_chat_accepts_only_the_owner(tmp_path: Path, monkeypatch) -> None:
    from nko2.vk_bot import apply_updates, handle_vk_message

    assistant = make(tmp_path, vk_user_id="42")
    denied = handle_vk_message(assistant.settings, assistant, 7, "Собери сводку")
    assert "Доступ только у руководителя" in denied[0]
    assert "7" in denied[0]
    assert assistant.db.recent_tasks("owner") == []

    sent: list[tuple[int, str]] = []
    monkeypatch.setattr("nko2.vk_bot.send_message", lambda _settings, peer, text: sent.append((peer, text)))
    apply_updates(
        assistant.settings,
        assistant,
        [
            {"type": "message_new", "object": {"message": {"from_id": -100, "peer_id": 42, "text": "служебное"}}},
            {
                "type": "message_new",
                "object": {"message": {"from_id": 42, "peer_id": 42, "text": "Собери, что нового в Yonote, Telegram, VK и почте"}},
            },
        ],
    )
    assert len(sent) == 1
    assert sent[0][0] == 42
    assert "Yonote" in sent[0][1]
    assert "группа не ответила" in sent[0][1]


def test_vk_polling_error_does_not_stop_the_loop(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    def down(_settings):
        calls["n"] += 1
        raise OSError("vk down")

    monkeypatch.setattr("nko2.vk_bot.long_poll_server", down)
    assistant = make(tmp_path, vk_token="vk", vk_group_id="1", vk_user_id="42")
    from nko2.vk_bot import polling_loop

    async def scenario() -> None:
        stop = asyncio.Event()

        async def runner() -> None:
            await polling_loop(assistant.settings, assistant, stop)

        task = asyncio.create_task(runner())
        for _ in range(50):
            if calls["n"] >= 1:
                break
            await asyncio.sleep(0.01)
        stop.set()
        await task

    asyncio.run(scenario())
    assert calls["n"] >= 1


def test_digest_weekly_and_post_continue_when_telegram_is_down(tmp_path: Path, monkeypatch) -> None:
    def down(*_args, **_kwargs):
        raise httpx.ConnectError("telegram")

    monkeypatch.setattr("nko2.assistant.telegram_reachable", down)
    monkeypatch.setattr("nko2.assistant.telegram_channel", down)
    vk_calls: list[str] = []
    monkeypatch.setattr("nko2.assistant.vk_wall", lambda _settings, message: vk_calls.append(message))
    assistant = make(tmp_path, telegram_token="token", telegram_channel_id="-100", vk_token="vk", vk_group_id="-1")

    report = text_of(assistant.handle(Incoming(user_id="owner", text="Собери, что нового в Yonote, Telegram, VK и почте")))
    assert "Telegram недоступен" in report
    assert "Yonote" in report
    assert "Почта" in report
    assert assistant.db.yonote_pages() == []

    weekly = text_of(assistant.handle(Incoming(user_id="owner", text="Собери еженедельный отчёт: что сделано и что в планах")))
    assert "Что сделано?" in weekly
    saved = assistant.handle(Incoming(user_id="owner", text="да"))
    assert "yonote-" in text_of(saved)
    assert len(assistant.db.yonote_pages()) == 1

    assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK"))
    published = text_of(assistant.handle(Incoming(user_id="owner", text="да")))
    assert "Telegram недоступен" in published
    assert "VK" in published
    assert "один раз" in published
    assert len(vk_calls) == 1
    assert assistant.db.count_approvals("sent") == 2
    again = assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK"))
    assert "уже опубликовано" in text_of(again).lower()
    assert len(vk_calls) == 1


def test_post_is_stored_when_only_telegram_is_down(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("nko2.assistant.telegram_channel", lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("telegram")))
    assistant = make(tmp_path, telegram_token="token", telegram_channel_id="-100")
    client = TestClient(create_app(assistant))
    assistant.handle(Incoming(user_id="owner", text="Напиши совет для Telegram и VK"))
    published = text_of(assistant.handle(Incoming(user_id="owner", text="да")))
    assert "Telegram недоступен" in published
    assert "исходящие" in published
    approval = assistant.db.approvals_with_status("sent")[0]
    page = client.get(f"/outbox/{approval['id']}")
    assert page.status_code == 200
    assert "короткий совет" in page.text.lower()


def test_vk_failure_does_not_get_a_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("nko2.assistant.vk_wall", lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("vk")))
    assistant = make(tmp_path, vk_token="vk", vk_group_id="-1")
    assistant.handle(Incoming(user_id="owner", text="Напиши анонс вебинара для Telegram и VK"))
    failed = text_of(assistant.handle(Incoming(user_id="owner", text="да")))
    assert "Квитанцию не ставлю" in failed
    assert assistant.db.count_approvals("sent") == 0
    assert assistant.db.count_approvals("pending") == 1


def test_telegram_polling_error_does_not_stop_the_loop(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    async def fail(self, *_args, **_kwargs):
        calls["n"] += 1
        raise OSError("telegram down")

    monkeypatch.setattr("nko2.telegram_bot.Dispatcher.start_polling", fail)
    assistant = make(tmp_path, telegram_token="123:ABC")
    from nko2.telegram_bot import polling_loop

    async def scenario() -> None:
        stop = asyncio.Event()

        async def runner() -> None:
            await polling_loop(assistant.settings, assistant, stop)

        task = asyncio.create_task(runner())
        for _ in range(50):
            if calls["n"] >= 1:
                break
            await asyncio.sleep(0.01)
        stop.set()
        await task

    asyncio.run(scenario())
    assert calls["n"] >= 1
