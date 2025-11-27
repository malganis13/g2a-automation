# g2a_config.py - Динамическая конфигурация с загрузкой из JSON

import json
import os

SANDBOX_MODE = False  # True = тесты, False = продакшн

# Папки
KEYS_FOLDER = "keys"
RESULT_FOLDER = "result"
PROXY_FILE = "proxy.txt"

# Парсинг
PRICE_EXPIRY_DAYS = 3
DELAY_BETWEEN_REQUESTS = 1
REQUEST_TIMEOUT = 20
DEFAULT_PREFIX = "pref"
ADMIN_API_KEY = "akblfkykc635671"
G2A_BASE_URL = "https://www.g2a.com/category/gaming-c1"
G2A_BASE_PARAMS = "f%5Bplatform%5D%5B0%5D=1&f%5Btype%5D%5B0%5D=10"

# Автоизменение цен (defaults)
AUTO_PRICE_CHANGE_ENABLED = True
AUTO_PRICE_CHECK_INTERVAL = 1800
AUTO_PRICE_MIN_OFFER_PRICE = 0.5
AUTO_PRICE_UNDERCUT_AMOUNT = 0.05
AUTO_PRICE_INCREASE_THRESHOLD = 0.1
AUTO_PRICE_DAILY_LIMIT = 30
AUTO_PRICE_MIN_PRICE = 0.1
AUTO_PRICE_MAX_PRICE = 1000.0

# Регионы
REGION_CODES = {
    "GLOBAL": 8355,
    "EUROPE": 878,
    "NORTH_AMERICA": 879,
    "ASIA": 883,
    "LATAM": 8794
}

COUNTRY_TO_REGION = {
    # Европа
    "AD": "EUROPE", "AL": "EUROPE", "AT": "EUROPE", "AX": "EUROPE", "BA": "EUROPE",
    "BE": "EUROPE", "BG": "EUROPE", "CH": "EUROPE", "CY": "EUROPE", "CZ": "EUROPE",
    "DE": "EUROPE", "DK": "EUROPE", "EE": "EUROPE", "ES": "EUROPE", "FI": "EUROPE",
    "FO": "EUROPE", "FR": "EUROPE", "GB": "EUROPE", "GG": "EUROPE", "GI": "EUROPE",
    "GL": "EUROPE", "GR": "EUROPE", "HR": "EUROPE", "HU": "EUROPE", "IE": "EUROPE",
    "IM": "EUROPE", "IS": "EUROPE", "IT": "EUROPE", "JE": "EUROPE", "LI": "EUROPE",
    "LT": "EUROPE", "LU": "EUROPE", "LV": "EUROPE", "MC": "EUROPE", "ME": "EUROPE",
    "MK": "EUROPE", "MT": "EUROPE", "NL": "EUROPE", "NO": "EUROPE", "PL": "EUROPE",
    "PT": "EUROPE", "RO": "EUROPE", "RS": "EUROPE", "SE": "EUROPE", "SI": "EUROPE",
    "SJ": "EUROPE", "SK": "EUROPE", "SM": "EUROPE", "VA": "EUROPE",
    "BY": "EUROPE", "MD": "EUROPE", "TR": "EUROPE", "UA": "EUROPE",
    # Северная Америка
    "US": "NORTH_AMERICA", "CA": "NORTH_AMERICA", "MX": "NORTH_AMERICA",
    # Латинская Америка
    "AR": "LATAM", "BO": "LATAM", "BR": "LATAM", "BS": "LATAM", "BZ": "LATAM",
    "CL": "LATAM", "CO": "LATAM", "CR": "LATAM", "EC": "LATAM", "GF": "LATAM",
    "GT": "LATAM", "GY": "LATAM", "HN": "LATAM", "NI": "LATAM", "PA": "LATAM",
    "PE": "LATAM", "PY": "LATAM", "SR": "LATAM", "SV": "LATAM", "UY": "LATAM",
    "VE": "LATAM",
    # Азия
    "JP": "ASIA", "CN": "ASIA", "KR": "ASIA", "IN": "ASIA", "TH": "ASIA",
    "VN": "ASIA", "MY": "ASIA", "SG": "ASIA", "ID": "ASIA", "PH": "ASIA",
    "AU": "ASIA", "NZ": "ASIA", "KZ": "ASIA", "UZ": "ASIA"
}

