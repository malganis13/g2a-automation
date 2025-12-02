"""
Конфигурация приложения на базе Pydantic Settings
Автоматически читает из .env файла
"""

from typing import Optional
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    print("⚠️  pydantic not installed, using fallback configuration")
    print("Install: pip install pydantic pydantic-settings")

import json
import os
from pathlib import Path


if PYDANTIC_AVAILABLE:
    class G2AConfig(BaseSettings):
        """Настройки приложения"""
        
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore"  # Игнорировать неизвестные поля
        )
        
        # ===== G2A API =====
        g2a_client_id: str = Field(default="", description="G2A Client ID")
        g2a_client_secret: str = Field(default="", description="G2A Client Secret")
        g2a_client_email: str = Field(default="", description="G2A Account Email")
        g2a_seller_id: str = Field(default="", description="G2A Seller ID (auto-detected)")
        g2a_api_base: str = Field(default="https://gateway.g2a.com", description="G2A API Base URL")
        
        # ===== Telegram =====
        telegram_bot_token: Optional[str] = Field(default=None, description="Telegram Bot Token")
        telegram_chat_id: Optional[str] = Field(default=None, description="Telegram Chat ID")
        telegram_enabled: bool = Field(default=False, description="Enable Telegram notifications")
        
        # ===== Proxy =====
        proxy_url: Optional[str] = Field(default=None, description="Proxy URL (http://user:pass@host:port)")
        
        # ===== Server =====
        server_host: str = Field(default="127.0.0.1", description="Server host")
        server_port: int = Field(default=8000, description="Server port")
        
        # ===== Database =====
        database_path: str = Field(default="keys.db", description="SQLite database path")
        
        # ===== Logging =====
        log_level: str = Field(default="INFO", description="Logging level")
        log_to_file: bool = Field(default=True, description="Enable file logging")
        
        # ===== Exchange Rate =====
        default_eur_usd_rate: float = Field(default=1.1, description="Default EUR/USD rate")
        
        # ===== HTTP Settings =====
        request_timeout: int = Field(default=30, description="HTTP request timeout (seconds)")
        max_retries: int = Field(default=3, description="Max retry attempts")
        
        # ===== Price Parser Settings =====
        min_price_to_sell: float = Field(default=0.1, description="Minimum price to sell (EUR)")
        
        @field_validator("g2a_client_id", "g2a_client_secret")
        @classmethod
        def check_not_empty_if_set(cls, v):
            """Проверка что если задано, то не пустое"""
            if v and len(v.strip()) == 0:
                print(f"Warning: credential is set but empty")
            return v
        
        @field_validator("log_level")
        @classmethod
        def validate_log_level(cls, v):
            """Валидация уровня логирования"""
            allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            v_upper = v.upper()
            if v_upper not in allowed:
                print(f"Invalid log_level '{v}', using INFO")
                return "INFO"
            return v_upper
        
        def is_g2a_configured(self) -> bool:
            """Проверка что G2A API настроен"""
            return bool(self.g2a_client_id and self.g2a_client_secret)
        
        def is_telegram_configured(self) -> bool:
            """Проверка что Telegram настроен"""
            return bool(self.telegram_bot_token and self.telegram_chat_id)
else:
    # Fallback конфиг без Pydantic
    class G2AConfig:
        def __init__(self):
            self.g2a_client_id = os.getenv("G2A_CLIENT_ID", "")
            self.g2a_client_secret = os.getenv("G2A_CLIENT_SECRET", "")
            self.g2a_client_email = os.getenv("G2A_CLIENT_EMAIL", "")
            self.g2a_seller_id = os.getenv("G2A_SELLER_ID", "")
            self.g2a_api_base = os.getenv("G2A_API_BASE", "https://gateway.g2a.com")
            self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
            self.telegram_enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
            self.proxy_url = os.getenv("PROXY_URL")
            self.server_host = os.getenv("SERVER_HOST", "127.0.0.1")
            self.server_port = int(os.getenv("SERVER_PORT", "8000"))
            self.database_path = os.getenv("DATABASE_PATH", "keys.db")
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.log_to_file = os.getenv("LOG_TO_FILE", "true").lower() == "true"
            self.default_eur_usd_rate = float(os.getenv("DEFAULT_EUR_USD_RATE", "1.1"))
            self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
            self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
            self.min_price_to_sell = float(os.getenv("MIN_PRICE_TO_SELL", "0.1"))
        
        def is_g2a_configured(self):
            return bool(self.g2a_client_id and self.g2a_client_secret)
        
        def is_telegram_configured(self):
            return bool(self.telegram_bot_token and self.telegram_chat_id)


