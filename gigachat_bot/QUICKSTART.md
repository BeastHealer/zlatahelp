# Быстрый старт - GigaChat Bot

## Пошаговая инструкция по запуску бота

### Шаг 1: Перейдите в директорию проекта

```bash
cd gigachat_bot
```

### Шаг 2: Создайте виртуальное окружение (рекомендуется)

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Шаг 3: Установите зависимости

```bash
pip install -r requirements.txt
```

### Шаг 4: Получите токен Telegram бота

1. Откройте Telegram
2. Найдите бота **@BotFather**
3. Отправьте команду `/newbot`
4. Следуйте инструкциям:
   - Введите имя бота (например: "My GigaChat Bot")
   - Введите username бота (должен заканчиваться на `bot`, например: `my_gigachat_bot`)
5. Скопируйте полученный токен (выглядит как: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Шаг 5: Получите учетные данные GigaChat API

1. Зарегистрируйтесь на https://developers.sber.ru/
2. Создайте новое приложение
3. Скопируйте `CLIENT_ID` и `CLIENT_SECRET`

### Шаг 6: Создайте файл .env

**Windows:**
```bash
copy .env.example .env
```

**Linux/macOS:**
```bash
cp .env.example .env
```

### Шаг 7: Отредактируйте файл .env

Откройте файл `.env` в текстовом редакторе и замените значения:

```
BOT_TOKEN=ваш_токен_от_BotFather
CLIENT_ID=ваш_client_id
CLIENT_SECRET=ваш_client_secret
```

**Пример:**
```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
CLIENT_ID=0199ce4a-456d-76aa-8848-06bffe4bf6fa
CLIENT_SECRET=your_client_secret_here
```

### Шаг 8: Запустите бота

```bash
python main.py
```

Если все настроено правильно, вы увидите:
```
🤖 GigaChat бот запущен и готов к работе!
Нажмите Ctrl+C для остановки.
```

### Шаг 9: Протестируйте бота

1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте команду `/start`
4. Задайте любой вопрос, например: "Что такое Python?"

## Решение проблем

### Ошибка: "Необходимо указать BOT_TOKEN в файле .env"

- Убедитесь, что файл `.env` существует в директории `gigachat_bot/`
- Проверьте, что в файле `.env` указан правильный `BOT_TOKEN`

### Ошибка: "CLIENT_ID и CLIENT_SECRET должны быть указаны"

- Проверьте, что в файле `.env` указаны `CLIENT_ID` и `CLIENT_SECRET`
- Убедитесь, что нет лишних пробелов вокруг знака `=`

### Бот не отвечает на сообщения

- Убедитесь, что бот запущен (команда `python main.py` выполняется)
- Проверьте, что токен бота правильный
- Проверьте интернет-соединение

### Ошибка при установке зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Остановка бота

Нажмите `Ctrl+C` в терминале, где запущен бот.

