# auto_price_changer.py - ПОЛНЫЙ КОД С НОВОЙ ЛОГИКОЙ +0.05 И ЗАЩИТОЙ

import asyncio
import json
import os
from datetime import datetime
from g2a_api_client import G2AApiClient
from telegram_notifier import notifier
import g2a_config
from database import PriceDatabase


class AutoPriceSettings:
    """Управление настройками автоизменения цен"""
    
    def __init__(self, settings_file="auto_price_settings.json"):
        self.settings_file = settings_file
        self.settings = self.load_settings()
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки настроек: {e}")
        
        return {
            "enabled": False,
            "telegram_notifications": False,
            "check_interval": 1800,
            "competitor_offset": 0.05,  # ✅ НОВОЕ: +0.05 от минимума конкурента
            "min_price": 0.1,
            "max_price": 100.0,
            "daily_limit": 20,
            "excluded_products": [],
            "included_products": [],
            "protect_single_seller": True  # ✅ НОВОЕ: защита если ты один
        }
    
    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            print(f"✅ Настройки сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def is_product_allowed(self, product_id):
        """Проверить разрешено ли автоизменение"""
        product_id = str(product_id)
        if not self.settings.get("enabled", False):
            return False
        excluded = self.settings.get("excluded_products", [])
        if product_id in [str(e) for e in excluded]:
            return False
        included = self.settings.get("included_products", [])
        if included:
            return product_id in [str(i) for i in included]
        return True
    
    def toggle_product(self, product_id, enabled=True):
        """Включить/выключить автоизменение для товара"""
        product_id = str(product_id)
        excluded = self.settings.get("excluded_products", [])
        included = self.settings.get("included_products", [])
        
        if enabled:
            self.settings["excluded_products"] = [str(p) for p in excluded if str(p) != product_id]
            if included and product_id not in [str(i) for i in included]:
                self.settings["included_products"].append(product_id)
        else:
            if product_id not in [str(e) for e in excluded]:
                self.settings["excluded_products"].append(product_id)
            self.settings["included_products"] = [str(i) for i in included if str(i) != product_id]
        
        self.save_settings()


class DailyLimitTracker:
    """Отслеживание дневного лимита изменений"""
    
    def __init__(self, limit_file="daily_limit.json"):
        self.limit_file = limit_file
        self.data = self.load_data()
    
    def load_data(self):
        try:
            if os.path.exists(self.limit_file):
                with open(self.limit_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {"date": str(datetime.now().date()), "changes": 0}
    
    def save_data(self):
        try:
            with open(self.limit_file, 'w') as f:
                json.dump(self.data, f)
        except:
            pass
    
    def reset_if_new_day(self):
        """Сбросить счётчик если новый день"""
        today = str(datetime.now().date())
        if self.data.get("date") != today:
            self.data = {"date": today, "changes": 0}
            self.save_data()
    
    def can_change(self, limit):
        """Проверить есть ли ещё изменения в лимите"""
        self.reset_if_new_day()
        remaining = limit - self.data.get("changes", 0)
        return remaining > 0, remaining
    
    def record_change(self):
        """Записать изменение"""
        self.data["changes"] = self.data.get("changes", 0) + 1
        self.save_data()


class AutoPriceChanger:
    """Автоматическое изменение цен с логикой +0.05"""
    
    def __init__(self):
        self.api_client = None
        self.settings = AutoPriceSettings()
        self.limit_tracker = DailyLimitTracker()
        self.running = False
        self.seller_id = None  # ✅ НОВОЕ
    
    async def start(self):
        """Запустить автоизменение"""
        self.running = True
        print("🚀 Запуск автоизменения цен...")
        
        while self.running:
            try:
                await self.check_and_update_prices()
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
            
            check_interval = self.settings.settings.get("check_interval", 1800)
            await asyncio.sleep(check_interval)
    
    def stop(self):
        """Остановить"""
        self.running = False
        print("🛑 Остановка...")
    
    async def check_and_update_prices(self):
        """ГЛАВНАЯ ЛОГИКА"""
        
        try:
            if not self.api_client:
                self.api_client = G2AApiClient()
            
            await self.api_client.get_token()
            offers_result = await self.api_client.get_offers()
            
            if not offers_result.get("success"):
                print(f"❌ Ошибка: {offers_result.get('error')}")
                return
            
            offers = offers_result.get("offers_cache", {})
            if not offers:
                print("⚠️ Нет офферов")
                return
            
            # ✅ Получаем seller_id
            if not self.seller_id and offers:
                first_offer = next(iter(offers.values()))
                self.seller_id = first_offer.get("seller_id")
                if self.seller_id:
                    g2a_config.G2A_SELLER_ID = self.seller_id
                    print(f"✅ Seller ID: {self.seller_id}")
            
            daily_limit = self.settings.settings.get("daily_limit", 20)
            can_change, remaining = self.limit_tracker.can_change(daily_limit)
            
            if not can_change:
                print(f"⚠️ Лимит исчерпан (0/{daily_limit})")
                return
            
            print(f"📊 Проверка {len(offers)} офферов (осталось {remaining})")
            
            for product_id, offer_info in offers.items():
                try:
                    if not self.settings.is_product_allowed(product_id):
                        continue
                    
                    can_change, remaining = self.limit_tracker.can_change(daily_limit)
                    if not can_change:
                        break
                    
                    offer_id = offer_info.get("id")
                    current_price = offer_info.get("price", 0)
                    game_name = offer_info.get("product_name", "Unknown")
                    
                    new_price = await self.calculate_new_price(
                        product_id, current_price, game_name, offer_id
                    )
                    
                    if new_price and new_price != current_price:
                        success = await self.update_offer_price(offer_id, new_price, offer_info)
                        if success:
                            self.limit_tracker.record_change()
<<<<<<< HEAD
                            # ✅ НОВОЕ: Сохраняем статистику в БД
                            try:
                                from database import PriceDatabase
                                db = PriceDatabase()
                                db.save_price_change(
                                    product_id,
                                    current_price,  # old_price
                                    new_price,
                                    new_price,  # market_price
                                    reason="автоизменение"
                                )
                            except Exception as e:
                                print(f"⚠️ Ошибка сохранения статистики: {e}")
=======
                                                        # Save to database
                                                        db = PriceDatabase()
                            db.save_price_change(product_id, current_price, new_price, new_price, reason="автоизменение")
>>>>>>> 1705c1742124f9fb14ad2579509903b23682e81c
                            print(f"✅ {game_name}: €{current_price} → €{new_price}")
                            
                            # Отправляем уведомление
                            await self.send_telegram_notification(
                                game_name, current_price, new_price, "автоизменение"
                            )
                
                except Exception as e:
                    print(f"❌ Ошибка {product_id}: {e}")
        
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    async def calculate_new_price(self, product_id, current_price, game_name, offer_id):
        """
        ✅ НОВАЯ ЛОГИКА РАСЧЁТА ЦЕНЫ
        
        Правила:
        1. Получаем мин цену конкурента
        2. Твоя цена = мин_конкурента + 0.05
        3. Если ты один → защита (не меняем)
        """
        
        try:
            market_info = await self.api_client.check_market_price(product_id)
            
            if not market_info.get("success"):
                return None
            
            market_price = market_info.get("market_price", 0)
            competitors = market_info.get("competitors", [])
            
            min_price = self.settings.settings.get("min_price", 0.1)
            max_price = self.settings.settings.get("max_price", 100.0)
            
            if market_price < min_price or market_price > max_price:
                print(f"⚠️ {game_name}: цена вне диапазона")
                return None
            
            offset = self.settings.settings.get("competitor_offset", 0.05)
            
            if not competitors:
                print(f"🏆 {game_name}: ТЫ ОДИН! Защита активирована")
                if self.settings.settings.get("protect_single_seller", True):
                    return None
            
            # Ищем конкурентов кроме себя
            other_competitors = []
            for comp in competitors:
                if comp.get("seller_id") != self.seller_id:
                    other_competitors.append(comp)
            
            other_competitors.sort(key=lambda x: x.get("price", float('inf')))
            
            if not other_competitors:
                print(f"🏆 {game_name}: Конкурентов нет, защита активирована")
                if self.settings.settings.get("protect_single_seller", True):
                    return None
            
            # Минимальный конкурент
            min_competitor = other_competitors[0]
            min_competitor_price = min_competitor.get("price", 0)
            
            # ✅ НОВАЯ ЛОГИКА: твоя_цена = мин_конкурента + 0.05
            new_price = round(min_competitor_price + offset, 2)
            
            if new_price < min_price:
                new_price = min_price
            elif new_price > max_price:
                new_price = max_price
            
            print(f"📊 {game_name}: мин_конкурент={min_competitor_price}€ → твоя={new_price}€ (+{offset}€)")
            
            return new_price
        
        except Exception as e:
            print(f"❌ Ошибка расчёта: {e}")
            return None
    
    async def update_offer_price(self, offer_id, new_price, offer_info):
        """Обновить цену оффера"""

        try:
            update_data = {
                "offerType": offer_info.get("offer_type", "dropshipping"),
                "variant": {
                    "price": {
                        "retail": str(new_price),
                        "business": str(new_price)
                    },
                    "active": True
                }
            }
            
            if "regions" in offer_info:
                update_data["variant"]["regions"] = offer_info["regions"]
            if "regionRestrictions" in offer_info:
                update_data["variant"]["regionRestrictions"] = offer_info["regionRestrictions"]
            
            result = await self.api_client.update_offer_partial(offer_id, update_data)
            return result.get("success", False)

        except Exception as e:
            print(f"❌ Ошибка обновления: {e}")
            return False

    async def send_telegram_notification(self, game_name, old_price, new_price, reason):
        """Отправить уведомление в Telegram"""
        try:
            if not self.settings.settings.get("telegram_notifications", False):
                return
            
            change = new_price - old_price
            direction = "📉" if change < 0 else "📈"
            
            message = f"""
🔄 АВТОИЗМЕНЕНИЕ ЦЕНЫ

🎮 Игра: {game_name}
{direction} Старая: €{old_price:.2f} → Новая: €{new_price:.2f}
💱 Изменение: €{abs(change):.2f}
🔖 Причина: {reason}
🕐 Время: {datetime.now().strftime('%H:%M:%S')}
            """
            
            await notifier.send_message(message)
        
        except Exception as e:
            print(f"⚠️ Ошибка отправки Telegram: {e}")


def save_price_change_stats(product_id, old_price, new_price, market_price, reason):
    """Сохранить статистику изменения"""
    try:
        stats_file = "price_changes_stats.json"
        
        if os.path.exists(stats_file):
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = []
        
        stats.append({
            "timestamp": datetime.now().isoformat(),
            "product_id": product_id,
            "old_price": old_price,
            "new_price": new_price,
            "market_price": market_price,
            "change": round(new_price - old_price, 2),
            "reason": reason
        })
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
    
    except Exception as e:
        print(f"❌ Ошибка сохранения статистики: {e}")
