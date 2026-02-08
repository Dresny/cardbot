import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    TOKEN = "8475923416:AAEn7pC6C6OsM57RU1HDOjQTdc1pa0CF4_o"

    # ID вашего канала (можно получить через @username_to_id_bot)
    CHANNEL_ID = -1002195866325

    # Цены за карточки
    PRICES = {
        "Обычный": 10,
        "Редкий": 15,
        "Мифик": 30,
        "Легендарный": 50,
        "Секрет": 100
    }

    # Путь к папке с карточками
    CARDS_PATH = "data"

    # Время между открытиями в секундах (1 час)
    COOLDOWN_SECONDS = 3600