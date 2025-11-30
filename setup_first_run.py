"""
Автоматическая настройка при первом запуске
Создаёт .env файл если его нет
"""

import os
from pathlib import Path
import shutil


def setup_env_file():
    """Создание .env файла если не существует"""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists():
        print("🔧 Первый запуск! Создаём .env файл...")
        
        if env_example.exists():
            # Копируем из .env.example
            shutil.copy(env_example, env_file)
            print("✅ .env файл создан из .env.example")
        else:
            # Создаём вручную
            default_env_content = """# G2A API Credentials
G2A_CLIENT_ID=
G2A_CLIENT_SECRET=
G2A_API_BASE=https://gateway.g2a.com

# Telegram Bot (опционально)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Proxy (опционально)
PROXY_URL=

# Server Settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Database
DATABASE_PATH=keys.db

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true

# Exchange Rate
DEFAULT_EUR_USD_RATE=1.1
"""
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(default_env_content)
            print("✅ .env файл создан с дефолтными настройками")
        
        print("")
        print("👉 Важно: Заполни G2A credentials в настройках GUI")
        print("   Или открой .env файл и вставь:")
        print("   G2A_CLIENT_ID=твой_id")
        print("   G2A_CLIENT_SECRET=твой_secret")
        print("")
    else:
        print("✅ .env файл найден")


def create_required_folders():
    """Создание необходимых папок"""
    folders = ['keys', 'result', 'logs', 'temp_parsing']
    
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            folder_path.mkdir(exist_ok=True)
            print(f"✅ Создана папка: {folder}/")


def check_dependencies():
    """Проверка наличия зависимостей"""
    missing = []
    
    try:
        import pydantic
    except ImportError:
        missing.append('pydantic')
    
    try:
        import pydantic_settings
    except ImportError:
        missing.append('pydantic-settings')
    
    try:
        import loguru
    except ImportError:
        missing.append('loguru')
    
    try:
        import httpx
    except ImportError:
        missing.append('httpx')
    
    if missing:
        print("")
        print("⚠️  Не хватает зависимостей!")
        print("")
        print("👉 Установи все зависимости:")
        print(f"   pip install -r requirements.txt")
        print("")
        print("Или только недостающие:")
        print(f"   pip install {' '.join(missing)}")
        print("")
        return False
    
    return True


def first_run_setup():
    """Полная настройка при первом запуске"""
    print("="*50)
    print("      G2A AUTOMATION - Первая настройка")
    print("="*50)
    print("")
    
    # Проверка зависимостей
    if not check_dependencies():
        return False
    
    # Создание .env
    setup_env_file()
    
    # Создание папок
    create_required_folders()
    
    print("")
    print("✅ Настройка завершена!")
    print("")
    print("🚀 Теперь можешь:")
    print("   1. Заполнить G2A credentials в GUI (Настройки → G2A API)")
    print("   2. Или открыть .env файл блокнотом и заполнить")
    print("")
    print("="*50)
    
    return True


if __name__ == "__main__":
    first_run_setup()
