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
            "undercut_amount": 0.05,
            "min_price": 0.1,
            "max_price": 100.0,
            "daily_limit": 20,
            "excluded_products": [],
            "included_products": []
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
        
        if not self.settings.get("enabled", False):
            return False
        
        if product_id in self.settings.get("excluded_products", []):
            return False
        
        included = self.settings.get("included_products", [])
        if included:
            return product_id in included
        
        return True
    
    def toggle_product(self, product_id, enabled=True):
        """Включить/выключить автоизменение для товара"""
        product_id = str(product_id)
        
        if enabled:
            excluded = self.settings.get("excluded_products", [])
            if product_id in excluded:
                excluded.remove(product_id)
            
            included = self.settings.get("included_products", [])
            if product_id not in included:
                included.append(product_id)
            
            self.settings["excluded_products"] = excluded
            self.settings["included_products"] = included
        else:
            included = self.settings.get("included_products", [])
            if product_id in included:
                included.remove(product_id)
            
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
            if hasattr(self, 'httpx_client'):
                await self.httpx_client.aclose()
            if hasattr(self.api_client, 'session') and self.api_client.session:
                await self.api_client.session.close()
        except Exception as e:
            print(f"⚠️ Ошибка при завершении: {e}")
    
    # ✅ НОВАЯ ФУНКЦИЯ 1: Получить мою текущую цену
    async def get_my_current_offer_price(self, product_id):
        """Получить мою текущую цену за конкретный товар"""
        try:
            offers_result = await self.api_client.get_offers()
            
            if not offers_result.get('success'):
                return None
            
            offers_cache = offers_result.get('offers_cache', {})
            
            if str(product_id) in offers_cache:
                offer = offers_cache[str(product_id)]
                price = offer.get('price', {})
                
                if isinstance(price, dict):
                    my_price = float(price.get('retail', 0))
                else:
                    my_price = float(price)
                
                return my_price
            else:
                return None
                
        except Exception as e:
            print(f"⚠️ Ошибка получения моей цены: {e}")
            return None
    
    # ✅ НОВАЯ ФУНКЦИЯ 2: Получить информацию о рынке (для GUI)
    async def get_market_info(self, product_id):
        """
        Получить информацию о рынке для оффера (используется в GUI)
        Возвращает словарь с информацией о TOP 1, позиции и разнице
        """
        try:
            # Получить рыночную цену (TOP 1)
            market_price = await self.check_market_price(product_id)
            if market_price is None:
                return None
            
            # Получить мою текущую цену
            my_price = await self.get_my_current_offer_price(product_id)
            if my_price is None:
                return None
            
            # Вычислить позицию и разницу
            if abs(market_price - my_price) < 0.01:
                position = "1-е место (ты минимум!)"
                position_number = 1
                margin = 0.0
                color = "yellow"
            elif market_price < my_price:
                position = "2-е место"
                position_number = 2
                margin = my_price - market_price
                color = "green"
            else:
                # Ошибка - мы дешевле рынка?
                position = "Ошибка: дешевле TOP 1"
                position_number = 0
                margin = my_price - market_price
                color = "red"
            
            return {
                "success": True,
                "market_price": round(market_price, 2),
                "my_price": round(my_price, 2),
                "position": position,
                "position_number": position_number,
                "margin": round(margin, 2),
                "color": color
            }
            
        except Exception as e:
            print(f"❌ Ошибка получения рыночной информации: {e}")
            return None
    
    # ✅ НОВАЯ ФУНКЦИЯ 3: Получить рыночную цену КОНКУРЕНТА (безопасно)
    async def check_market_price_safe(self, product_id):
        """Получить рыночную цену КОНКУРЕНТА (исключая свою цену)"""
        try:
            market_price = await self.check_market_price(product_id)
            if market_price is None:
                return None
            
            my_price = await self.get_my_current_offer_price(product_id)
            
            if my_price and abs(market_price - my_price) < 0.01:
                print(f"   ⚠️ Я единственный продавец (€{market_price:.2f}), не меняю цену")
                return None
            
            return market_price
            
        except Exception as e:
            print(f"❌ Ошибка проверки рыночной цены: {e}")
            return None
    
    async def start(self):
        """Запуск автоматического изменения цен"""
        print("🤖 Автоматическое изменение цен запущено")
        print(f"📋 Настройки:")
        print(f"  Включено: {self.settings.settings.get('enabled')}")
        print(f"  Telegram: {self.settings.settings.get('telegram_notifications')}")
        print(f"  Интервал: {self.settings.settings.get('check_interval')}с")
        print(f"  Margin (undercut): €{self.settings.settings.get('undercut_amount'):.2f}")
        print(f"  Дневной лимит: {self.settings.settings.get('daily_limit')}")
        
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
                
                daily_limit = self.settings.settings.get("daily_limit", 20)
                remaining = self.limit_tracker.get_remaining_changes(daily_limit)
                print(f"📊 Осталось изменений сегодня: {remaining}/{daily_limit}")
                
                if remaining <= 0:
                    print("⚠️ Достигнут дневной лимит изменений!")
                    now = datetime.now()
                    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    wait_seconds = (tomorrow - now).total_seconds()
                    print(f"⏳ Следующая проверка в 00:00 ({wait_seconds / 3600:.1f} часов)")
                    await asyncio.sleep(wait_seconds)
                    continue
                
                offers_response = await self.api_client.get_offers()
                
                if not offers_response.get("success"):
                    print(f"❌ Ошибка получения офферов: {offers_response.get('error')}")
                    await asyncio.sleep(60)
                    continue
                
                offers = offers_response.get("offers_cache", {})
                print(f"📦 Найдено {len(offers)} офферов")
                
                changed_count = 0
                
                for product_id, offer_info in offers.items():
                    if changed_count >= remaining:
                        print("⚠️ Достигнут дневной лимит!")
                        break
                    
                    if not offer_info.get("is_active"):
                        continue
                    
                    if not self.settings.is_product_allowed(product_id):
                        continue
                    
                    market_price = await self.check_market_price_safe(product_id)
                    
                    if market_price is None:
                        continue
                    
                    current_price = float(offer_info.get("price", 0))
                    
                    margin = self.settings.settings.get("undercut_amount", 0.05)
                    new_price = market_price + margin
                    
                    min_price = self.settings.settings.get("min_price", 0.1)
                    max_price = self.settings.settings.get("max_price", 100.0)
                    
                    if new_price < min_price:
                        new_price = min_price
                    if new_price > max_price:
                        new_price = max_price
                    
                    new_price = round(new_price, 2)
                    
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
                            print(f"   Рынок (TOP 1): €{market_price:.2f}")
                            print(f"   Новая цена: €{new_price:.2f} (TOP 1 + €{margin:.2f})")
                            
                            self.limit_tracker.record_change(
                                product_id,
                                current_price,
                                new_price,
                                product_name
                            )
                            
                            changed_count += 1
                            
                            await self.save_price_change_stats(
                                product_id,
                                product_name,
                                current_price,
                                new_price,
                                market_price,
                                "auto_margin"
                            )
                            
                            # ✅ ИСПРАВЛЕННОЕ Telegram уведомление
                            if self.settings.settings.get("telegram_notifications"):
                                await self.send_telegram_notification(
                                    product_name,
                                    current_price,
                                    new_price,
                                    market_price,
                                    margin
                                )
                            
                            await asyncio.sleep(2)
                
                print(f"\n{'=' * 60}")
                print(f"📊 Итоги проверки:")
                print(f"  Изменено цен: {changed_count}")
                print(f"  Осталось на сегодня: {remaining - changed_count}/{daily_limit}")
                print(f"{'=' * 60}")
                
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
        """Проверка рыночной цены"""
        try:
            import httpx
            
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
                    print("  ⚠️ Токен истёк, обновляем...")
                    await self.api_client.get_token()
                    headers["Authorization"] = f"Bearer {self.api_client.token}"
                    response = await client.get(url, params=params, headers=headers)
                
                if response.status_code != 200:
                    print(f"  ⚠️ HTTP {response.status_code} для {product_id}")
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
            print(f"  ⚠️ Ошибка получения цены для {product_id}: {e}")
            return None
    
    async def update_offer_price(self, offer_id, product_id, new_price, offer_type, market_price):
        """Обновление цены оффера"""
        try:
            details = await self.api_client.get_offer_details(offer_id)
            
            if not details.get("success"):
                print(f"  ❌ Не удалось получить детали оффера")
                return False
            
            offer_data = details.get("data", {})
            
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
            
            if "regions" in offer_data:
                update_data["variant"]["regions"] = offer_data["regions"]
            
            if "regionRestrictions" in offer_data:
                update_data["variant"]["regionRestrictions"] = offer_data["regionRestrictions"]
            
            result = await self.api_client.update_offer_partial(offer_id, update_data)
            return result.get("success", False)
            
        except Exception as e:
            print(f"  ❌ Ошибка обновления цены: {e}")
            return False
    
    async def save_price_change_stats(self, product_id, game_name, old_price, new_price, market_price, reason):
        """Сохранение статистики изменений в базу"""
        try:
            await self.httpx_client.post(
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
            pass
    
    # ✅ ИСПРАВЛЕННАЯ ФУНКЦИЯ: Telegram уведомление с полной информацией
    async def send_telegram_notification(self, game_name, old_price, new_price, market_price, margin):
        """
        Отправка полного уведомления в Telegram об автоизменении цены
        Теперь показывает: старую цену, новую цену, TOP 1, margin
        """
        try:
            # Определяем направление
            if new_price > old_price:
                direction = "📈"  # Цена повысилась
            elif new_price < old_price:
                direction = "📉"  # Цена понизилась
            else:
                direction = "➡️"  # Цена не изменилась
            
            # ✅ НОВОЕ: Полное и понятное сообщение
            message = (
                f"{direction} 🤖 Автоизменение цены\n\n"
                f"🎮 <b>{game_name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Старая цена: <b>€{old_price:.2f}</b>\n"
                f"💸 Новая цена: <b>€{new_price:.2f}</b>\n"
                f"📊 TOP 1 (рынок): <b>€{market_price:.2f}</b>\n"
                f"📌 Margin: <b>+€{margin:.2f}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
            )
            
            # Отправляем через notifier (с HTML форматированием если поддерживается)
            try:
                # Пытаемся отправить напрямую в Telegram
                await notifier.send_custom_telegram_message(
                    message=message,
                    parse_mode="HTML"
                )
            except:
                # Если нет функции - используем стандартную
                await notifier.send_sale_notification(
                    game_name=game_name,
                    key_value="",
                    price=new_price,
                    prefix=""
                )
            
        except Exception as e:
            print(f"  ⚠️ Ошибка отправки в Telegram: {e}")


async def main():
    """Запуск автоматизации"""
    changer = AutoPriceChanger()
    try:
        await changer.start()
    except KeyboardInterrupt:
        changer.stop()


if __name__ == "__main__":
    asyncio.run(main())
