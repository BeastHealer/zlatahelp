"""
Telegram-бот с интеграцией GigaChat API.
Отвечает на вопросы пользователей, используя GigaChat для генерации ответов.
"""

import telebot
import logging
from dotenv import load_dotenv
import os

from gigachat import GigaChatClient

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получение токена бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    raise ValueError(
        "Ошибка: Необходимо указать BOT_TOKEN в файле .env\n"
        "Получите токен у @BotFather в Telegram"
    )

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)

# Создание клиента GigaChat
try:
    giga_client = GigaChatClient()
    logger.info("GigaChat клиент инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации GigaChat клиента: {e}")
    giga_client = None


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Обработчик команд /start и /help.
    
    Args:
        message: Объект сообщения от пользователя
    """
    welcome_text = (
        "🤖 Привет! Я бот с интеграцией GigaChat AI.\n\n"
        "Я могу отвечать на ваши вопросы, используя искусственный интеллект.\n\n"
        "📝 Просто отправьте мне любой вопрос или сообщение, и я постараюсь на него ответить!\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/status - Проверить статус подключения к GigaChat\n"
        "/models - Показать список доступных моделей\n\n"
        "💡 Примеры вопросов:\n"
        "• Что такое Python?\n"
        "• Объясни квантовую физику\n"
        "• Напиши стихотворение о программировании"
    )
    
    bot.reply_to(message, welcome_text)
    logger.info(f"Пользователь {message.from_user.id} ({message.from_user.username}) использовал команду {message.text}")


@bot.message_handler(commands=['status'])
def check_status(message):
    """
    Проверка статуса подключения к GigaChat API.
    
    Args:
        message: Объект сообщения от пользователя
    """
    if giga_client is None:
        bot.reply_to(message, "❌ GigaChat клиент не инициализирован. Проверьте настройки.")
        return
    
    try:
        # Пытаемся получить токен для проверки подключения
        token = giga_client.get_access_token()
        if token:
            # Пытаемся получить список моделей для полной проверки
            try:
                models = giga_client.get_models()
                status_msg = "✅ Подключение к GigaChat API работает!\n"
                status_msg += f"✅ Access token получен\n"
                status_msg += f"✅ Список моделей доступен"
                bot.reply_to(message, status_msg)
            except:
                bot.reply_to(message, "✅ Access token получен, но ошибка при получении моделей")
            logger.info(f"Проверка статуса от {message.from_user.id}: успешно")
        else:
            bot.reply_to(message, "⚠️ Не удалось получить токен доступа")
    except Exception as e:
        error_msg = str(e)
        # Более детальное сообщение об ошибке
        if "CLIENT_ID" in error_msg or "AUTHORIZATION_KEY" in error_msg:
            error_msg += "\n\n💡 Проверьте, что в файле .env указаны правильные CLIENT_ID и AUTHORIZATION_KEY"
        elif "400" in error_msg or "Bad Request" in error_msg:
            error_msg += "\n\n💡 Возможные причины:\n"
            error_msg += "• Неправильный формат CLIENT_ID или CLIENT_SECRET\n"
            error_msg += "• Учетные данные недействительны\n"
            error_msg += "• Проверьте, что CLIENT_ID и CLIENT_SECRET скопированы полностью без пробелов"
        
        bot.reply_to(message, f"❌ Ошибка подключения к GigaChat API:\n{error_msg}")
        logger.error(f"Ошибка проверки статуса: {e}")


@bot.message_handler(commands=['models'])
def show_models(message):
    """
    Показать список доступных моделей GigaChat.
    
    Args:
        message: Объект сообщения от пользователя
    """
    if giga_client is None:
        bot.reply_to(message, "❌ GigaChat клиент не инициализирован. Проверьте настройки.")
        return
    
    try:
        models = giga_client.get_models()
        if models:
            models_text = "📋 Доступные модели GigaChat:\n\n"
            if isinstance(models, list):
                for model in models:
                    if isinstance(model, dict):
                        model_id = model.get('id', 'Unknown')
                        model_name = model.get('name', model_id)
                        models_text += f"• {model_name}\n"
                    else:
                        models_text += f"• {model}\n"
            else:
                models_text += str(models)
            bot.reply_to(message, models_text)
        else:
            bot.reply_to(message, "⚠️ Не удалось получить список моделей")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении списка моделей: {str(e)}")
        logger.error(f"Ошибка получения моделей: {e}")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """
    Обработчик всех текстовых сообщений.
    Отправляет запрос в GigaChat и возвращает ответ пользователю.
    
    Args:
        message: Объект сообщения от пользователя
    """
    if giga_client is None:
        bot.reply_to(message, "❌ GigaChat клиент не инициализирован. Обратитесь к администратору.")
        return
    
    user_text = message.text
    user_name = message.from_user.first_name or "Пользователь"
    
    # Отправляем сообщение о том, что бот думает
    thinking_msg = bot.reply_to(message, "🤔 Думаю...")
    
    try:
        logger.info(f"Запрос от {message.from_user.id} ({message.from_user.username}): {user_text[:100]}")
        
        # Получаем ответ от GigaChat
        response = giga_client.generate_response(user_text)
        
        # Удаляем сообщение "Думаю..."
        bot.delete_message(message.chat.id, thinking_msg.message_id)
        
        # Отправляем ответ пользователю
        bot.reply_to(message, f"💬 {response}")
        
        logger.info(f"Ответ отправлен пользователю {message.from_user.id}")
        
    except Exception as e:
        # Удаляем сообщение "Думаю..."
        try:
            bot.delete_message(message.chat.id, thinking_msg.message_id)
        except:
            pass
        
        error_msg = f"❌ Произошла ошибка при обработке запроса: {str(e)}"
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка при обработке сообщения от {message.from_user.id}: {e}")


def main():
    """Главная функция для запуска бота."""
    try:
        logger.info("Запуск GigaChat бота...")
        logger.info("Бот активен и ожидает сообщения...")
        print("🤖 GigaChat бот запущен и готов к работе!")
        print("Нажмите Ctrl+C для остановки.\n")
        
        # Запуск бота в режиме polling
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
        print("\n👋 Бот остановлен.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()

