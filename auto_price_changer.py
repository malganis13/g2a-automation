import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from g2a_api_client import G2AApiClient
from database import PriceDatabase
from telegram_notifier import notifier
from g2a_config import (
    AUTO_PRICE_CHANGE_ENABLED,
    AUTO_PRICE_CHECK_INTERVAL,
    AUTO_PRICE_UNDERCUT_AMOUNT,
    AUTO_PRICE_MIN_PRICE,
    AUTO_PRICE_MAX_PRICE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    API_BASE_URL,
    ADMIN_API_KEY,
    G2A_API_BASE
)
import httpx


class AutoPriceSettings:
    """Настройки автоматического изменения цен"""

    def __init__(self, settings_file="auto_price_settings.json"):
        self.settings_file = settings_file
        self.settings = self.load_settings()

    def load_settings(self):
        """Загрузка настроек из файла"""
        default_settings = {
            "enabled": False,
            "telegram_notifications": True,
            "check_interval": 1800,
            "undercut_amount": 0.01,
            "min_price": 0.1,
            "max_price": 100.0,
            "daily_limit": 20,
            "excluded_products": [],  # ID товаров, которые НЕ менять
            "included_products": []  # Если указано - менять ТОЛЬКО эти
        }

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
            except:
                pass

        return default_settings

    def save_settings(self):
        """Сохранение настроек"""
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def is_product_allowed(self, product_id):
        """Проверка, разрешено ли менять цену для этого товара"""
        product_id = str(product_id)

        # ✅ НОВАЯ ЛОГИКА: Простая и понятная

        # 1. Если глобально выключено - ничего не трогаем
        if not self.settings.get("enabled", False):
            return False

        # 2. Если товар в чёрном списке - не трогаем
        if product_id in self.settings.get("excluded_products", []):
            return False

        # 3. Если есть белый список - трогаем ТОЛЬКО его
        included = self.settings.get("included_products", [])
        if included:
            return product_id in included

        # 4. Иначе - трогаем всё (глобально включено, нет ограничений)
        return True

    def toggle_product(self, product_id, enabled=True):
        """Включить/выключить автоизменение для товара"""
        product_id = str(product_id)

        if enabled:
            # ✅ ВКЛЮЧАЕМ: убираем из чёрного списка, добавляем в белый
            excluded = self.settings.get("excluded_products", [])
            if product_id in excluded:
                excluded.remove(product_id)

            # Добавляем в белый список (для точечного управления)
            included = self.settings.get("included_products", [])
            if product_id not in included:
                included.append(product_id)

            self.settings["excluded_products"] = excluded
            self.settings["included_products"] = included
        else:
            # ✅ ВЫКЛЮЧАЕМ: убираем из белого списка, добавляем в чёрный
            included = self.settings.get("included_products", [])
            if product_id in included:
                included.remove(product_id)

            # Добавляем в чёрный список
            excluded = self.settings.get("excluded_products", [])
            if product_id not in excluded:
                excluded.append(product_id)

            self.settings["excluded_products"] = excluded
            self.settings["included_products"] = included

        self.save_settings()


