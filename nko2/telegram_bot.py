"""Telegram руководителя: текст, голос, фото и файл. Чужой чат отклоняется."""

from __future__ import annotations

import asyncio
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

from nko.access import allowed_chat
from nko2.assistant import Assistant
from nko2.config import Settings
from nko2.models import Incoming, Outbound


def transcribe(path: Path, settings: Settings) -> str:
    from nko.media import transcribe as _transcribe

    return _transcribe(path, settings)  # type: ignore[arg-type]


def describe_image(path: Path, settings: Settings) -> str:
    from nko.media import describe_image as _describe

    return _describe(path, settings)  # type: ignore[arg-type]


def extract_document(path: Path) -> str:
    from nko.media import extract_document as _extract

    return _extract(path)


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
        if allowed_chat(message.chat.id, settings):  # type: ignore[arg-type]
            return True
        await message.answer(f"Доступ только у руководителя. Идентификатор этого чата: {message.chat.id}.")
        return False

    @dispatcher.message(F.text.startswith("/start"))
    async def start(message: Message) -> None:
        if not await allowed(message):
            return
        await message.answer(
            "Вторая версия. Сводка Yonote, Telegram, VK и почты, отчёт недели, поиск грантов, "
            "напоминания и посты. Публикация и запись в Yonote ждут «да». «Стоп» отменяет черновик."
        )

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
        remote = await bot.get_file(message.voice.file_id)
        await bot.download_file(remote.file_path, destination)
        transcript = await asyncio.to_thread(transcribe, destination, settings)
        if not transcript:
            await message.answer("Голос сохранён. Расшифровка выключена: для работы из России укажите LLM_PROVIDER=gigachat и LLM_API_KEY.")
            return
        replies = await asyncio.to_thread(assistant.handle, Incoming(user_id=settings.owner_id, voice_transcript=transcript, source="telegram"))
        await _reply(message, replies)

    @dispatcher.message(F.photo)
    async def photo(message: Message) -> None:
        if not await allowed(message):
            return
        picture = message.photo[-1]
        destination = upload_dir / f"{picture.file_unique_id}.jpg"
        remote = await bot.get_file(picture.file_id)
        await bot.download_file(remote.file_path, destination)
        note = await asyncio.to_thread(describe_image, destination, settings)
        if not note and not (message.caption or "").strip():
            await message.answer("Фото сохранено. Добавьте подпись или ключ GigaChat.")
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
        remote = await bot.get_file(message.document.file_id)
        await bot.download_file(remote.file_path, destination)
        try:
            extracted = await asyncio.to_thread(extract_document, destination)
        except Exception as exc:  # noqa: BLE001
            await message.answer(str(exc))
            return
        replies = await asyncio.to_thread(
            assistant.handle,
            Incoming(user_id=settings.owner_id, text=message.caption or "Разбери входящие", document_name=name, document_text=extracted, source="telegram"),
        )
        await _reply(message, replies)

    @dispatcher.message(F.text)
    async def text(message: Message) -> None:
        if not await allowed(message):
            return
        replies = await asyncio.to_thread(assistant.handle, Incoming(user_id=settings.owner_id, text=message.text or "", source="telegram"))
        await _reply(message, replies)

    return dispatcher


async def serve(app, settings: Settings, assistant: Assistant) -> None:
    bot = Bot(settings.telegram_token)
    dispatcher = build_dispatcher(settings, assistant, bot)
    server = uvicorn.Server(uvicorn.Config(app, host=settings.host, port=settings.port, loop="asyncio"))
    await asyncio.gather(server.serve(), dispatcher.start_polling(bot))
