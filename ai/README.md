# GigaChat Summary CLI

CLI-инструмент на Python для получения кратких выжимок (summary) текстовых сообщений через GigaChat API.

## Описание проекта

Проект представляет собой командную строку утилиту, которая:
- Читает текст из файла или принимает его как аргумент
- Отправляет текст в GigaChat API
- Получает краткую выжимку текста
- Выводит результат на экран

## Структура проекта

```
ai/
├── main.py          # CLI-приложение
├── gigachat.py      # Модуль для работы с GigaChat API
├── utils.py         # Вспомогательные функции
├── requirements.txt # Зависимости проекта
├── .env            # Файл с credentials (создайте из .env.example)
├── .env.example    # Пример файла с переменными окружения
└── README.md       # Документация проекта
```

## Требования

- Python 3.10 или выше
- Библиотеки: requests, python-dotenv
- Учетные данные GigaChat API (CLIENT_ID и CLIENT_SECRET)

## Установка

### 1. Переход в директорию проекта

```bash
cd ai
```

### 2. Создание виртуального окружения

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

1. Скопируйте файл `.env.example` в `.env`:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

2. Откройте файл `.env` и укажите ваши credentials:

```
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```

**Где получить credentials:**
- Перейдите на https://developers.sber.ru/gigachat
- Зарегистрируйтесь и создайте приложение
- Скопируйте CLIENT_ID и CLIENT_SECRET

## Использование

### Получение выжимки из файла

```bash
python main.py summary --file messages.txt
```

### Получение выжимки из текста

```bash
python main.py summary --text "Ваш текст сообщений здесь"
```

### Приоритет параметров

Если указаны оба параметра (`--file` и `--text`), приоритет имеет `--text`.

### Примеры

```bash
# Из файла
python main.py summary --file data/messages.txt

# Из текста
python main.py summary --text "Сегодня была важная встреча. Обсудили планы на квартал."

# Помощь
python main.py summary --help
```

## Пример вывода

```
==================================================
ВЫЖИМКА:
==================================================
Краткая выжимка вашего текста будет здесь...
==================================================
```

## Обработка ошибок

Приложение обрабатывает следующие ошибки:
- Отсутствие файла
- Пустой текст
- Ошибки аутентификации в GigaChat API
- Ошибки запросов к API
- Неверный формат ответа API

## Безопасность

⚠️ **Важно:**
- Никогда не публикуйте файл `.env` с реальными credentials
- Добавьте `.env` в `.gitignore`
- Используйте `.env.example` как шаблон для других разработчиков

## Дополнительная информация

- **GigaChat API документация**: https://developers.sber.ru/gigachat
- **Документация requests**: https://requests.readthedocs.io/
- **Документация python-dotenv**: https://pypi.org/project/python-dotenv/

## Лицензия

Проект создан в образовательных целях.

