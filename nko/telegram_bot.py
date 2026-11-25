"""Telegram одного владельца: текст, голос, фото и файл сходятся в одно поручение."""

from __future__ import annotations

import asyncio
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

from nko.access import allowed_chat
from nko.assistant import Assistant
from nko.config import Settings
from nko.media import describe_image, extract_document, transcribe
from nko.models import Incoming, Outbound


def _guard_text(chat_id: int) -> str:
    return (
        "Доступ только у руководителя. На сервере должен быть задан TELEGRAM_CHAT_ID. "
        f"Идентификатор этого чата: {chat_id}."
    )


async def _reply(message: Message, items: list[Outbound]) -> None:
    for item in items:
        prefix = {"progress": "▶ ", "waiting": "⏸ ", "error": "⚠ ", "result": ""}.get(item.kind, "")
        text = (prefix + item.text).strip()
        for start in range(0, len(text), 3900):
            await message.answer(text[start : start + 3900])


def build_dispatcher(settings: Settings, assistant: Assistant, bot: Bot) -> Dispatcher:
    dispatcher = Dispatcher()
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    async def allowed(message: Message) -> bool:
        if allowed_chat(message.chat.id, settings):
            return True
        await message.answer(_guard_text(message.chat.id))
        return False

    @dispatcher.message(F.text.startswith("/start"))
    async def start(message: Message) -> None:
        if not await allowed(message):
            return
        await message.answer(
            "Можно писать текстом, голосом, фото или файлом. "
            "Я показываю, что уже открыл и где жду «да». "
            "В Notion, календарь и почту ничего не уходит без подтверждения. "
            "«Стоп» останавливает текущую задачу. Команды: /tasks, /memory, /browser, /cancel."
        )

    @dispatcher.message(F.text.startswith("/tasks"))
    async def tasks(message: Message) -> None:
        if not await allowed(message):
            return
        rows = assistant.snapshot()["tasks"][:8]
        if not rows:
            await message.answer("Задач пока нет.")
            return
        lines = []
        for row in rows:
            line = f"{row['status']}: {row['title']}"
            if row.get("wait_reason"):
                line += f" — {row['wait_reason']}"
            lines.append(line)
        await message.answer("\n".join(lines))

    @dispatcher.message(F.text.startswith("/memory"))
    async def memory(message: Message) -> None:
        if not await allowed(message):
            return
        rows = assistant.snapshot()["memory"]
        if not rows:
            await message.answer("Память пуста.")
            return
        await message.answer("\n".join(f"{row['key']}: {row['value']}" for row in rows))

    @dispatcher.message(F.text.startswith("/browser"))
    async def browser(message: Message) -> None:
        if not await allowed(message):
            return
        state = assistant.browser.state()
        if state.get("needs_user"):
            await message.answer(f"Нужно ваше участие.\n{state.get('reason', '')}\n{settings.public_base_url}/")
            return
        await message.answer(f"Последняя страница: {state.get('last_url') or 'ещё не открывал'}.")

    @dispatcher.message(F.text.startswith("/cancel"))
    async def cancel(message: Message) -> None:
        if not await allowed(message):
            return
        await _reply(message, assistant.cancel())

    @dispatcher.message(F.voice)
    async def voice(message: Message) -> None:
        if not await allowed(message):
            return
        assert message.voice is not None
        destination = upload_dir / f"{message.voice.file_unique_id}.ogg"
        await _download(bot, message.voice.file_id, destination)
        transcript = await asyncio.to_thread(transcribe, destination, settings)
        if not transcript:
            await message.answer("Голос сохранён. Расшифровка выключена: нужен LLM_PROVIDER=openai и LLM_API_KEY. Пока пришлите текст.")
            return
        replies = await asyncio.to_thread(
            assistant.handle,
            Incoming(user_id=settings.owner_id, voice_transcript=transcript, source="telegram"),
        )
        await _reply(message, replies)

    @dispatcher.message(F.photo)
    async def photo(message: Message) -> None:
        if not await allowed(message):
            return
        picture = message.photo[-1]
        destination = upload_dir / f"{picture.file_unique_id}.jpg"
        await _download(bot, picture.file_id, destination)
        note = await asyncio.to_thread(describe_image, destination, settings)
        if not note and not (message.caption or "").strip():
            await message.answer("Фото сохранено. Распознавание выключено: добавьте подпись или ключ модели.")
            return
        replies = await asyncio.to_thread(
            assistant.handle,
            Incoming(user_id=settings.owner_id, text=message.caption or "", image_note=note, source="telegram"),
        )
        await _reply(message, replies)

    @dispatcher.message(F.document)
    async def document(message: Message) -> None:
        if not await allowed(message):
            return
        assert message.document is not None
        name = message.document.file_name or "file.bin"
        destination = upload_dir / f"{message.document.file_unique_id}-{Path(name).name}"
        await _download(bot, message.document.file_id, destination)
        try:
            extracted = await asyncio.to_thread(extract_document, destination)
        except Exception as exc:  # noqa: BLE001
            await message.answer(str(exc))
            return
        replies = await asyncio.to_thread(
            assistant.handle,
            Incoming(
                user_id=settings.owner_id,
                text=message.caption or "Разбери письмо и подготовь ответ",
                document_name=name,
                document_text=extracted,
                source="telegram",
            ),
        )
        await _reply(message, replies)

    @dispatcher.message(F.text)
    async def text(message: Message) -> None:
        if not await allowed(message):
            return
        replies = await asyncio.to_thread(
            assistant.handle,
            Incoming(user_id=settings.owner_id, text=message.text or "", source="telegram"),
        )
        await _reply(message, replies)

    return dispatcher


async def _download(bot: Bot, file_id: str, destination: Path) -> None:
    remote = await bot.get_file(file_id)
    await bot.download_file(remote.file_path, destination)


async def run_bot(settings: Settings, assistant: Assistant) -> None:
    bot = Bot(settings.telegram_token)
    dispatcher = build_dispatcher(settings, assistant, bot)
    await dispatcher.start_polling(bot)


async def serve(app, settings: Settings, assistant: Assistant) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host=settings.host, port=settings.port, loop="asyncio"))
    await asyncio.gather(server.serve(), run_bot(settings, assistant))