HEADERS = {
    "host": "www.g2a.com",
    "connection": "keep-alive",
    "sec-ch-ua": '\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Google Chrome\";v=\"140\"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '\"Windows\"',
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "sec-fetch-site": "none",
    "sec-fetch-mode": "navigate",
    "sec-fetch-user": "?1",
    "sec-fetch-dest": "document",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ============================================
# ДИНАМИЧЕСКАЯ ЗАГРУЗКА НАСТРОЕК ИЗ JSON
# ============================================

def load_config_from_json():
    """Загрузка конфигурации из g2a_config_saved.json"""
    config_file = "g2a_config_saved.json"
    # Defaults (fallback если файла нет)
    default_config = {
        "G2A_CLIENT_ID": "",
        "G2A_CLIENT_SECRET": "",
        "G2A_CLIENT_EMAIL": "",
            "G2A_SELLER_ID": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "MIN_PRICE_TO_SELL": 0.3,
        "TELEGRAM_ENABLED": False
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                default_config.update(loaded)
            print(f"✅ Загружены настройки из {config_file}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {config_file}: {e}")

    return default_config

# Загружаем конфиг
_config = load_config_from_json()

# Применяем к переменным
G2A_CLIENT_ID = _config.get("G2A_CLIENT_ID", "")
G2A_CLIENT_SECRET = _config.get("G2A_CLIENT_SECRET", "")
G2A_CLIENT_EMAIL = _config.get("G2A_CLIENT_EMAIL", "")
G2A_SELLER_ID = _config.get("G2A_SELLER_ID", "")
TELEGRAM_BOT_TOKEN = _config.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _config.get("TELEGRAM_CHAT_ID", "")
MIN_PRICE_TO_SELL = _config.get("MIN_PRICE_TO_SELL", 0.3)

# API endpoints (зависят от режима)
if SANDBOX_MODE:
    G2A_API_BASE = "https://sandboxapi.g2a.com"
    DATABASE_FILE = "sandbox_keys.db"
else:
    G2A_API_BASE = "https://api.g2a.com"
    DATABASE_FILE = "keys.db"

# Server config - ИСПРАВЛЕНО: используем порт 80
SERVER_CLIENT_ID = "my_test_client"
SERVER_CLIENT_SECRET = "my_test_secret_key_12345"
API_BASE_URL = "http://127.0.0.1:80"

# Конфигурация сервера (для совместимости)
YOUR_SERVER_CONFIG = {
    "DATABASE_FILE": DATABASE_FILE,
    "API_BASE_URL": API_BASE_URL,
    "ADMIN_API_KEY": ADMIN_API_KEY,
    "SERVER_CLIENT_ID": SERVER_CLIENT_ID,
    "SERVER_CLIENT_SECRET": SERVER_CLIENT_SECRET
}

def reload_config():
    """Перезагрузка конфигурации из JSON (вызывать после сохранения в GUI)"""
    global G2A_CLIENT_ID, G2A_CLIENT_SECRET, G2A_CLIENT_EMAIL, G2A_SELLER_ID
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, MIN_PRICE_TO_SELL
    config = load_config_from_json()
    G2A_CLIENT_ID = config.get("G2A_CLIENT_ID", "")
    G2A_CLIENT_SECRET = config.get("G2A_CLIENT_SECRET", "")
    G2A_CLIENT_EMAIL = config.get("G2A_CLIENT_EMAIL", "")
    G2A_SELLER_ID = config.get("G2A_SELLER_ID", "")
    TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = config.get("TELEGRAM_CHAT_ID", "")
    MIN_PRICE_TO_SELL = config.get("MIN_PRICE_TO_SELL", 0.3)
    print("✅ Конфигурация перезагружена!")

def generate_credentials():
    """Генерация учетных данных для G2A Import API"""
    return {
        "client_id": SERVER_CLIENT_ID,
        "client_secret": SERVER_CLIENT_SECRET,
        "api_url": f"{API_BASE_URL}/api",
        "token_url": f"{API_BASE_URL}/token"
    }

def save_credentials_to_file(credentials, filename="g2a_credentials.json"):
    """Сохранение credentials в файл"""
    with open(filename, 'w') as f:
        json.dump(credentials, f, indent=4)