class DailyLimitTracker:
    """Отслеживание дневного лимита изменений"""

    def __init__(self, limit_file="daily_limit.json"):
        self.limit_file = limit_file
        self.data = self.load_data()

    def load_data(self):
        """Загрузка данных о изменениях"""
        if os.path.exists(self.limit_file):
            try:
                with open(self.limit_file, 'r') as f:
                    return json.load(f)
            except:
                pass

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "changes_count": 0,
            "changes": []
        }

    def save_data(self):
        """Сохранение данных"""
        with open(self.limit_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def reset_if_new_day(self):
        """Сброс счётчика если новый день"""
        today = datetime.now().strftime("%Y-%m-%d")

        if self.data.get("date") != today:
            self.data = {
                "date": today,
                "changes_count": 0,
                "changes": []
            }
            self.save_data()

    def can_change(self, daily_limit):
        """Проверка, можно ли ещё менять цены сегодня"""
        self.reset_if_new_day()
        return self.data["changes_count"] < daily_limit

    def record_change(self, product_id, old_price, new_price, product_name=""):
        """Записать изменение"""
        self.reset_if_new_day()

        self.data["changes_count"] += 1
        self.data["changes"].append({
            "timestamp": datetime.now().isoformat(),
            "product_id": product_id,
            "product_name": product_name,
            "old_price": old_price,
            "new_price": new_price
        })

        self.save_data()

    def get_remaining_changes(self, daily_limit):
        """Сколько изменений осталось сегодня"""
        self.reset_if_new_day()
        return daily_limit - self.data["changes_count"]


class AutoPriceChanger:
    """Автоматическое изменение цен на основе конкурентов"""

    def __init__(self):
        self.api_client = G2AApiClient()
        self.db = PriceDatabase()
        self.settings = AutoPriceSettings()
        self.limit_tracker = DailyLimitTracker()
        self.running = False
        self.httpx_client = httpx.AsyncClient(verify=False)

    async def cleanup(self):
        """Корректное завершение всех ресурсов"""
        try:
            # Закрываем httpx клиент
            if hasattr(self, 'httpx_client'):
                await self.httpx_client.aclose()

            # Закрываем сессию API клиента
            if hasattr(self.api_client, 'session') and self.api_client.session:
                await self.api_client.session.close()

        except Exception as e:
            print(f"⚠️  Ошибка при завершении: {e}")

    async def start(self):
        """Запуск автоматического изменения цен"""
        print("🤖 Автоматическое изменение цен запущено")
        print(f"📋 Настройки:")
        print(f"   Включено: {self.settings.settings.get('enabled')}")
        print(f"   Telegram: {self.settings.settings.get('telegram_notifications')}")
        print(f"   Интервал: {self.settings.settings.get('check_interval')}с")
        print(f"   Дневной лимит: {self.settings.settings.get('daily_limit')}")

        if not self.settings.settings.get("enabled"):
            print("❌ Автоматизация отключена в настройках")
            return

        await self.api_client.get_token()
        await self.api_client.get_rate()

        self.running = True

        while self.running:
            try:
                print(f"\n{'=' * 60}")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Проверка цен...")
                print(f"{'=' * 60}")

                # Проверяем дневной лимит
                daily_limit = self.settings.settings.get("daily_limit", 20)
                remaining = self.limit_tracker.get_remaining_changes(daily_limit)

                print(f"📊 Осталось изменений сегодня: {remaining}/{daily_limit}")

                if remaining <= 0:
                    print("⚠️ Достигнут дневной лимит изменений!")

                    # Ждём до следующего дня
                    now = datetime.now()
                    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    wait_seconds = (tomorrow - now).total_seconds()

                    print(f"⏳ Следующая проверка в 00:00 ({wait_seconds / 3600:.1f} часов)")
                    await asyncio.sleep(wait_seconds)
                    continue

                # Получаем все офферы
                offers_response = await self.api_client.get_offers()

                if not offers_response.get("success"):
                    print(f"❌ Ошибка получения офферов: {offers_response.get('error')}")
                    await asyncio.sleep(60)
                    continue

                offers = offers_response.get("offers_cache", {})
                print(f"📦 Найдено {len(offers)} офферов")

                changed_count = 0

                for product_id, offer_info in offers.items():
                    # Проверяем лимит
                    if changed_count >= remaining:
                        print("⚠️ Достигнут дневной лимит!")
                        break

                    # Пропускаем неактивные
                    if not offer_info.get("is_active"):
                        continue

                    # Проверяем, разрешено ли менять этот товар
                    if not self.settings.is_product_allowed(product_id):
                        print(f"⏭️  Пропускаем {offer_info.get('product_name')} (отключен)")
                        continue

                    # Проверяем рыночную цену
                    market_price = await self.check_market_price(product_id)

                    if market_price is None:
                        continue

                    current_price = float(offer_info.get("price", 0))

                    # Рассчитываем новую цену
                    undercut = self.settings.settings.get("undercut_amount", 0.01)
                    new_price = market_price - undercut

                    # Проверяем лимиты
                    min_price = self.settings.settings.get("min_price", 0.1)
                    max_price = self.settings.settings.get("max_price", 100.0)

                    if new_price < min_price:
                        new_price = min_price

                    if new_price > max_price:
                        new_price = max_price

                    # Округляем до 2 знаков
                    new_price = round(new_price, 2)

                    # Если цена изменилась значительно
                    if abs(new_price - current_price) > 0.01:
                        success = await self.update_offer_price(
                            offer_info.get("id"),
                            product_id,
                            new_price,
                            offer_info.get("offer_type", "dropshipping"),
                            market_price
                        )

                        if success:
                            product_name = offer_info.get('product_name', 'Unknown')

                            print(f"✅ {product_name}")
                            print(f"   Старая цена: €{current_price:.2f}")
                            print(f"   Новая цена: €{new_price:.2f}")
                            print(f"   Рынок: €{market_price:.2f}")

                            # Записываем изменение
                            self.limit_tracker.record_change(
                                product_id,
                                current_price,
                                new_price,
                                product_name
                            )

                            changed_count += 1

                            # Сохраняем в базу для статистики
                            await self.save_price_change_stats(
                                product_id,
                                product_name,
                                current_price,
                                new_price,
                                market_price,
                                "auto_undercut"
                            )

                            # Telegram уведомление
                            if self.settings.settings.get("telegram_notifications"):
                                await self.send_telegram_notification(
                                    product_name,
                                    current_price,
                                    new_price,
                                    market_price
                                )

                        # Пауза между изменениями
                        await asyncio.sleep(2)

                print(f"\n{'=' * 60}")
                print(f"📊 Итоги проверки:")
                print(f"   Изменено цен: {changed_count}")
                print(f"   Осталось на сегодня: {remaining - changed_count}/{daily_limit}")
                print(f"{'=' * 60}")

                # Ждем следующей проверки
                # ✅ ИСПРАВЛЕНИЕ: Ждем с проверкой флага
                interval = self.settings.settings.get("check_interval", 1800)
                print(f"\n⏳ Следующая проверка через {interval // 60} минут ({interval}с)")

                for _ in range(interval):
                    if not self.running:
                        print("🛑 Остановка во время ожидания")
                        return
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()

                # Ждём минуту перед повтором (с проверкой флага)
                for _ in range(60):
                    if not self.running:
                        return
                    await asyncio.sleep(1)

        await self.cleanup()
        print("✅ Автоизменение цен остановлено")

    def stop(self):
        """Остановка автоматизации"""
        self.running = False
        print("🛑 Запрошена остановка автоизменения...")

    async def check_market_price(self, product_id):
        """Проверка рыночной цены (ИСПРАВЛЕНО)"""
        try:
            # ✅ ИСПРАВЛЕНИЕ: Используем httpx вместо curl_cffi
            import httpx

            # Получаем свежий токен
            if not self.api_client.token:
                await self.api_client.get_token()

            url = f"{G2A_API_BASE}/v1/products"
            params = {
                "id": product_id,
                "includeOutOfStock": "true"
            }

            headers = {
                "Authorization": f"Bearer {self.api_client.token}",
                "Accept": "application/json"
            }

            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 401:
                    # Токен истёк, обновляем
                    print("   ⚠️  Токен истёк, обновляем...")
                    await self.api_client.get_token()

                    # Повторяем запрос с новым токеном
                    headers["Authorization"] = f"Bearer {self.api_client.token}"
                    response = await client.get(url, params=params, headers=headers)

                if response.status_code != 200:
                    print(f"   ⚠️  HTTP {response.status_code} для {product_id}")
                    return None

                data = response.json()
                products = data.get("docs", [])

                if not products:
                    return None

                product = products[0]
                retail_price = product.get("retailMinBasePrice")

                if retail_price is not None:
                    return float(retail_price)

            return None

        except Exception as e:
            print(f"   ⚠️ Ошибка получения цены для {product_id}: {e}")
            return None

    async def update_offer_price(self, offer_id, product_id, new_price, offer_type, market_price):
        """Обновление цены оффера"""
        try:
            # Получаем детали оффера
            details = await self.api_client.get_offer_details(offer_id)

            if not details.get("success"):
                print(f"   ❌ Не удалось получить детали оффера")
                return False

            offer_data = details.get("data", {})

            # Обновляем цену
            update_data = {
                "offerType": offer_type,
                "variant": {
                    "price": {
                        "retail": str(new_price),
                        "business": str(new_price)
                    },
                    "active": True,
                    "visibility": offer_data.get("visibility", "all")
                }
            }

            # Добавляем regions если есть
            if "regions" in offer_data:
                update_data["variant"]["regions"] = offer_data["regions"]

            if "regionRestrictions" in offer_data:
                update_data["variant"]["regionRestrictions"] = offer_data["regionRestrictions"]

            result = await self.api_client.update_offer_partial(offer_id, update_data)

            return result.get("success", False)

        except Exception as e:
            print(f"   ❌ Ошибка обновления цены: {e}")
            return False

    async def save_price_change_stats(self, product_id, game_name, old_price, new_price, market_price, reason):
        """Сохранение статистики изменений в базу (через API сервера)"""
        try:
            response = await self.httpx_client.post(
                f"{API_BASE_URL}/admin/price-changes",
                json={
                    "product_id": str(product_id),
                    "game_name": game_name,
                    "old_price": old_price,
                    "new_price": new_price,
                    "market_price": market_price,
                    "change_reason": reason
                },
                headers={'X-API-Key': ADMIN_API_KEY}
            )
        except:
            pass  # Игнорируем ошибки сохранения статистики

    async def send_telegram_notification(self, game_name, old_price, new_price, market_price):
        """Отправка уведомления в Telegram"""
        try:
            # ✅ ИСПРАВЛЕНО: Используем send_price_change_notification вместо send_sale_notification
            await notifier.send_price_change_notification(
                game_name=game_name,
                old_price=old_price,
                new_price=new_price,
                market_price=market_price,
                reason="автоизменение",
                min_competitor_price=market_price,
                change_reason="Автоматическое изменение на основе рыночной цены"
            )
        except Exception as e:
            print(f"   ⚠️ Ошибка отправки в Telegram: {e}")


async def main():
    """Запуск автоматизации"""
    changer = AutoPriceChanger()

    try:
        await changer.start()
    except KeyboardInterrupt:
        changer.stop()


if __name__ == "__main__":
    asyncio.run(main())