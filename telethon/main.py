"""
Основной файл Telegram-бота на базе Telethon.
Реализует подключение, получение чатов, сбор сообщений и live-мониторинг.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from telethon import TelegramClient, events
from telethon.tl.types import User, Channel, Chat

from config import API_ID, API_HASH, SESSION_NAME
from db import Database

# Настройка логирования
# Создание форматтера для логов
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_format)

# Обработчик для записи в файл
file_handler = logging.FileHandler('telegram_bot.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_format)

# Настройка базового логирования для всех модулей
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[console_handler, file_handler],
    force=True  # Переопределить существующую конфигурацию
)

# Получение логгера для текущего модуля
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()


class TelegramBot:
    """Основной класс для работы с Telegram через Telethon."""
    
    def __init__(self, api_id: int, api_hash: str, session_name: str):
        """
        Инициализация клиента Telegram.
        
        Args:
            api_id: API ID из my.telegram.org
            api_hash: API Hash из my.telegram.org
            session_name: Имя файла сессии
        """
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.db = Database()
    
    async def connect(self):
        """Подключение к Telegram с обработкой ошибок."""
        try:
            await self.client.start()
            logger.info("Успешное подключение к Telegram")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    
    async def get_dialogs(self) -> List[dict]:
        """
        Получение списка всех доступных диалогов (чатов).
        
        Returns:
            Список словарей с информацией о чатах
        """
        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs():
                chat_info = {
                    'id': dialog.id,
                    'title': dialog.name,
                    'type': type(dialog.entity).__name__,
                    'unread_count': dialog.unread_count
                }
                dialogs.append(chat_info)
                logger.info(f"Найден чат: {chat_info['title']} (ID: {chat_info['id']})")
            
            return dialogs
        except Exception as e:
            logger.error(f"Ошибка при получении списка чатов: {e}")
            return []
    
    async def collect_messages(self, chat_id: int, limit: int = 100) -> int:
        """
        Сбор последних N сообщений из выбранного чата.
        
        Args:
            chat_id: ID чата
            limit: Количество сообщений для сбора
            
        Returns:
            Количество сохраненных сообщений
        """
        try:
            saved_count = 0
            chat = await self.client.get_entity(chat_id)
            chat_title = chat.title if hasattr(chat, 'title') else str(chat_id)
            
            logger.info(f"Начинаю сбор сообщений из чата '{chat_title}' (лимит: {limit})")
            
            async for message in self.client.iter_messages(chat_id, limit=limit):
                # Получение имени отправителя
                sender_name = None
                if message.sender:
                    if isinstance(message.sender, User):
                        sender_name = message.sender.first_name
                        if message.sender.last_name:
                            sender_name += f" {message.sender.last_name}"
                    elif hasattr(message.sender, 'title'):
                        sender_name = message.sender.title
                
                # Если отправитель не определен (каналы, групповые чаты), используем название чата
                if not sender_name:
                    sender_name = chat_title
                
                # Сохранение сообщения в базу данных
                if self.db.save_message(
                    message_id=message.id,
                    chat_id=chat_id,
                    sender=sender_name,
                    text=message.text,
                    date=message.date
                ):
                    saved_count += 1
            
            logger.info(f"Собрано и сохранено {saved_count} сообщений из чата '{chat_title}'")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка при сборе сообщений: {e}")
            return 0
    
    async def setup_new_message_handler(self):
        """Настройка обработчика новых сообщений в реальном времени."""
        
        @self.client.on(events.NewMessage)
        async def handler(event):
            """Обработчик новых сообщений."""
            try:
                # Получение информации о чате
                chat = await event.get_chat()
                chat_title = chat.title if hasattr(chat, 'title') else "Unknown"
                chat_id = event.chat_id
                
                # Получение информации об отправителе
                sender_name = None
                if event.sender:
                    if isinstance(event.sender, User):
                        sender_name = event.sender.first_name
                        if event.sender.last_name:
                            sender_name += f" {event.sender.last_name}"
                    elif hasattr(event.sender, 'title'):
                        sender_name = event.sender.title
                
                # Если отправитель не определен (каналы, групповые чаты), используем название чата
                if not sender_name:
                    sender_name = chat_title
                
                # Получение текста сообщения
                message_text = event.message.text or "[Медиа/Стикер/Другое]"
                
                # Сохранение в базу данных
                if self.db.save_message(
                    message_id=event.message.id,
                    chat_id=chat_id,
                    sender=sender_name,
                    text=message_text,
                    date=event.message.date
                ):
                    # Вывод короткого лога в консоль
                    print(f"[{chat_title}] {sender_name}: {message_text[:100]}")
                    logger.info(f"Сохранено новое сообщение из '{chat_title}' от {sender_name}")
                else:
                    logger.debug(f"Сообщение уже существует в БД (дубликат)")
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке нового сообщения: {e}")
        
        logger.info("Обработчик новых сообщений настроен и активен")
    
    async def run(self):
        """Основной метод запуска бота."""
        try:
            # Подключение
            if not await self.connect():
                return
            
            # Получение списка чатов
            logger.info("Получение списка доступных чатов...")
            dialogs = await self.get_dialogs()
            print(f"\nНайдено чатов: {len(dialogs)}")
            print("\nПервые 10 чатов:")
            for i, dialog in enumerate(dialogs[:10], 1):
                print(f"{i}. {dialog['title']} (ID: {dialog['id']}, Тип: {dialog['type']})")
            
            # Пример: сбор последних 100 сообщений из первого чата
            if dialogs:
                first_chat_id = dialogs[0]['id']
                print(f"\nСобираю последние 100 сообщений из чата '{dialogs[0]['title']}'...")
                await self.collect_messages(first_chat_id, limit=100)
            
            # Запуск live-слушателя новых сообщений
            print("\nЗапуск live-слушателя новых сообщений...")
            print("Бот активен и слушает новые сообщения. Нажмите Ctrl+C для остановки.\n")
            await self.setup_new_message_handler()
            
            # Поддержание соединения
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("Остановка бота по запросу пользователя")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            await self.client.disconnect()
            logger.info("Отключение от Telegram")


async def main():
    """Главная функция для запуска бота."""
    bot = TelegramBot(API_ID, API_HASH, SESSION_NAME)
    await bot.run()


if __name__ == "__main__":
    # Запуск асинхронного бота
    asyncio.run(main())

