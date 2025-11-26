import sqlite3
import os
import json
from typing import List, Dict
from datetime import datetime
import asyncio
import httpx

# Импортируем только то, что есть
try:
    from g2a_config import DATABASE_FILE, G2A_API_BASE, G2A_CLIENT_ID, G2A_CLIENT_SECRET
except ImportError:
    # Если нет DATABASE_FILE, используем значение по умолчанию
    from g2a_config import G2A_API_BASE, G2A_CLIENT_ID, G2A_CLIENT_SECRET

    DATABASE_FILE = "keys.db"


class KeyManager:
    def __init__(self, db_file: str = None):
        self.db_file = db_file or DATABASE_FILE
        self.init_database()

    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_name TEXT NOT NULL,
                product_id TEXT,
                key_value TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'available',
                price REAL,
                reserved_at TIMESTAMP,
                sold_at TIMESTAMP,
                reservation_id TEXT,
                order_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_name TEXT NOT NULL,
                product_id TEXT,
                g2a_offer_id TEXT,
                price REAL,
                declared_stock INTEGER,
                actual_stock INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def add_keys_from_file(self, file_path: str, prefix: str = "sks") -> int:
        """Добавление ключей из файла с префиксом"""
        if not os.path.exists(file_path):
            print(f"Файл {file_path} не найден")
            return 0

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        added_count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                parts = line.split(' | ')
                if len(parts) < 3:
                    print(f"Строка {line_num} некорректного формата: {line}")
                    continue

                try:
                    # Проверяем не продается ли уже ключ
                    if line.startswith('selling'):
                        continue

                    game_name = parts[0].strip()
                    key_value = parts[1].strip()
                    price = 0.0

                    # Добавление ключа с префиксом
                    cursor.execute("""
                        INSERT OR IGNORE INTO keys (game_name, key_value, price, prefix)
                        VALUES (?, ?, ?, ?)
                    """, (game_name, key_value, price, prefix))

                    if cursor.rowcount > 0:
                        added_count += 1

                except Exception as e:
                    print(f"Ошибка обработки строки {line_num}: {e}")
                    continue

        conn.commit()
        conn.close()

        return added_count

    def add_keys_from_folder(self, folder_path: str) -> Dict[str, int]:
        """Добавление ключей из папки с файлами"""
        results = {}

        if not os.path.exists(folder_path):
            print(f"Папка {folder_path} не найдена")
            return results

        for filename in os.listdir(folder_path):
            if filename.endswith('.txt'):
                file_path = os.path.join(folder_path, filename)
                added = self.add_keys_from_file(file_path)
                results[filename] = added
                print(f"Файл {filename}: добавлено {added} ключей")

        return results

    def get_keys_stats(self) -> Dict[str, int]:
        """Статистика по ключам"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM keys 
            GROUP BY status
        """)

        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = row[1]

        cursor.execute("SELECT COUNT(*) FROM keys")
        total = cursor.fetchone()[0]
        stats['total'] = total

        conn.close()
        return stats

    def get_games_list(self) -> List[Dict]:
        """Список игр с количеством ключей"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                game_name,
                COUNT(*) as total_keys,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_keys,
                SUM(CASE WHEN status = 'sold' THEN 1 ELSE 0 END) as sold_keys,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM keys 
            GROUP BY game_name
            ORDER BY total_keys DESC
        """)

        games = []
        for row in cursor.fetchall():
            games.append({
                'name': row[0],
                'total_keys': row[1],
                'available_keys': row[2],
                'sold_keys': row[3],
                'min_price': row[4] or 0.0,
                'max_price': row[5] or 0.0
            })

        conn.close()
        return games

    def update_product_ids(self, game_to_product_mapping: Dict[str, str]):
        """Обновление product_id для игр"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        updated_count = 0
        for game_name, product_id in game_to_product_mapping.items():
            cursor.execute("""
                UPDATE keys 
                SET product_id = ? 
                WHERE game_name = ? AND product_id IS NULL
            """, (product_id, game_name))
            updated_count += cursor.rowcount

        conn.commit()
        conn.close()

        return updated_count

    def set_prices_from_file(self, prices_file: str):
        """Установка цен из файла с распарсенными ценами"""
        if not os.path.exists(prices_file):
            print(f"Файл {prices_file} не найден")
            return 0

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        updated_count = 0
        with open(prices_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith('€'):
                    continue

                try:
                    parts = line.split(' | ')
                    if len(parts) < 2:
                        continue

                    price_str = parts[0].replace('€', '')
                    game_name = parts[1].strip()
                    price = float(price_str)

                    cursor.execute("""
                        UPDATE keys 
                        SET price = ? 
                        WHERE game_name = ? AND status = 'available'
                    """, (price, game_name))

                    updated_count += cursor.rowcount

                except Exception as e:
                    continue

        conn.commit()
        conn.close()

        return updated_count


class G2AOfferCreator:
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.g2a_token = None

    async def get_g2a_token(self) -> str:
        """Получение токена G2A API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{G2A_API_BASE}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": G2A_CLIENT_ID,
                    "client_secret": G2A_CLIENT_SECRET
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.g2a_token = data["access_token"]
                return self.g2a_token
            else:
                raise Exception(f"Failed to get G2A token: {response.status_code}")

    async def search_product_id(self, game_name: str) -> str:
        """Поиск product_id по названию игры"""
        if not self.g2a_token:
            await self.get_g2a_token()

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.g2a_token}"}

            # Поиск продукта
            response = await client.get(
                f"{G2A_API_BASE}/v1/products",
                headers=headers,
                params={"name": game_name, "limit": 10}
            )

            if response.status_code == 200:
                data = response.json()
                products = data.get("docs", [])

                for product in products:
                    if game_name.lower() in product.get("name", "").lower():
                        return product.get("id")

        return None

    async def create_offer(self, game_name: str, product_id: str, price: float, stock: int) -> Dict:
        """Создание офера на G2A"""
        if not self.g2a_token:
            await self.get_g2a_token()

        # Устанавливаем цену на 2-5% ниже найденной
        offer_price = round(price * 0.97, 2)  # 3% скидка

        offer_data = {
            "offerType": "dropshipping",
            "productId": product_id,
            "variants": [{
                "price": offer_price,
                "declaredStock": stock,
                "regions": ["GLOBAL"]  # Можно настроить по регионам
            }]
        }

        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {self.g2a_token}",
                "Content-Type": "application/json"
            }

            response = await client.post(
                f"{G2A_API_BASE}/v1/offer",
                headers=headers,
                json=offer_data
            )

            if response.status_code == 200:
                result = response.json()

                # Сохранение информации об офере в БД
                conn = sqlite3.connect(self.key_manager.db_file)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO offers (game_name, product_id, price, declared_stock, actual_stock, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                """, (game_name, product_id, offer_price, stock, stock))

                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "job_id": result.get("jobId"),
                    "offer_price": offer_price,
                    "message": f"Офер создан для {game_name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }


def main_menu():
    """Главное меню управления ключами"""
    key_manager = KeyManager()
    offer_creator = G2AOfferCreator(key_manager)

    while True:
        print("\n=== G2A Key Manager ===")
        print("1. Добавить ключи из файла")
        print("2. Добавить ключи из папки")
        print("3. Показать статистику")
        print("4. Показать список игр")
        print("5. Обновить цены из файла")
        print("6. Создать оферы на G2A")
        print("7. Найти Product ID для игр")
        print("0. Выход")

        choice = input("\nВыберите действие: ")

        if choice == "1":
            file_path = input("Путь к файлу: ")
            added = key_manager.add_keys_from_file(file_path)
            print(f"Добавлено {added} ключей")

        elif choice == "2":
            folder_path = input("Путь к папке (по умолчанию 'keys'): ") or "keys"
            results = key_manager.add_keys_from_folder(folder_path)
            total = sum(results.values())
            print(f"Всего добавлено {total} ключей")
            for file, count in results.items():
                print(f"  {file}: {count}")

        elif choice == "3":
            stats = key_manager.get_keys_stats()
            print("\nСтатистика по ключам:")
            for status, count in stats.items():
                print(f"  {status}: {count}")

        elif choice == "4":
            games = key_manager.get_games_list()
            print(f"\nСписок игр ({len(games)} шт.):")
            for game in games[:20]:  # Показываем только первые 20
                print(f"  {game['name']}: {game['available_keys']}/{game['total_keys']} "
                      f"(цена: €{game['min_price']:.2f})")
            if len(games) > 20:
                print(f"  ... и еще {len(games) - 20} игр")

        elif choice == "5":
            file_path = input("Путь к файлу с ценами: ")
            updated = key_manager.set_prices_from_file(file_path)
            print(f"Обновлено цен для {updated} ключей")

        elif choice == "6":
            print("Создание оферов на G2A...")
            print("Эта функция требует настроенного API сервера!")
            print("Сначала запустите: python main.py")

        elif choice == "7":
            print("Поиск Product ID...")
            print("Функция находится в разработке")

        elif choice == "0":
            break

        else:
            print("Неверный выбор")


if __name__ == "__main__":
    main_menu()