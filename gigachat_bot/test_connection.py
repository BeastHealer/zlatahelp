"""
Скрипт для проверки подключения к GigaChat API.
Используйте этот скрипт для диагностики проблем с подключением.
"""

import os
from dotenv import load_dotenv
from gigachat import GigaChatClient, GigaChatAuthError

# Загрузка переменных окружения
load_dotenv()

def test_connection():
    """Тестирование подключения к GigaChat API."""
    print("=" * 60)
    print("Тестирование подключения к GigaChat API")
    print("=" * 60)
    
    # Проверка переменных окружения
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    authorization_key = os.getenv('AUTHORIZATION_KEY')
    
    print("\n1. Проверка переменных окружения...")
    if not client_id:
        print("❌ CLIENT_ID не найден в .env файле")
        print("   CLIENT_ID используется как RqUID в запросах")
        print("   Получите на https://developers.sber.ru/gigachat")
        return False
    else:
        print(f"✅ CLIENT_ID найден: {client_id}")
        print("   (будет использован как RqUID в запросах)")
    
    if not authorization_key:
        print("❌ AUTHORIZATION_KEY не найден в .env файле")
        print("   AUTHORIZATION_KEY используется для Authorization key в запросах")
        print("   Получите на https://developers.sber.ru/gigachat")
        return False
    else:
        # Скрываем часть ключа для безопасности
        masked_key = authorization_key[:20] + "..." + authorization_key[-10:] if len(authorization_key) > 30 else authorization_key[:20] + "..."
        print(f"✅ AUTHORIZATION_KEY найден: {masked_key}")
        print("   (будет использован для Authorization key в запросах)")
    
    if client_secret:
        masked_secret = client_secret[:20] + "..." + client_secret[-10:] if len(client_secret) > 30 else client_secret[:20] + "..."
        print(f"✅ CLIENT_SECRET найден: {masked_secret}")
        print("   (отдельная переменная, не используется для Authorization key)")
    
    # Проверка формата
    print("\n2. Проверка формата...")
    if not authorization_key.startswith('Basic ') and len(authorization_key) < 20:
        print("⚠️  Внимание: AUTHORIZATION_KEY должен быть Base64 encoded строкой")
        print("   Бот автоматически добавит префикс 'Basic ' если его нет")
    
    # Попытка подключения
    print("\n3. Попытка подключения к GigaChat API...")
    try:
        client = GigaChatClient()
        print("✅ Клиент GigaChat создан успешно")
        
        print("\n4. Получение access token...")
        token = client.get_access_token()
        
        if token:
            print(f"✅ Access token получен успешно!")
            print(f"   Token (первые 50 символов): {token[:50]}...")
            return True
        else:
            print("❌ Не удалось получить access token")
            return False
            
    except GigaChatAuthError as e:
        print(f"❌ Ошибка аутентификации: {e}")
        print("\n💡 Возможные решения:")
        print("   • Проверьте правильность CLIENT_ID и AUTHORIZATION_KEY")
        print("   • Убедитесь, что ключи скопированы полностью")
        print("   • Проверьте, что в .env файле нет лишних пробелов")
        print("   • Убедитесь, что учетные данные действительны на https://developers.sber.ru/")
        print("   • AUTHORIZATION_KEY может быть в формате 'Basic <encoded>' или просто '<encoded>'")
        print("   • CLIENT_ID используется как RqUID в запросах к API")
        print("   • CLIENT_SECRET и AUTHORIZATION_KEY - это разные переменные")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    print("\n" + "=" * 60)
    if success:
        print("✅ Все проверки пройдены! Бот должен работать.")
    else:
        print("❌ Обнаружены проблемы. Исправьте их перед запуском бота.")
    print("=" * 60)