# ===== Загрузка сохраненных настроек из JSON (для GUI) =====
def load_saved_config():
    """Загрузка сохраненных настроек из g2a_config_saved.json"""
    config_file = "g2a_config_saved.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


# ===== Глобальный экземпляр конфига =====
try:
    config = G2AConfig()
    
    # Попытка загрузить сохраненные настройки из JSON (для GUI)
    saved_config = load_saved_config()
    if saved_config:
        config.g2a_client_id = saved_config.get("G2A_CLIENT_ID", config.g2a_client_id)
        config.g2a_client_secret = saved_config.get("G2A_CLIENT_SECRET", config.g2a_client_secret)
        config.g2a_client_email = saved_config.get("G2A_CLIENT_EMAIL", config.g2a_client_email)
        config.g2a_seller_id = saved_config.get("G2A_SELLER_ID", config.g2a_seller_id)
        config.telegram_bot_token = saved_config.get("TELEGRAM_BOT_TOKEN", config.telegram_bot_token)
        config.telegram_chat_id = saved_config.get("TELEGRAM_CHAT_ID", config.telegram_chat_id)
        config.telegram_enabled = saved_config.get("TELEGRAM_ENABLED", config.telegram_enabled)
    
    print("✅ Configuration loaded successfully")
    
    if not config.is_g2a_configured():
        print("⚠️  G2A API credentials not configured! Check .env file")
    
except Exception as e:
    print(f"❌ Failed to load configuration: {e}")
    print("Creating default config...")
    config = G2AConfig()


# ===== Backward compatibility (для старого кода) =====
G2A_CLIENT_ID = config.g2a_client_id
G2A_CLIENT_SECRET = config.g2a_client_secret
G2A_CLIENT_EMAIL = config.g2a_client_email
G2A_SELLER_ID = config.g2a_seller_id
G2A_API_BASE = config.g2a_api_base
REQUEST_TIMEOUT = config.request_timeout
TELEGRAM_BOT_TOKEN = config.telegram_bot_token or ""
TELEGRAM_CHAT_ID = config.telegram_chat_id or ""
TELEGRAM_ENABLED = config.telegram_enabled

# ✅ ДОБАВЛЕНЫ НЕДОСТАЮЩИЕ КОНСТАНТЫ для price_parser.py
# ✅ ИСПРАВЛЕНО: Используем локальный сервер вместо ngrok
API_BASE_URL = f"http://{config.server_host}:{config.server_port}"  # Автоматически из конфига
DEFAULT_PREFIX = "pref"  # Префикс по умолчанию
MIN_PRICE_TO_SELL = config.min_price_to_sell  # Минимальная цена для продажи
ADMIN_API_KEY = "akblfkykc635671"  # API ключ для админ панели

# Старые константы (для совместимости)
KEYS_FOLDER = "keys"
RESULT_FOLDER = "result"
PROXY_FILE = "proxy.txt"
PRICE_EXPIRY_DAYS = 3
DELAY_BETWEEN_REQUESTS = 1
G2A_BASE_URL = "https://www.g2a.com/category/gaming-c1"
G2A_BASE_PARAMS = "f%5Bplatform%5D%5B0%5D=1&f%5Btype%5D%5B0%5D=10"

