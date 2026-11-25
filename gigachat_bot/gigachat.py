"""
Модуль для работы с GigaChat API.
Обеспечивает получение токена доступа и генерацию ответов.
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
    MODELS_URL = "https://gigachat.devices.sberbank.ru/api/v1/models"
    CHAT_COMPLETIONS_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    
    def __init__(self):
        """
        Инициализация клиента GigaChat.
        
        Получает CLIENT_ID, CLIENT_SECRET и AUTHORIZATION_KEY из переменных окружения.
        """
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.authorization_key = os.getenv('AUTHORIZATION_KEY')
        
        if not self.client_id or not self.client_secret:
            raise GigaChatError(
                "CLIENT_ID и CLIENT_SECRET должны быть указаны в файле .env"
            )
        
        if not self.authorization_key:
            raise GigaChatError(
                "AUTHORIZATION_KEY должен быть указан в файле .env"
            )
    def _get_authorization_key(self) -> str:
        """
        Получение Authorization key из переменной окружения.
        
        Returns:
            Authorization key для Basic Authentication
        """
        return self.authorization_key
    
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
            # Подготовка данных для запроса
            # payload должен быть строкой в формате application/x-www-form-urlencoded
            payload = 'scope=GIGACHAT_API_PERS'
            
            # Используем CLIENT_ID как RqUID (Request Unique ID)
            rquid = self.client_id
            
            # Получение Authorization key
            auth_key = self._get_authorization_key()
            
            # Подготовка заголовков
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': rquid,
                'Authorization': auth_key
            }
            
            # Выполнение запроса
            # verify=False отключает проверку SSL сертификата
            try:
                response = requests.post(
                    self.OAUTH_URL,
                    data=payload,  # Передаем строку напрямую
                    headers=headers,
                    timeout=30,  # Увеличиваем таймаут
                    verify=False,
                    allow_redirects=True
                )
            except requests.exceptions.RequestException as e:
                raise GigaChatAuthError(f"Ошибка при получении токена доступа: {e}")    
        except Exception as e:
            raise GigaChatAuthError(f"Неожиданная ошибка при получении токена доступа в функции get_access_token: {e}")
        try:    
            response = requests.get(
                self.MODELS_URL,
                headers=headers,
                data=payload,
                timeout=30,  # Увеличиваем таймаут для стабильности
                verify=False
            )
        except requests.exceptions.RequestException as e:
            raise GigaChatAPIError(f"Ошибка при получении списка моделей: {e}")
        except Exception as e:
            raise GigaChatAPIError(f"Неожиданная ошибка при получении списка моделей в функции get_models: {e}")
    
        try:
            response = requests.get(
                self.MODELS_URL,
                headers=headers,
                data=payload,
                timeout=30,  # Увеличиваем таймаут для стабильности
                verify=False
            )
            
            response.raise_for_status()
            result = response.json()
            
            if 'data' in result:
                return result['data']
            return result
            
        except requests.exceptions.RequestException as e:
            raise GigaChatAPIError(f"Ошибка при получении списка моделей: {e}")
    
    def generate_response(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """
        Генерация ответа на вопрос пользователя через GigaChat API.
        
        Args:
            user_message: Вопрос или сообщение пользователя
            system_prompt: Опциональный системный промпт (по умолчанию используется стандартный)
            
        Returns:
            Ответ от GigaChat
            
        Raises:
            GigaChatAPIError: При ошибке запроса к API
        """
        # Получаем актуальный Access token для авторизации
        access_token = self.get_access_token()
        
        # Системный промпт по умолчанию
        if system_prompt is None:
            system_prompt = (
                "Ты - полезный AI-ассистент. Отвечай на вопросы пользователей "
                "четко, информативно и дружелюбно. Если не знаешь ответа, честно об этом скажи."
            )
        
        # Подготовка запроса
        request_data = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"  # Используем актуальный токен
        }
        
        try:
            response = requests.post(
                self.CHAT_COMPLETIONS_URL,
                json=request_data,
                headers=headers,
                timeout=30,
                verify=False
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

