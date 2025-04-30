from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Настройка подключения к Firebird
DATABASE_CONFIG = {
    'user': 'sysdba',  # Ваш пользователь базы данных
    'password': 'liku',  # Ваш пароль
    'host': '10.10.12.12',  # Адрес сервера базы данных
    'port': '3050',  # Порт Firebird
    'database': 'C:\Prometheus_Api\DATABMDW.FDB',  # Путь к вашей базе данных
}

# Создаем строку подключения
connection_string = f"firebird+fdb://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}/{DATABASE_CONFIG['database']}"
engine = create_engine(connection_string)

# Создаем сессию
Session = sessionmaker(bind=engine)