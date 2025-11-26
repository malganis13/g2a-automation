# main.py - Главный запускатель системы G2A
import asyncio
import subprocess
import sys
import os
from pathlib import Path
import threading
import time

# Импорты ваших модулей
from key_manager import KeyManager, G2AOfferCreator
from g2a_config import YOUR_SERVER_CONFIG, generate_credentials, save_credentials_to_file

# Импорт парсера (переименуйте parser.py в price_parser.py)
try:
    from parser import KeyPriceParser  # Ваш текущий парсер
except ImportError:
    print("Переименуйте parser.py в price_parser.py")
    sys.exit(1)


def check_requirements():
    """Проверка необходимых зависимостей"""
    required_packages = [
        'fastapi', 'uvicorn', 'httpx', 'curl_cffi', 'sqlite3'
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)

    if missing:
        print(f"Установите недостающие пакеты: pip install {' '.join(missing)}")
        return False
    return True


def setup_directories():
    """Создание необходимых папок"""
    directories = ['keys', 'result', 'logs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)



def start_api_server():
    """Запуск FastAPI сервера в отдельном процессе"""
    print("Запуск API сервера...")

    # Создаем файл для запуска сервера
    server_code = '''
from fastapi import FastAPI
import uvicorn
from main_fastapi_server import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80, reload=False)
'''

    with open('run_server.py', 'w') as f:
        f.write(server_code)

    # Запуск в отдельном процессе
    process = subprocess.Popen([sys.executable, 'run_server.py'])
    return process


async def parse_and_create_offers():
    """Режим 1: Парсинг цен и создание оферов"""
    print("\n=== Режим 1: Парсинг цен и создание оферов ===")

    # Инициализация компонентов
    key_manager = KeyManager()
    offer_creator = G2AOfferCreator(key_manager)
    price_parser = KeyPriceParser()

    # Проверка наличия ключей
    print("1. Проверка наличия ключей...")
    stats = key_manager.get_keys_stats()

    if stats.get('available', 0) == 0:
        print("❌ Нет доступных ключей!")
        print("Добавьте ключи через Режим управления ключами")
        return

    print(f"✓ Найдено {stats.get('available', 0)} доступных ключей")

    # Получение списка игр без цен
    games = key_manager.get_games_list()
    games_without_prices = [g for g in games if g['min_price'] == 0.0 and g['available_keys'] > 0]

    if not games_without_prices:
        print("✓ У всех игр уже есть цены")
        create_offers = input("Создать оферы для существующих игр? (y/n): ")
        if create_offers.lower() == 'y':
            await create_offers_for_existing_games(key_manager, offer_creator)
        return

    print(f"2. Найдено {len(games_without_prices)} игр без цен")

    # Парсинг цен
    print("3. Запуск парсинга цен...")

    # Создаем временные файлы для парсинга
    temp_folder = "temp_parsing"
    Path(temp_folder).mkdir(exist_ok=True)

    for game in games_without_prices[:5]:  # Ограничиваем для теста
        temp_file = os.path.join(temp_folder, f"{game['name']}.txt")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(f"{game['name']} | SAMPLE-KEY | Steam | Global\n")

    # Запуск парсера
    try:
        await price_parser.process_files()
        print("✓ Парсинг завершен")
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return

    # Обновление цен в базе
    print("4. Обновление цен в базе данных...")
    result_files = [f for f in os.listdir("result") if f.endswith('.txt')]

    updated_total = 0
    for result_file in result_files:
        file_path = os.path.join("result", result_file)
        updated = key_manager.set_prices_from_file(file_path)
        updated_total += updated

    print(f"✓ Обновлено цен для {updated_total} ключей")

    # Создание оферов
    print("5. Создание оферов на G2A...")
    await create_offers_for_games_with_prices(key_manager, offer_creator)


async def create_offers_from_existing_prices():
    """Режим 2: Создание оферов для готовых цен"""
    print("\n=== Режим 2: Создание оферов для готовых цен ===")

    key_manager = KeyManager()
    offer_creator = G2AOfferCreator(key_manager)

    # Загрузка цен из result файлов
    result_folder = "result"
    if not os.path.exists(result_folder):
        print("❌ Папка result не найдена")
        return

    result_files = [f for f in os.listdir(result_folder) if f.endswith('.txt')]
    if not result_files:
        print("❌ Нет файлов с ценами в папке result")
        return

    print(f"Найдено {len(result_files)} файлов с ценами")

    # Обновление цен
    updated_total = 0
    for result_file in result_files:
        file_path = os.path.join(result_folder, result_file)
        updated = key_manager.set_prices_from_file(file_path)
        updated_total += updated

    print(f"✓ Обновлено цен для {updated_total} ключей")

    # Создание оферов
    await create_offers_for_games_with_prices(key_manager, offer_creator)


async def parse_prices_only():
    """Режим 3: Только парсинг цен"""
    print("\n=== Режим 3: Только парсинг цен ===")

    price_parser = KeyPriceParser()

    print("Запуск парсера цен...")
    try:
        await price_parser.process_files()
        print("✓ Парсинг завершен. Проверьте папку result/")
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")


async def create_offers_for_games_with_prices(key_manager: KeyManager, offer_creator: G2AOfferCreator):
    """Создание оферов для игр с ценами"""
    games = key_manager.get_games_list()
    games_with_prices = [g for g in games if g['min_price'] > 0 and g['available_keys'] > 0]

    if not games_with_prices:
        print("❌ Нет игр с ценами для создания оферов")
        return

    print(f"Найдено {len(games_with_prices)} игр для создания оферов")

    created_count = 0
    for game in games_with_prices[:3]:  # Ограничиваем для теста
        print(f"Создание офера для: {game['name']}")

        # Поиск product_id (упрощенная версия)
        product_id = await offer_creator.search_product_id(game['name'])

        if not product_id:
            print(f"❌ Product ID не найден для {game['name']}")
            continue

        # Создание офера
        result = await offer_creator.create_offer(
            game_name=game['name'],
            product_id=product_id,
            price=game['min_price'],
            stock=game['available_keys']
        )

        if result['success']:
            print(f"✓ {result['message']}")
            created_count += 1
        else:
            print(f"❌ Ошибка: {result['error']}")

        # Пауза между запросами
        await asyncio.sleep(2)

    print(f"✓ Создано {created_count} оферов")


async def create_offers_for_existing_games(key_manager: KeyManager, offer_creator: G2AOfferCreator):
    """Создание оферов для существующих игр с ценами"""
    games = key_manager.get_games_list()
    games_ready = [g for g in games if g['min_price'] > 0 and g['available_keys'] > 0]

    print(f"Игры готовые к созданию оферов:")
    for i, game in enumerate(games_ready[:10], 1):
        print(f"{i}. {game['name']} - {game['available_keys']} ключей, от €{game['min_price']:.2f}")

    if len(games_ready) > 10:
        print(f"... и еще {len(games_ready) - 10} игр")

    confirm = input(f"Создать оферы для {len(games_ready)} игр? (y/n): ")
    if confirm.lower() == 'y':
        await create_offers_for_games_with_prices(key_manager, offer_creator)


def key_management_menu():
    """Меню управления ключами"""
    from key_manager import main_menu
    main_menu()


def show_server_status():
    """Показать статус сервера"""
    try:
        import requests
        response = requests.get("http://localhost:80/health", timeout=5)
        if response.status_code == 200:
            print("✓ API сервер работает")
            print(f"  URL: http://localhost:8000")
            print(f"  Docs: http://localhost:8000/docs")
        else:
            print("❌ API сервер не отвечает")
    except:
        print("❌ API сервер не запущен")


async def main():
    """Главная функция"""
    print("=" * 50)
    print("      G2A АВТОМАТИЗАЦИЯ ПРОДАЖИ КЛЮЧЕЙ")
    print("=" * 50)

    if not check_requirements():
        return

    setup_directories()

    while True:
        print("\n" + "=" * 40)
        print("ГЛАВНОЕ МЕНЮ")
        print("=" * 40)
        print("1. Парсинг цен + создание оферов")
        print("2. Создание оферов (цены готовы)")
        print("3. Только парсинг цен")
        print("4. Управление ключами")
        print("5. Запустить API сервер")
        print("6. Статус сервера")
        print("7. Настройка G2A credentials")
        print("0. Выход")
        print("-" * 40)

        choice = input("Выберите режим: ").strip()

        if choice == "1":
            await parse_and_create_offers()

        elif choice == "2":
            await create_offers_from_existing_prices()

        elif choice == "3":
            await parse_prices_only()

        elif choice == "4":
            key_management_menu()

        elif choice == "5":
            print("Запуск API сервера...")
            print("Выполните в отдельном терминале:")
            print(
                "python -c \"from g2a_fastapi_server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000)\"")
            input("Нажмите Enter для продолжения...")

        elif choice == "6":
            show_server_status()

        elif choice == "7":
            print("\nДля настройки G2A Import API credentials:")
            print("1. Перейдите в G2A Dashboard -> API Integration")
            print("3. API URL: https://your-domain.com/api")
            print("4. Token URL: https://your-domain.com/token")
            input("Нажмите Enter для продолжения...")

        elif choice == "0":
            print("Выход из программы")
            break

        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        input("Нажмите Enter для выхода...")