"""
Модуль для работы с локальной базой данных SQLite.
Обеспечивает сохранение и проверку сообщений из Telegram.
"""

import sqlite3
from datetime import datetime
from typing import Optional


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_name: str = 'telegram_messages.db'):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_name: Имя файла базы данных
        """
        self.db_name = db_name
        self._init_database()
    
    def _init_database(self):
        """Создание таблицы messages, если она не существует."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                sender TEXT,
                text TEXT,
                date TEXT NOT NULL,
                UNIQUE(id, chat_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_message(self, message_id: int, chat_id: int, sender: Optional[str], 
                     text: Optional[str], date: datetime) -> bool:
        """
        Сохранение сообщения в базу данных с проверкой на дубликаты.
        
        Args:
            message_id: ID сообщения
            chat_id: ID чата
            sender: Имя отправителя
            text: Текст сообщения
            date: Дата и время сообщения
            
        Returns:
            True, если сообщение было сохранено, False если уже существует
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            # Проверка на дубликаты перед вставкой
            cursor.execute('''
                SELECT id FROM messages 
                WHERE id = ? AND chat_id = ?
            ''', (message_id, chat_id))
            
            if cursor.fetchone():
                conn.close()
                return False  # Сообщение уже существует
            
            # Вставка нового сообщения
            cursor.execute('''
                INSERT INTO messages (id, chat_id, sender, text, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (message_id, chat_id, sender, text, date.isoformat()))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении сообщения в БД: {e}")
            conn.close()
            return False
    
    def get_message_count(self, chat_id: Optional[int] = None) -> int:
        """
        Получение количества сообщений в базе данных.
        
        Args:
            chat_id: Опциональный ID чата для фильтрации
            
        Returns:
            Количество сообщений
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if chat_id:
            cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
        else:
            cursor.execute('SELECT COUNT(*) FROM messages')
        
        count = cursor.fetchone()[0]
        conn.close()
        return count

