"""
Конфигурационный файл для Telegram-бота.
Здесь хранятся настройки подключения к Telegram API.
"""

# Получите эти значения на https://my.telegram.org/apps
# Локальные ключи лежат в config_local.py и не попадают в GitHub.
try:
    from config_local import API_HASH, API_ID, SESSION_NAME
except ImportError:
    API_ID = 0  # Замените на ваш api_id
    API_HASH = "your_api_hash_here"  # Замените на ваш api_hash
    SESSION_NAME = "telegram_session"

