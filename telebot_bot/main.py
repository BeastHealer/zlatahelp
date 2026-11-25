"""
Простой Telegram-бот с функцией echo (повторение сообщений).
Использует библиотеку pyTelegramBotAPI (telebot).
"""

import telebot
from telebot import types
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импорт токена из config.py
try:
    from config import BOT_TOKEN
except ImportError:
    # Если config.py не найден, используем токен напрямую
    BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'  # Замените на ваш токен

# Проверка токена
if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE' or not BOT_TOKEN:
    raise ValueError(
        "Ошибка: Необходимо указать BOT_TOKEN в config.py или main.py\n"
        "Получите токен у @BotFather в Telegram"
    )

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Обработчик команд /start и /help.
    
    Args:
        message: Объект сообщения от пользователя
    """
    welcome_text = (
        "👋 Привет! Я простой echo-бот.\n\n"
        "Я буду повторять все ваши сообщения.\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/echo <текст> - Отправить echo сообщение\n\n"
        "Просто отправьте мне любое сообщение, и я его повторю!"
    )
    
    bot.reply_to(message, welcome_text)
    logger.info(f"Пользователь {message.from_user.id} ({message.from_user.username}) использовал команду {message.text}")


@bot.message_handler(commands=['echo'])
def echo_command(message):
    """
    Обработчик команды /echo.
    
    Args:
        message: Объект сообщения от пользователя
    """
    # Получаем текст после команды /echo
    text = message.text.replace('/echo', '').strip()
    
    if text:
        bot.reply_to(message, f"🔄 Echo: {text}")
        logger.info(f"Echo команда от {message.from_user.id}: {text}")
    else:
        bot.reply_to(message, "❌ Пожалуйста, укажите текст после команды /echo\n\nПример: /echo Привет, мир!")
        logger.warning(f"Пустая echo команда от {message.from_user.id}")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """
    Обработчик всех остальных сообщений (echo функция).
    
    Args:
        message: Объект сообщения от пользователя
    """
    # Игнорируем команды (они обрабатываются отдельными обработчиками)
    if message.text and message.text.startswith('/'):
        return
    
    # Повторяем сообщение пользователя
    user_name = message.from_user.first_name or "Пользователь"
    echo_text = f"📝 {user_name}, вы написали:\n\n{message.text}"
    
    bot.reply_to(message, echo_text)
    logger.info(f"Echo сообщение от {message.from_user.id} ({message.from_user.username}): {message.text[:50]}...")


@bot.message_handler(content_types=['photo', 'document', 'sticker', 'voice', 'video'])
def echo_media(message):
    """
    Обработчик медиа-файлов (фото, документы, стикеры и т.д.).
    
    Args:
        message: Объект сообщения от пользователя
    """
    user_name = message.from_user.first_name or "Пользователь"
    
    if message.photo:
        bot.reply_to(message, f"📷 {user_name}, вы отправили фото!")
        logger.info(f"Фото от {message.from_user.id}")
    elif message.document:
        bot.reply_to(message, f"📄 {user_name}, вы отправили документ: {message.document.file_name}")
        logger.info(f"Документ от {message.from_user.id}: {message.document.file_name}")
    elif message.sticker:
        bot.reply_to(message, f"😊 {user_name}, вы отправили стикер!")
        logger.info(f"Стикер от {message.from_user.id}")
    elif message.voice:
        bot.reply_to(message, f"🎤 {user_name}, вы отправили голосовое сообщение!")
        logger.info(f"Голосовое сообщение от {message.from_user.id}")
    elif message.video:
        bot.reply_to(message, f"🎥 {user_name}, вы отправили видео!")
        logger.info(f"Видео от {message.from_user.id}")


def main():
    """Главная функция для запуска бота."""
    try:
        logger.info("Запуск echo-бота...")
        logger.info("Бот активен и ожидает сообщения...")
        print("🤖 Echo-бот запущен и готов к работе!")
        print("Нажмите Ctrl+C для остановки.\n")
        
        # Запуск бота в режиме polling (постоянный опрос сервера)
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
        print("\n👋 Бот остановлен.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()

