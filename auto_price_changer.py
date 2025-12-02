# auto_price_changer.py - ФИНАЛЬНАЯ ВЕРСИЯ С ЛОГИКОЙ -0.01€ И ИНДИВИДУАЛЬНЫМИ ПОРОГАМИ

import asyncio
import json
import os
from datetime import datetime
from g2a_api_client import G2AApiClient
from telegram_notifier import notifier
from database import PriceDatabase
import g2a_config


class AutoPriceSettings:
    """Управление настройками автоизменения цен"""

    def __init__(self, settings_file="auto_price_settings.json"):
        self.settings_file = settings_file
        self.settings = self.load_settings()
        self.db = PriceDatabase()

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
            "undercut_amount": 0.01,  # ✅ -0.01€ от конкурента
            "min_price": 0.1,  # Глобальный порог
            "max_price": 100.0,
            "daily_limit": 20,
            "excluded_products": [],  # Чёрный список
            "included_products": []   # Белый список
        }

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            print(f"✅ Настройки сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")

    def is_product_allowed(self, product_id):
        """
        ✅ ОБНОВЛЕНО: Проверить разрешено ли автоизменение
        
        Приоритет:
        1. Глобально выключено → запрет для всех
        2. Индивидуальные настройки в БД (приоритет!)
        3. Исключения (чёрный список)
        4. Включения (белый список)
        """
        product_id = str(product_id)
        
        # 1️⃣ Глобально выключено
        if not self.settings.get("enabled", False):
            return False
        
        # 2️⃣ Проверяем индивидуальные настройки в БД
        product_settings = self.db.get_product_settings(product_id)
        
        if product_settings:
            # Есть запись → используем её настройку
            return bool(product_settings.get("auto_enabled", 0))
        
        # 3️⃣ Чёрный список
        excluded = self.settings.get("excluded_products", [])
        if product_id in [str(e) for e in excluded]:
            return False
        
        # 4️⃣ Белый список
        included = self.settings.get("included_products", [])
        if included:
            return product_id in [str(i) for i in included]
        
        # 5️⃣ По умолчанию → ВКЛ (если глобально включено)
        return True

    def toggle_product(self, product_id, enabled=True):
        """
        ✅ ОБНОВЛЕНО: Включить/выключить автоизменение для товара
        
        Теперь использует БД вместо JSON!
        """
        product_id = str(product_id)
        
        # Сохраняем в БД
        self.db.set_product_settings(
            product_id=product_id,
            auto_enabled=1 if enabled else 0
        )
        
        print(f"✅ Точечное авто {'ВКЛ' if enabled else 'ВЫКЛ'} для {product_id}")


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
    """
    ✅ ФИНАЛЬНАЯ ВЕРСИЯ: Автоматическое изменение цен
    
    Логика:
    1. Твоя_цена = мин_конкурент - 0.01€
    2. Если цена < порога → СТОП, не меняем
    3. Индивидуальный порог > глобальный
    """

    def __init__(self):
        self.api_client = None
        self.settings = AutoPriceSettings()
        self.limit_tracker = DailyLimitTracker()
        self.db = PriceDatabase()
        self.running = False
        self.seller_id = None

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
        """
        ✅ ГЛАВНАЯ ЛОГИКА АВТОИЗМЕНЕНИЯ
        """
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
                    # Проверяем разрешено ли автоизменение
                    if not self.settings.is_product_allowed(product_id):
                        continue

                    can_change, remaining = self.limit_tracker.can_change(daily_limit)
                    if not can_change:
                        break

                    offer_id = offer_info.get("id")
                    current_price = offer_info.get("price", 0)
                    game_name = offer_info.get("product_name", "Unknown")

                    # ✅ Рассчитываем новую цену
                    new_price = await self.calculate_new_price(
                        product_id, current_price, game_name, offer_id
                    )

                    if new_price and new_price != current_price:
                        success = await self.update_offer_price(offer_id, new_price, offer_info)
                        
                        if success:
                            self.limit_tracker.record_change()
                            
                            # ✅ Сохраняем статистику в БД
                            self.db.save_price_change(
                                product_id=product_id,
                                old_price=current_price,
                                new_price=new_price,
                                market_price=new_price,
                                reason="автоизменение",
                                game_name=game_name
                            )
                            
                            print(f"✅ {game_name}: €{current_price:.2f} → €{new_price:.2f}")
                            
                            # Telegram уведомление
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
        ✅ ФИНАЛЬНАЯ ЛОГИКА РАСЧЁТА ЦЕНЫ
        
        Правила:
        1. Получаем мин. конкурента из G2A API
        2. Твоя_цена = мин_конкурент - 0.01€
        3. Если цена < порога → СТОП, не меняем!
        4. Индивидуальный порог > глобальный
        """
        try:
            # 1️⃣ Получаем мин. конкурента из API
            market_info = await self.api_client.check_market_price(product_id)
            
            if not market_info.get("success"):
                return None
            
            min_competitor_price = market_info.get("market_price", 0)
            competitors_count = market_info.get("competitor_count", 0)
            
            if not min_competitor_price or min_competitor_price == 0:
                print(f"⚠️ {game_name}: нет конкурентов")
                return None
            
            # 2️⃣ Получаем индивидуальные настройки
            product_settings = self.db.get_product_settings(product_id)
            
            # 3️⃣ Определяем порог (индивидуальный или глобальный)
            if product_settings and product_settings.get("min_floor_price"):
                min_floor = product_settings["min_floor_price"]
                print(f"🛡️ Индивидуальный порог: €{min_floor:.2f}")
            else:
                min_floor = self.settings.settings.get("min_price", 0.1)
                print(f"🌐 Глобальный порог: €{min_floor:.2f}")
            
            # 4️⃣ Определяем снижение
            if product_settings and product_settings.get("undercut_amount"):
                undercut = product_settings["undercut_amount"]
            else:
                undercut = self.settings.settings.get("undercut_amount", 0.01)
            
            # 5️⃣ Проверяем макс. порог
            max_price = self.settings.settings.get("max_price", 100.0)
            
            if min_competitor_price < min_floor or min_competitor_price > max_price:
                print(f"⚠️ {game_name}: конкурент вне диапазона")
                return None
            
            # 6️⃣ Рассчитываем новую цену
            # ✅ ФИНАЛЬНАЯ ЛОГИКА: твоя_цена = мин_конкурент - 0.01€
            new_price = round(min_competitor_price - undercut, 2)
            
            # 7️⃣ ✅ ПРОВЕРКА ПОРОГА!
            if new_price < min_floor:
                print(f"🛑 СТОП! {game_name}:")
                print(f"   Новая цена €{new_price:.2f} < порога €{min_floor:.2f}")
                print(f"   🛡️ Оставляем текущую: €{current_price:.2f}")
                return None  # НЕ МЕНЯЕМ!
            
            # 8️⃣ Проверяем максимум
            if new_price > max_price:
                new_price = max_price
            
            # 9️⃣ Информация
            print(f"📊 {game_name}:")
            print(f"   Мин. конкурент: €{min_competitor_price:.2f}")
            print(f"   Твоя цена: €{new_price:.2f} (-€{undercut:.2f})")
            print(f"   🛡️ Порог: €{min_floor:.2f}")
            
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