"""
Конфигурационный файл для Telegram-бота.
Здесь хранится токен бота.
"""

# Получите токен у @BotFather в Telegram.
# Локальный токен лежит в config_local.py и не попадает в GitHub.
try:
    from config_local import BOT_TOKEN
except ImportError:
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

