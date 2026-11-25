"""
Вспомогательные функции для работы с текстом и файлами.
"""

from pathlib import Path
from typing import Optional


def read_text_from_file(file_path: Path) -> str:
    """
    Чтение текста из файла.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Содержимое файла как строка
        
    Raises:
        IOError: При ошибке чтения файла
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise IOError(f"Ошибка при чтении файла '{file_path}': {e}")


def validate_text(text: Optional[str]) -> bool:
    """
    Валидация текста.
    
    Args:
        text: Текст для проверки
        
    Returns:
        True, если текст валиден (не пустой), False в противном случае
    """
    if not text:
        return False
    
    # Удаление пробелов и проверка, что остался хотя бы один символ
    stripped = text.strip()
    return len(stripped) > 0

