import asyncio
import os
from pathlib import Path
from database import PriceDatabase
from proxy_manager import ProxyManager
from g2a_id_parser import G2AIdParser
from g2a_api_client import G2AApiClient
from region_analyzer import RegionAnalyzer
from g2a_config import API_BASE_URL, DEFAULT_PREFIX, MIN_PRICE_TO_SELL, ADMIN_API_KEY,KEYS_FOLDER,RESULT_FOLDER
import httpx
from color_utils import print_success, print_error, print_warning, print_info

class KeyPriceParser:
    def __init__(self):
        self.db = PriceDatabase()
        self.proxy_manager = ProxyManager()
        self.id_parser = G2AIdParser(self.proxy_manager)
        self.api_client = G2AApiClient()
        self.region_analyzer = RegionAnalyzer()
        self.client = httpx.AsyncClient(verify=False)
        Path(RESULT_FOLDER).mkdir(exist_ok=True)

    async def process_files(self, auto_sell=False):
        if not os.path.exists(KEYS_FOLDER):
            print(f"Ошибка: {KEYS_FOLDER} папка не найдена")
            return

        key_files = [f for f in os.listdir(KEYS_FOLDER) if f.endswith('.txt')]
        if not key_files:
            print(f"Не найдены .txt файлы в {KEYS_FOLDER}")
            return

        print(f"Найдено {len(key_files)} файлов для обработки")

        if auto_sell:
            print("🔄 Режим автопродажи активен")

        for filename in key_files:
            await self.process_file(filename, auto_sell)

        self.db.close()
        print("Все файлы обработаны")

    async def process_file(self, filename, auto_sell=False):
        input_path = os.path.join(KEYS_FOLDER, filename)
        output_path = os.path.join(RESULT_FOLDER, filename)

        print(f"\nОбрабатываем файл: {filename}")

        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        await self.api_client.get_rate()

        offers_cache = {}
        if auto_sell:
            print("📥 Загружаем список существующих офферов...")
            await self.api_client.get_token()
            print_info("✓ Токен получен для автопродажи")
            offers_response = await self.api_client.get_offers()
            if offers_response.get("success"):
                offers_cache = offers_response.get("offers_cache", {})
                total_loaded = offers_response.get("total_loaded", 0)
                print(f"Загружено {total_loaded} офферов")
            else:
                print(f"Ошибка загрузки офферов: {offers_response.get('error')}")

        processed_lines = []
        steam_keys_count = 0
        regional_keys_count = 0
        sold_count = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                processed_lines.append(line)
                continue

            processed_line = await self.process_line(line, auto_sell, offers_cache)

            if processed_line is None:
                continue

            processed_lines.append(processed_line)

            if processed_line.startswith('selling'):
                sold_count += 1

            if self.is_steam_key(line):
                steam_keys_count += 1
                parts = line.split(' | ')
                if len(parts) > 3:
                    regional_keys_count += 1

        sorted_lines = self.sort_lines_by_price(processed_lines)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f'result/keys_result_{timestamp}.txt', 'w', encoding='utf-8') as f:
            for line in sorted_lines:
                f.write(line + '\n')

        print(f"Всего обработано: {steam_keys_count} (Региональных: {regional_keys_count})")
        if auto_sell:
            print(f"Выставлено на продажу: {sold_count} ключей")

    def sort_lines_by_price(self, lines):
        def get_price_from_line(line):
            if line.strip() == "":
                return -1, line

            if '€' in line and ' | ' in line:
                try:
                    price_part = line.split(' | ')[0]
                    if '€' in price_part:
                        price_str = price_part.replace('€', '')
                        price = float(price_str)
                        return price, line
                except (ValueError, IndexError):
                    return -1, line

            return -1, line

        selling_lines = []
        lines_with_prices = []
        lines_without_prices = []
        for line in lines:
            if line.strip().startswith('selling'):
                selling_lines.append(line)
            else:
                price, original_line = get_price_from_line(line)
                if price > 0:
                    lines_with_prices.append((price, original_line))
                else:
                    lines_without_prices.append(original_line)

        lines_with_prices.sort(key=lambda x: x[0], reverse=True)
        sorted_lines = (
                selling_lines +
                [line for price, line in lines_with_prices] +
                lines_without_prices
        )

        return sorted_lines

    def is_steam_key(self, line):
        parts = line.split(' | ')

        # Формат: Game | key | Restrictions (БЕЗ "Steam")
        # Или: €price | Game | key | Restrictions
        # Или: selling | €price | Game | key | Restrictions

        # Проверяем наличие хотя бы 2 частей (название игры и ключ)
        if '€' in parts[0] or parts[0].startswith('selling'):
            # Формат с ценой: нужно минимум 3 части
            return len(parts) >= 3
        else:
            # Обычный формат: нужно минимум 2 части
            return len(parts) >= 2



    async def process_line(self, line, auto_sell=False, offers_cache=None):
        parts = line.split(' | ')

        if line.startswith('selling'):
            return line

        if not self.is_steam_key(line):
            return line

        if '€' in parts[0]:
            game_name = parts[1].strip()
            key_value = parts[2].strip() if len(parts) > 2 else None
        else:
            game_name = parts[0].strip()
            key_value = parts[1].strip() if len(parts) > 1 else None

        target_region = self.region_analyzer.analyze_key_region(parts)

        cached_price = self.db.get_price(game_name, target_region)
        if cached_price is not None:
            print(f"Используем цену из бд {game_name} ({target_region}): €{cached_price}")

            if auto_sell and key_value and cached_price >= MIN_PRICE_TO_SELL:
                cached_g2a_id = self.db.get_g2a_id(game_name, target_region)
                if cached_g2a_id:
                    result = await self.sell_key_on_g2a(
                        game_name, key_value, cached_g2a_id, cached_price, offers_cache, parts
                    )
                    if result == "duplicate":
                        return None
                    elif result:
                        return f"selling | €{cached_price} | {line} | {target_region}"
                    else:
                        return f"€{cached_price} | {line} | {target_region}"
                else:
                    print(f"G2A ID не найден в кэше для {game_name}, пропускаем автопродажу")
                    return f"€{cached_price} | {line} | {target_region}"
            else:
                return f"€{cached_price} | {line} | {target_region}"

        cached_g2a_id = self.db.get_g2a_id(game_name, target_region)

        if cached_g2a_id is None:
            search_regions = self.region_analyzer.get_search_regions_priority(target_region)
            for region in search_regions:
                g2a_id = await self.id_parser.search_game_id(game_name, region)
                if g2a_id is not None:
                    self.db.save_g2a_id(game_name, g2a_id, region)
                    if region == target_region:
                        cached_g2a_id = g2a_id
                    break

        if cached_g2a_id is None:
            print(f"G2A ID не найден для {game_name}")
            return f"{line} | {target_region}"

        price_data = await self.api_client.get_product_price(cached_g2a_id)

        if price_data is not None:
            min_price = price_data['min_price']
            retail_price = price_data['retail_price']
            usd_price = price_data['min_price_usd']

            self.db.save_price(game_name, retail_price, target_region)

            print(f"Найдена цена для {game_name}: ${usd_price:.2f} (€{min_price:.2f})")

            if auto_sell and key_value and retail_price >= MIN_PRICE_TO_SELL:
                result = await self.sell_key_on_g2a(
                    game_name, key_value, cached_g2a_id, retail_price, offers_cache, parts
                )
                if result == "duplicate":
                    return None
                elif result:
                    return f"selling | €{retail_price} | {line} | {target_region}"
                else:
                    return f"€{retail_price} | {line} | {target_region}"
            else:
                return f"€{retail_price} | {line} | {target_region}"
        else:
            print(f"Цена не найдена {game_name}")
            return f"{line} | {target_region}"

    async def sell_key_on_g2a(self, game_name, key_value, product_id, price, offers_cache,line_parts=None):
        """Выставление ключа на продажу через G2A API"""
        try:
            if price < MIN_PRICE_TO_SELL:
                print(f"Цена {price}€ ниже минимальной {MIN_PRICE_TO_SELL}€, пропускаем")
                return False

            restrictions = None
            if line_parts:
                restrictions = self.region_analyzer.parse_restrictions_for_g2a(line_parts)
            # 1. Добавляем ключ в нашу БД
            response = await self.client.post(
                f"{API_BASE_URL}/admin/keys",
                json=[{
                    'game_name': game_name,
                    'product_id': product_id,
                    'key_value': key_value,
                    'price': price,
                    'prefix': DEFAULT_PREFIX
                }],
                headers={
                    'X-API-Key': ADMIN_API_KEY
                }
            )

            if response.status_code != 200:
                print(f"Ошибка добавления ключа в БД: {response.status_code}")
                return False

            response_data = response.json()
            if "errors" in response_data:
                errors = response_data["errors"]
                for error in errors:
                    if "Duplicate key" in error:
                        print(f"Ключ уже существует в БД: {key_value}")
                        return "duplicate"
                    else:
                        print(f"Ошибка добавления ключа: {error}")
                        return False


            # 2. Проверяем кеш офферов
            product_id_str = str(product_id)
            existing_offer = offers_cache.get(product_id_str) if offers_cache else None

            if existing_offer:
                current_stock = existing_offer.get('current_stock', 0)
                is_active = existing_offer.get('is_active', False)
                new_stock = current_stock + 1

                if is_active:
                    print(f"Обновляем активный оффер: stock {current_stock} → {new_stock}")
                else:
                    print(f"Активируем неактивный оффер: stock {current_stock} → {new_stock}")

                success = await self.update_offer_stock_and_activate(existing_offer['id'], new_stock, existing_offer, price)

                if success:
                    offers_cache[product_id_str]['current_stock'] = new_stock
                    offers_cache[product_id_str]['is_active'] = True
                    offers_cache[product_id_str]['price'] = price
                    print(f"✅ Ключ {game_name} добавлен к офферу за €{price:.2f}")
                    return True
                else:
                    print_error(f"❌ Не удалось обновить оффер")
                    return False
            else:
                success = await self.api_client.create_new_offer_with_fallback(game_name, product_id, price, offers_cache,restrictions=restrictions)
                return success

        except Exception as e:
            print(f"Ошибка при выставлении ключа на продажу: {e}")
            return False

    async def update_offer_stock_and_activate(self, offer_id, new_quantity, offer_info=None, new_price=None):
        try:
            offer_type = 'dropshipping'
            if offer_info and "offer_type" in offer_info:
                offer_type = offer_info["offer_type"]

            update_data = {
                "offerType": offer_type,
                "variant": {
                    "inventory": {
                        "size": new_quantity
                    },
                    "active": True,
                    "visibility": "all"
                }
            }

            # Если передана новая цена, обновляем и её
            if new_price is not None:
                adjusted_price = round(new_price, 2)
                update_data["variant"]["price"] = {
                    "retail": str(adjusted_price),
                    "business": str(adjusted_price)
                }
                print(f"   ℹ️  Устанавливаем рыночную цену: €{adjusted_price:.2f}")

            result = await self.api_client.update_offer_partial(offer_id, update_data)
            return result.get("success", False)
        except Exception as e:
            print(f"Ошибка обновления оффера: {e}")
            return False

    async def change_offer_prices(self):
        """Режим изменения цен на существующие офферы"""
        try:
            print("\n" + "=" * 60)
            print("РЕЖИМ ИЗМЕНЕНИЯ ЦЕН НА ОФФЕРЫ")
            print("=" * 60)

            # Получаем токен
            await self.api_client.get_token()
            await self.api_client.get_rate()

            print("\nЗагружаем список офферов...")
            offers_response = await self.api_client.get_offers()

            if not offers_response.get("success"):
                print(f"Ошибка загрузки офферов: {offers_response.get('error')}")
                return

            offers_cache = offers_response.get("offers_cache", {})

            if not offers_cache:
                print("Нет доступных офферов для изменения цен")
                return

            offers_list = []

            for product_id, offer_info in offers_cache.items():
                current_stock = offer_info.get("current_stock", 0)

                # Показываем только офферы с ключами в наличии
                if current_stock > 0:
                    offers_list.append({
                        "offer_id": offer_info.get("id"),
                        "product_id": product_id,
                        "product_name": offer_info.get("product_name", f"ID: {product_id}"),
                        "price": offer_info.get("price", "N/A"),
                        "stock": current_stock,
                        "is_active": offer_info.get("active", "active"),
                        "offer_type": offer_info.get("offer_type", "game")
                    })

            if not offers_list:
                print("Не удалось загрузить офферы")
                return

            offers_list.sort(key=lambda x: float(x["price"]) if x["price"] != "N/A" else 0, reverse=True)

            # Отображаем список игр с ценами
            print("\n" + "=" * 60)
            print("СПИСОК ОФФЕРОВ:")
            print("=" * 60)

            for idx, offer in enumerate(offers_list, 1):
                print(f"{idx}. €{offer['price']} | {offer['product_name']} | В наличии: {offer['stock']}")

            print("=" * 60)

            # Запрашиваем выбор игры
            while True:
                try:
                    choice = input("\nВведите номер игры (0 для выхода): ").strip()

                    if choice == "0":
                        print("Выход из режима изменения цен")
                        return

                    game_index = int(choice) - 1

                    if 0 <= game_index < len(offers_list):
                        selected_offer = offers_list[game_index]
                        break
                    else:
                        print(f"Введите число от 1 до {len(offers_list)}")
                except ValueError:
                    print("Введите корректное число")

            # Показываем выбранную игру
            print("\n" + "-" * 60)
            print(f"Выбрана игра: {selected_offer['product_name']}")
            print(f"Текущая цена: €{selected_offer['price']}")
            print(f"Склад: {selected_offer['stock']}")
            print("-" * 60)

            print("Загружаем детали оффера...")
            offer_details = await self.api_client.get_offer_details(selected_offer['offer_id'])

            if not offer_details.get("success"):
                print(f"Ошибка получения деталей оффера: {offer_details.get('error')}")
                return

            offer_data = offer_details.get("data", {})

            variant_data = {
                "status3": "active",
                "visibility": offer_data.get("visibility", "all"),
            }

            if "regions" in offer_data:
                variant_data["regions"] = offer_data["regions"]
            if "regionRestrictions" in offer_data:
                variant_data["regionRestrictions"] = offer_data["regionRestrictions"]

            while True:
                try:
                    new_price_input = input("\nВведите новую цену в EUR (0 для отмены): ").strip()

                    if new_price_input == "0":
                        print("Изменение цены отменено")
                        return

                    new_price = float(new_price_input)

                    if new_price <= 0:
                        print("Цена должна быть больше 0")
                        continue


                    # Меняем цену
                    success = await self.update_offer_price(
                            selected_offer['offer_id'],
                            new_price,
                            selected_offer['offer_type'],
                            variant_data
                        )

                    if success:
                        print_success(f"✅ Цена успешно изменена на €{new_price:.2f}")
                    else:
                        print_error("❌ Не удалось изменить цену")


                    return

                except ValueError:
                    print("Введите корректное число")

        except Exception as e:
            print(f"Ошибка в режиме изменения цен: {e}")

    async def update_offer_price(self, offer_id, new_price, offer_type, variant_data):
        """Обновление цены оффера через PATCH запрос (ИСПРАВЛЕНО)"""
        try:
            adjusted_price = round(new_price, 2)

            # Подготавливаем данные для PATCH запроса
            update_data = {
                "offerType": offer_type,
                "variant": {
                    "price": {
                        "retail": str(adjusted_price),
                        "business": str(adjusted_price)
                    },
                    "active": True,  # ✅ Всегда активируем при обновлении цены
                    "visibility": variant_data.get("visibility", "all")
                }
            }

            # Добавляем regions если есть
            if "regions" in variant_data:
                update_data["variant"]["regions"] = variant_data["regions"]

            # Добавляем regionRestrictions если есть
            if "regionRestrictions" in variant_data:
                update_data["variant"]["regionRestrictions"] = variant_data["regionRestrictions"]

            # Отправляем PATCH запрос
            result = await self.api_client.update_offer_partial(offer_id, update_data)

            if result.get("success"):
                print(f"✅ Цена обновлена: €{adjusted_price:.2f}")
                return True
            else:
                print(f"❌ Ошибка обновления: {result.get('error')}")
                return False

        except Exception as e:
            print(f"❌ Ошибка при обновлении цены: {e}")
            return False

    def extract_region_from_product_name(self, product_name):
        """Извлечение региона из названия продукта (последнее слово)"""
        from g2a_config import REGION_CODES

        if not product_name:
            return "GLOBAL"

        # Разбиваем название на слова
        words = product_name.strip().split()

        if not words:
            return "GLOBAL"

        # Берем последнее слово и проверяем, является ли оно регионом
        last_word = words[-1].upper()

        # Проверяем точное совпадение
        if last_word in REGION_CODES:
            return last_word

        # Проверяем частичные совпадения (например, "NORTH" для "NORTH_AMERICA")
        for region in REGION_CODES.keys():
            if last_word in region or region in last_word:
                return region

        return "GLOBAL"

    async def reduce_all_prices_by_percentage(self):
        """Режим массового снижения цен на все офферы на указанный процент"""
        try:
            print("\n" + "=" * 60)
            print("РЕЖИМ МАССОВОГО СНИЖЕНИЯ ЦЕН НА ВСЕ ОФФЕРЫ")
            print("=" * 60)

            # Получаем токен
            await self.api_client.get_token()
            await self.api_client.get_rate()
            print_info("✓ Токен получен")

            while True:
                try:
                    percentage_input = input("\nВведите процент снижения цен (например, 5 для снижения на 5%, 0 для отмены): ").strip()

                    if percentage_input == "0":
                        print("Отмена операции")
                        return

                    percentage = float(percentage_input)

                    if percentage <= 0 or percentage >= 100:
                        print("Процент должен быть больше 0 и меньше 100")
                        continue

                    break
                except ValueError:
                    print("Введите корректное число")

            print(f"\n📥 Загружаем список офферов...")
            offers_response = await self.api_client.get_offers()

            if not offers_response.get("success"):
                print_error(f"Ошибка загрузки офферов: {offers_response.get('error')}")
                return

            offers_cache = offers_response.get("offers_cache", {})

            if not offers_cache:
                print("Нет доступных офферов")
                return

            offers_to_update = []
            for product_id, offer_info in offers_cache.items():
                try:
                    current_price = float(offer_info.get("price", 0))
                    current_stock = offer_info.get("current_stock", 0)

                    # Обрабатываем только офферы с ключами в наличии
                    if current_price > 0 and current_stock > 0:
                        reduction_multiplier = 1 - (percentage / 100)
                        new_price = round(current_price * reduction_multiplier, 2)

                        if new_price < 0.01:
                            new_price = 0.01

                        offers_to_update.append({
                            "product_id": product_id,
                            "offer_id": offer_info.get("id"),
                            "product_name": offer_info.get("product_name", f"ID: {product_id}"),
                            "current_price": current_price,
                            "new_price": new_price,
                            "stock": offer_info.get("current_stock", 0),
                            "offer_type": offer_info.get("offer_type", "dropshipping"),
                            "is_active": offer_info.get("is_active", False)
                        })
                except (ValueError, TypeError):
                    continue

            if not offers_to_update:
                print("Нет офферов для обновления цен")
                return

            offers_to_update.sort(key=lambda x: x["current_price"], reverse=True)

            print(f"\n{'=' * 80}")
            print(f"Найдено {len(offers_to_update)} офферов для снижения цен на {percentage}%:")
            print(f"{'=' * 80}")

            for idx, offer in enumerate(offers_to_update[:10], 1):  # Показываем первые 10
                print(f"{idx}. €{offer['current_price']:.2f} → €{offer['new_price']:.2f} | {offer['product_name']} | Ключей: {offer['stock']}")

            if len(offers_to_update) > 10:
                print(f"... и еще {len(offers_to_update) - 10} офферов")

            print(f"{'=' * 80}")

            # Подтверждение
            confirm = input(f"\nСнизить цены на {len(offers_to_update)} офферах на {percentage}%? (yes/no): ").strip().lower()

            if confirm != "yes":
                print("Операция отменена")
                return

            total_updated = 0
            total_failed = 0

            for idx, offer in enumerate(offers_to_update, 1):
                offer_id = offer["offer_id"]
                product_name = offer["product_name"]
                current_price = offer["current_price"]
                new_price = offer["new_price"]
                offer_type = offer["offer_type"]

                print(f"\n[{idx}/{len(offers_to_update)}] 🔄 Обновляем: {product_name}")
                print(f"   Цена: €{current_price:.2f} → €{new_price:.2f}")

                offer_details = await self.api_client.get_offer_details(offer_id)

                if not offer_details.get("success"):
                    print_error(f"   ❌ Ошибка получения деталей: {offer_details.get('error')}")
                    total_failed += 1
                    continue

                offer_data = offer_details.get("data", {})

                variant_data = {
                    "status": "active",
                    "visibility": offer_data.get("visibility", "all"),
                }

                if "regions" in offer_data:
                    variant_data["regions"] = offer_data["regions"]
                if "regionRestrictions" in offer_data:
                    variant_data["regionRestrictions"] = offer_data["regionRestrictions"]

                success = await self.update_offer_price(
                    offer_id,
                    new_price,
                    offer_type,
                    variant_data
                )

                if success:
                    print_success(f"   ✓ Цена обновлена")
                    total_updated += 1

                    product_id = offer["product_id"]
                    region = self.extract_region_from_product_name(product_name)

                    game_name = product_name
                    if region in product_name:
                        game_name = product_name.replace(region, "").strip()

                    self.db.save_price(game_name, new_price, region)
                    print(f"   ✓ Цена обновлена в БД для {game_name} ({region})")
                else:
                    print_error(f"   ❌ Не удалось обновить цену")
                    total_failed += 1

                await asyncio.sleep(1.5)

            # Итоговая статистика
            print(f"\n{'=' * 80}")
            print_success("✅ ОПЕРАЦИЯ ЗАВЕРШЕНА")
            print(f"📊 Статистика:")
            print(f"   • Обработано офферов: {len(offers_to_update)}")
            print(f"   • Успешно обновлено: {total_updated}")
            print(f"   • Ошибок: {total_failed}")
            print(f"   • Снижение цен: {percentage}%")
            print(f"{'=' * 80}")

        except Exception as e:
            print_error(f"Ошибка в режиме массового снижения цен: {e}")

    async def remove_offers_by_price(self):
        """Режим снятия офферов с продажи по цене"""
        try:
            print("\n" + "=" * 60)
            print("РЕЖИМ СНЯТИЯ ОФФЕРОВ С ПРОДАЖИ ПО ЦЕНЕ")
            print("=" * 60)

            # Получаем токен
            await self.api_client.get_token()
            print_info("✓ Токен получен")

            # Запрашиваем максимальную цену
            while True:
                try:
                    max_price_input = input("\nВведите максимальную цену в EUR (офферы до этой цены будут удалены, 0 для отмены): ").strip()

                    if max_price_input == "0":
                        print("Отмена удаления офферов")
                        return

                    max_price = float(max_price_input)

                    if max_price <= 0:
                        print("Цена должна быть больше 0")
                        continue

                    break
                except ValueError:
                    print("Введите корректное число")

            print(f"\n📥 Загружаем список офферов...")
            offers_response = await self.api_client.get_offers()

            if not offers_response.get("success"):
                print_error(f"Ошибка загрузки офферов: {offers_response.get('error')}")
                return

            offers_cache = offers_response.get("offers_cache", {})

            if not offers_cache:
                print("Нет доступных офферов")
                return

            # Фильтруем офферы по цене (только активные)
            offers_to_remove = []
            for product_id, offer_info in offers_cache.items():
                try:
                    offer_price = float(offer_info.get("price", 0))
                    is_active = offer_info.get("is_active", False)

                    if offer_price <= max_price and is_active:
                        offers_to_remove.append({
                            "product_id": product_id,
                            "offer_id": offer_info.get("id"),
                            "product_name": offer_info.get("product_name", f"ID: {product_id}"),
                            "price": offer_price,
                            "stock": offer_info.get("current_stock", 0),
                            "offer_type": offer_info.get("offer_type", "dropshipping")
                        })
                except (ValueError, TypeError):
                    continue

            if not offers_to_remove:
                print(f"\nНет офферов с ценой <= €{max_price}")
                return

            # Показываем список офферов для снятия с продажи
            print(f"\n{'=' * 60}")
            print(f"Найдено {len(offers_to_remove)} офферов для снятия с продажи:")
            print(f"{'=' * 60}")

            for idx, offer in enumerate(offers_to_remove, 1):
                print(f"{idx}. €{offer['price']} | {offer['product_name']} | Ключей: {offer['stock']}")

            print(f"{'=' * 60}")

            # Подтверждение
            confirm = input(f"\nСнять с продажи {len(offers_to_remove)} офферов? (yes/no): ").strip().lower()

            if confirm != "yes":
                print("Операция отменена")
                return

            # Создаем файл для результатов
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(RESULT_FOLDER) / f"removed_from_selling_{timestamp}.txt"

            total_removed_offers = 0
            total_removed_keys = 0

            # Открываем файл для записи
            with open(output_path, 'w', encoding='utf-8') as result_file:
                # Снимаем офферы с продажи
                for offer in offers_to_remove:
                    product_id = offer["product_id"]
                    offer_id = offer["offer_id"]
                    product_name = offer["product_name"]
                    offer_type = offer.get("offer_type", "dropshipping")

                    print(f"\n🗑️  Обрабатываем оффер: {product_name} (€{offer['price']})")

                    # 1. Обнуляем инвентарь и деактивируем оффер
                    print(f"🔄 Обнуляем инвентарь и деактивируем оффер...")
                    update_inventory_result = await self.api_client.update_offer_partial(offer_id, {
                        "offerType": offer_type,
                        "variant": {
                            "inventory": {
                                "size": 0
                            },
                            "active": False
                        }
                    })

                    if not update_inventory_result.get("success"):
                        print_error(f"❌ Не удалось обнулить инвентарь: {update_inventory_result.get('error')}")
                        continue
                    else:
                        print_success(f"✓ Инвентарь обнулен и оффер деактивирован")
                        total_removed_offers += 1

                    # 2. Получаем все ключи этого оффера с нашего сервера
                    try:
                        response = await self.client.get(
                            f"{API_BASE_URL}/admin/keys/by-product/{product_id}",
                            params={"exclude_sold": "true"},
                            headers={'X-API-Key': ADMIN_API_KEY}
                        )

                        if response.status_code != 200:
                            print_error(f"❌ Ошибка получения ключей с сервера: {response.status_code}")
                            continue

                        keys_data = response.json()
                        keys = keys_data.get("keys", [])

                        if not keys:
                            print("ℹ️  Нет ключей для обновления")
                            continue

                        print(f"📦 Найдено {len(keys)} ключей")

                        # 3. Обновляем статус ключей на сервере
                        key_ids = [key["id"] for key in keys]

                        update_response = await self.client.patch(
                            f"{API_BASE_URL}/admin/keys/status",
                            json={
                                "key_ids": key_ids,
                                "new_status": "removed_from_sale"
                            },
                            headers={'X-API-Key': ADMIN_API_KEY}
                        )

                        if update_response.status_code != 200:
                            print_error(f"❌ Ошибка обновления статуса ключей: {update_response.status_code}")
                            continue

                        print_success(f"✓ Статус {len(keys)} ключей обновлен на 'removed_from_sale'")
                        total_removed_keys += len(keys)

                        # 4. Извлекаем регион из названия
                        region = self.extract_region_from_product_name(product_name)

                        # 5. Записываем ключи в файл сразу
                        game_name = keys[0].get("game_name", "Unknown Game")
                        for key in keys:
                            line = f"{game_name} | {key['key_value']} | {region}\n"
                            result_file.write(line)

                        result_file.flush()  # Сохраняем на диск
                        print(f"✓ Регион: {region}, записано {len(keys)} ключей в файл")

                    except Exception as e:
                        print_error(f"❌ Ошибка обработки ключей: {e}")
                        continue

            # Итоговая статистика
            print(f"\n{'=' * 60}")
            print_success(f"✅ Результаты записаны в: {output_path}")
            print(f"📊 Статистика:")
            print(f"   • Снято с продажи офферов: {total_removed_offers}")
            print(f"   • Ключей снято с продажи: {total_removed_keys}")
            print(f"{'=' * 60}")

        except Exception as e:
            print_error(f"Ошибка в режиме снятия офферов с продажи: {e}")

    async def view_price_stats(self):
        try:
            print("\n" + "=" * 60)
            print("СТАТИСТИКА ИЗМЕНЕНИЙ ЦЕН")
            print("=" * 60)

            print("\nВыберите период:")
            print("1. За сегодня")
            print("2. За последние 7 дней")
            print("3. За последние 30 дней")
            print("0. Назад")

            choice = input("\nВведите номер: ").strip()

            if choice == "0":
                return

            period_map = {
                "1": "day",
                "2": "week",
                "3": "month"
            }

            period = period_map.get(choice)
            if not period:
                print_error("Неверный выбор")
                return

            print(f"\nЗагрузка статистики...")

            response = await self.client.get(
                f"{API_BASE_URL}/admin/price-stats?period={period}",
                headers={'X-API-Key': ADMIN_API_KEY}
            )

            if response.status_code != 200:
                print_error(f"Ошибка получения статистики: {response.status_code}")
                return

            data = response.json()

            print(f"\n{'=' * 80}")
            print(f"СТАТИСТИКА ЗА ПЕРИОД: {data['period']}")
            print(f"{'=' * 80}")

            summary = data['summary']
            print(f"\nОбщая сводка:")
            print(f"  Всего изменений цен: {summary['total_changes']}")
            print(f"  Понижений цен: {summary['price_decreases']}")
            print(f"  Повышений цен: {summary['price_increases']}")
            print(f"  Среднее изменение цены: €{summary['avg_price_change']:.2f}")
            print(f"  Общее изменение цен: €{summary['total_price_change']:.2f}")
            print(f"  Изменений сегодня: {summary['today_changes']}")

            if data['top_changed_games']:
                print(f"\n{'=' * 80}")
                print("ТОП-20 ИГР С НАИБОЛЬШИМИ ИЗМЕНЕНИЯМИ:")
                print(f"{'=' * 80}")

                for idx, game in enumerate(data['top_changed_games'], 1):
                    print(f"\n{idx}. {game['game_name']}")
                    print(f"   Изменений: {game['change_count']}")
                    print(f"   Мин. старая цена: €{game['min_old_price']:.2f}")
                    print(f"   Макс. новая цена: €{game['max_new_price']:.2f}")
                    print(f"   Среднее изменение: €{game['avg_change']:.2f}")

            if data['recent_changes']:
                print(f"\n{'=' * 80}")
                print("ПОСЛЕДНИЕ ИЗМЕНЕНИЯ (до 100):")
                print(f"{'=' * 80}")

                for change in data['recent_changes'][:20]:
                    direction = "↓" if change['change_amount'] < 0 else "↑"
                    print(f"\n{change['created_at']}")
                    print(f"  {change['game_name']} (ID: {change['product_id']})")
                    print(f"  Старая цена: €{change['old_price']:.2f}")
                    print(f"  Новая цена: €{change['new_price']:.2f}")
                    print(f"  Рыночная цена: €{change['market_price']:.2f}")
                    print(f"  Изменение: {direction} €{abs(change['change_amount']):.2f}")
                    print(f"  Причина: {change['change_reason']}")

                if len(data['recent_changes']) > 20:
                    print(f"\n... и еще {len(data['recent_changes']) - 20} изменений")

            print(f"\n{'=' * 80}")
            input("\nНажмите Enter для продолжения...")

        except Exception as e:
            print_error(f"Ошибка при получении статистики: {e}")


