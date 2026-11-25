"""
CLI-приложение для получения выжимки (summary) текстовых сообщений через GigaChat API.
"""

import argparse
import sys
from pathlib import Path

from gigachat import GigaChatClient
from utils import read_text_from_file, validate_text


def main():
    """Главная функция CLI-приложения."""
    # Проверяем, если первый аргумент не начинается с дефиса и не является командой
    # то считаем его файлом (упрощенный синтаксис)
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        # Если это не команда и не флаг, проверяем, может ли это быть файлом
        if not first_arg.startswith('-') and first_arg not in ['summary']:
            file_path = Path(first_arg)
            if file_path.exists() or file_path.suffix in ['.txt', '.md', '.text']:
                # Упрощенный синтаксис: python main.py messages.txt
                try:
                    if not file_path.exists():
                        print(f"Ошибка: Файл '{first_arg}' не найден.")
                        sys.exit(1)
                    text = read_text_from_file(file_path)
                    process_text(text)
                    return
                except Exception as e:
                    print(f"Ошибка при чтении файла: {e}")
                    sys.exit(1)
            else:
                # Если файл не найден, используем стандартный парсер
                parse_and_run()
                return
        else:
            # Стандартный синтаксис с командами
            parse_and_run()
            return
    else:
        # Нет аргументов - показываем помощь
        parse_and_run()


def parse_and_run():
    """Парсинг аргументов и выполнение команды."""
    parser = argparse.ArgumentParser(
        description='Получение краткой выжимки текста через GigaChat API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py summary --file messages.txt
  python main.py summary --text "Ваш текст здесь"
  python main.py messages.txt              # Упрощенный синтаксис
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда summary
    summary_parser = subparsers.add_parser('summary', help='Получить выжимку текста')
    summary_parser.add_argument(
        '--file',
        type=str,
        help='Путь к файлу с текстом сообщений'
    )
    summary_parser.add_argument(
        '--text',
        type=str,
        help='Текст сообщений для обработки'
    )
    
    args = parser.parse_args()
    
    # Получение текста для обработки
    text = None
    
    if args.command == 'summary':
        # Приоритет у --text, если указаны оба параметра
        if args.text:
            text = args.text
        elif args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Ошибка: Файл '{args.file}' не найден.")
                sys.exit(1)
            text = read_text_from_file(file_path)
        else:
            print("Ошибка: Необходимо указать либо --file, либо --text")
            summary_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Валидация и обработка текста
    process_text(text)
    
def process_text(text: str):
    """Обработка текста и получение выжимки."""
    # Валидация текста
    if not validate_text(text):
        print("Ошибка: Текст не может быть пустым.")
        sys.exit(1)
    
    # Получение выжимки через GigaChat API
    try:
        client = GigaChatClient()
        summary = client.generate_summary(text)
        print("\n" + "="*50)
        print("ВЫЖИМКА:")
        print("="*50)
        print(summary)
        print("="*50 + "\n")
    except Exception as e:
        print(f"Ошибка при получении выжимки: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