# ОЧЕНЬ ВАЖНО: DATABASE_FILE для backward compatibility!
DATABASE_FILE = config.database_path

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
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "sec-fetch-site": "none",
    "sec-fetch-mode": "navigate",
    "sec-fetch-user": "?1",
    "sec-fetch-dest": "document",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def reload_config():
    """Перезагрузка конфигурации из .env и JSON"""
    global config, G2A_CLIENT_ID, G2A_CLIENT_SECRET, G2A_CLIENT_EMAIL, G2A_SELLER_ID
    global G2A_API_BASE, REQUEST_TIMEOUT, DATABASE_FILE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    global API_BASE_URL
    
    print("🔄 Reloading configuration...")
    config = G2AConfig()
    
    # Попытка загрузить сохраненные настройки из JSON
    saved_config = load_saved_config()
    if saved_config:
        config.g2a_client_id = saved_config.get("G2A_CLIENT_ID", config.g2a_client_id)
        config.g2a_client_secret = saved_config.get("G2A_CLIENT_SECRET", config.g2a_client_secret)
        config.g2a_client_email = saved_config.get("G2A_CLIENT_EMAIL", config.g2a_client_email)
        config.g2a_seller_id = saved_config.get("G2A_SELLER_ID", config.g2a_seller_id)
        config.telegram_bot_token = saved_config.get("TELEGRAM_BOT_TOKEN", config.telegram_bot_token)
        config.telegram_chat_id = saved_config.get("TELEGRAM_CHAT_ID", config.telegram_chat_id)
        config.telegram_enabled = saved_config.get("TELEGRAM_ENABLED", config.telegram_enabled)
    
    # Обновляем backward compatibility переменные
    G2A_CLIENT_ID = config.g2a_client_id
    G2A_CLIENT_SECRET = config.g2a_client_secret
    G2A_CLIENT_EMAIL = config.g2a_client_email
    G2A_SELLER_ID = config.g2a_seller_id
    G2A_API_BASE = config.g2a_api_base
    REQUEST_TIMEOUT = config.request_timeout
    DATABASE_FILE = config.database_path
    TELEGRAM_BOT_TOKEN = config.telegram_bot_token or ""
    TELEGRAM_CHAT_ID = config.telegram_chat_id or ""
    API_BASE_URL = f"http://{config.server_host}:{config.server_port}"
    
    print("✅ Configuration reloaded")


def update_g2a_credentials(client_id: str, client_secret: str):
    """Обновление G2A credentials и сохранение в .env"""
    env_path = Path(".env")
    
    # Читаем существующий .env
    env_lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
    
    # Обновляем значения
    updated = {"client_id": False, "client_secret": False}
    for i, line in enumerate(env_lines):
        if line.startswith("G2A_CLIENT_ID="):
            env_lines[i] = f"G2A_CLIENT_ID={client_id}\n"
            updated["client_id"] = True
        elif line.startswith("G2A_CLIENT_SECRET="):
            env_lines[i] = f"G2A_CLIENT_SECRET={client_secret}\n"
            updated["client_secret"] = True
    
    # Если не найдено - добавляем
    if not updated["client_id"]:
        env_lines.append(f"\nG2A_CLIENT_ID={client_id}\n")
    if not updated["client_secret"]:
        env_lines.append(f"G2A_CLIENT_SECRET={client_secret}\n")
    
    # Сохраняем
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(env_lines)
    
    print("✅ G2A credentials saved to .env")
    
    # Перезагружаем конфиг
    reload_config()


# ===== Вспомогательные функции (для совместимости со старым кодом) =====
def generate_credentials():
    """Генерация credentials (deprecated, оставлено для совместимости)"""
    return {
        "client_id": config.g2a_client_id,
        "client_secret": config.g2a_client_secret
    }


def save_credentials_to_file(credentials: dict):
    """Сохранение credentials (deprecated)"""
    update_g2a_credentials(
        credentials.get("client_id", ""),
        credentials.get("client_secret", "")
    )


YOUR_SERVER_CONFIG = {
    "host": config.server_host,
    "port": config.server_port
}


if __name__ == "__main__":
    # Тест конфигурации
    print("\n===== Current Configuration =====")
    print(f"G2A API Base: {config.g2a_api_base}")
    print(f"G2A Configured: {config.is_g2a_configured()}")
    print(f"Telegram Configured: {config.is_telegram_configured()}")
    print(f"Database: {config.database_path}")
    print(f"Log Level: {config.log_level}")
    print(f"Server: {config.server_host}:{config.server_port}")
    print(f"DATABASE_FILE: {DATABASE_FILE}")
    print(f"API_BASE_URL: {API_BASE_URL}")
    print(f"MIN_PRICE_TO_SELL: {MIN_PRICE_TO_SELL}")
    print("=" * 40)