async def main():
    while True:
        print("\n" + "=" * 40)
        print("ГЛАВНОЕ МЕНЮ")
        print("=" * 40)
        print("1. Обычный парсинг цен")
        print("2. Парсинг + автовыставление на G2A")
        print("3. Изменение цен на офферы")
        print("4. Удаление офферов по цене")
        print("5. Массовое снижение цен на %")
        print("6. Статистика автоизменений цен")
        print("0. Выход")
        print("-" * 40)

        choice = input("Выберите режим: ").strip()

        if choice == "1":
            await run_price_parser(auto_sell=False)

        elif choice == "2":
            await run_price_parser(auto_sell=True)

        elif choice == "3":
            parser = KeyPriceParser()
            await parser.change_offer_prices()

        elif choice == "4":
            parser = KeyPriceParser()
            await parser.remove_offers_by_price()

        elif choice == "5":
            parser = KeyPriceParser()
            await parser.reduce_all_prices_by_percentage()

        elif choice == "6":
            parser = KeyPriceParser()
            await parser.view_price_stats()

        elif choice == "0":
            print("Выход из программы")
            break

        else:
            print_error("Неверный выбор")



async def run_price_parser(auto_sell=False):

    parser = KeyPriceParser()

    if auto_sell:
        print("\n🚀 Режим: Парсинг + автовыставление на G2A")
        print(f"Минимальная цена для продажи: €{MIN_PRICE_TO_SELL}")
    else:
        print("\n📊 Режим: Обычный парсинг цен")

    await parser.process_files(auto_sell=auto_sell)


if __name__ == "__main__":
    asyncio.run(main())