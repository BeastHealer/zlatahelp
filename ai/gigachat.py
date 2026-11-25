"""
Модуль для работы с GigaChat API.
Обеспечивает получение токена доступа и генерацию выжимки текста.
"""

import os
import requests
import urllib3
from typing import Optional
from dotenv import load_dotenv

# Отключение предупреждений о небезопасных SSL запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Загрузка переменных окружения из .env файла
load_dotenv()


class GigaChatError(Exception):
    """Базовое исключение для ошибок GigaChat API."""
    pass


class GigaChatAuthError(GigaChatError):
    """Ошибка аутентификации в GigaChat API."""
    pass


class GigaChatAPIError(GigaChatError):
    """Ошибка при запросе к GigaChat API."""
    pass


class GigaChatClient:
    """Клиент для работы с GigaChat API."""
    
    OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    CHAT_COMPLETIONS_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    
    def __init__(self):
        """
        Инициализация клиента GigaChat.
        
        Получает CLIENT_ID и CLIENT_SECRET из переменных окружения.
        """
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        
        if not self.client_id or not self.client_secret:
            raise GigaChatError(
                "CLIENT_ID и CLIENT_SECRET должны быть указаны в файле .env"
            )
        
        self._access_token: Optional[str] = None
    
    def get_access_token(self) -> str:
        """
        Получение OAuth токена доступа.
        
        Returns:
            Access token для доступа к API
            
        Raises:
            GigaChatAuthError: При ошибке аутентификации
        """
        if self._access_token:
            return self._access_token
        
        try:
            # Подготовка данных для запроса (формат application/x-www-form-urlencoded)
            auth_data = {
                "scope": "GIGACHAT_API_PERS"
            }
            
            # Подготовка заголовков
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            # Выполнение запроса с Basic Auth
            # verify=False отключает проверку SSL сертификата (небезопасно, но необходимо для работы с GigaChat)
            response = requests.post(
                self.OAUTH_URL,
                data=auth_data,
                auth=(self.client_id, self.client_secret),
                headers=headers,
                timeout=10,
                verify=False  # Отключение проверки SSL сертификата
            )
            
            response.raise_for_status()
            result = response.json()
            
            if 'access_token' not in result:
                raise GigaChatAuthError("Токен доступа не получен в ответе API")
            
            self._access_token = result['access_token']
            return self._access_token
            
        except requests.exceptions.RequestException as e:
            raise GigaChatAuthError(f"Ошибка при получении токена доступа: {e}")
        except KeyError as e:
            raise GigaChatAuthError(f"Неожиданный формат ответа API: {e}")
    
    def generate_summary(self, text: str) -> str:
        """
        Генерация краткой выжимки текста через GigaChat API.
        
        Args:
            text: Текст для обработки
            
        Returns:
            Краткая выжимка текста
            
        Raises:
            GigaChatAPIError: При ошибке запроса к API
        """
        # Получение токена доступа
        access_token = self.get_access_token()
        
        # Подготовка запроса
        request_data = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты – ассистент, который делает краткие выжимки текста."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        try:
            # verify=False отключает проверку SSL сертификата
            response = requests.post(
                self.CHAT_COMPLETIONS_URL,
                json=request_data,
                headers=headers,
                timeout=30,
                verify=False  # Отключение проверки SSL сертификата
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Извлечение ответа из структуры ответа API
            if 'choices' not in result or len(result['choices']) == 0:
                raise GigaChatAPIError("Пустой ответ от API")
            
            message = result['choices'][0].get('message', {})
            content = message.get('content', '')
            
            if not content:
                raise GigaChatAPIError("Ответ не содержит текста")
            
            return content.strip()
            
        except requests.exceptions.RequestException as e:
            raise GigaChatAPIError(f"Ошибка при запросе к API: {e}")
        except (KeyError, IndexError) as e:
            raise GigaChatAPIError(f"Неожиданный формат ответа API: {e}")

