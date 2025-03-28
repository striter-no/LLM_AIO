import sqlite3
import json

class DataBase:
    def __init__(self, db_name='data.db'):
        self.connection = sqlite3.connect(db_name, check_same_thread=False)
        self.__create_table()

    def __create_table(self):
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS data (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

    def all(self):
        cursor = self.connection.cursor()
        cursor.execute('SELECT key FROM data')
        keys = [row[0] for row in cursor.fetchall()]
        return keys

    def set(self, key, value):
        # Сериализуем значение в JSON
        serialized_value = json.dumps(value)
        
        # Используем один запрос для вставки или обновления
        with self.connection:
            self.connection.execute('''
                INSERT INTO data (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            ''', (key, serialized_value))

    def batch_set(self, items):
        # Пакетная вставка для улучшения производительности
        with self.connection:
            self.connection.executemany('''
                INSERT INTO data (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            ''', [(key, json.dumps(value)) for key, value in items])

    def get(self, key):
        cursor = self.connection.cursor()
        cursor.execute('SELECT value FROM data WHERE key = ?', (key,))
        result = cursor.fetchone()
        return json.loads(result[0]) if result else None

    def close(self):
        self.connection.close()

# Пример использования
if __name__ == "__main__":
    store = DataBase()
    
    # Пример одиночной вставки
    store.set('example_key', {'example': 'value'})

    # Пример пакетной вставки
    items_to_insert = [
        ('key1', {'data': 'value1'}),
        ('key2', {'data': 'value2'}),
        ('key3', {'data': 'value3'}),
    ]
    store.batch_set(items_to_insert)

    # Получение значения
    print(store.get('example_key'))

    # Закрытие соединения
    store.close()
