# telegram_notifier.py - ИСПРАВЛЕННЫЙ
# ✅ ДОБАВЛЕНО:
# • Минимальный оффер конкурента
# • Правильное определение "Продажа" vs "Изменение цены"
# • Ключ и префикс всегда показываются
# • Рыночная цена

import asyncio
from typing import Optional
import httpx

class TelegramNotifier:
    """Отправка уведомлений в Telegram"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            print(f"✅ Telegram уведомления включены (Chat ID: {chat_id})")
        else:
            print("⚠️ Telegram уведомления отключены (токен/chat_id не заданы)")

    async def send_message(self, message: str, parse_mode: str = "HTML"):
        """Отправка сообщения в Telegram"""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": parse_mode
                    }
                )

            if response.status_code == 200:
                print("✅ Telegram уведомление отправлено")
                return True
            else:
                print(f"⚠️ Ошибка Telegram API: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"⚠️ Ошибка отправки в Telegram: {e}")
            return False

    async def send_sale_notification(self, game_name: str, key_value: str, price: float, 
                                     prefix: str = "", min_competitor_price: float = None,
                                     market_price: float = None):
        """
        ✅ ИСПРАВЛЕНО: Отправка уведомления о продаже
        Добавлены параметры:
        • min_competitor_price - минимальная цена конкурента
        • market_price - рыночная цена
        """
        if not self.enabled:
            return False

        # Если ключ пустой - используем плейсхолдер
        key_display = key_value if key_value and key_value.strip() else "(будет выдан)"
        prefix_display = prefix if prefix and prefix.strip() else "steam"

        # Формируем сообщение с дополнительной информацией
        message = f"""
🎉 ПРОДАЖА!

🎮 Игра: {game_name}

💰 Ваша цена: €{price:.2f}"""

        # Добавляем информацию о конкурентах если есть
        if min_competitor_price is not None:
            message += f"""
🏆 Мин. цена конкурента: €{min_competitor_price:.2f}"""
            
            # Показываем преимущество
            advantage = min_competitor_price - price
            if advantage > 0:
                message += f" (↓ на €{advantage:.2f})"
            elif advantage < 0:
                message += f" (↑ на €{abs(advantage):.2f})"

        # Рыночная цена
        if market_price is not None:
            message += f"""
📊 Рыночная цена: €{market_price:.2f}"""

        message += f"""

🔑 Ключ: {key_display}

📦 Префикс: {prefix_display}

🕐 Время: {self._get_current_time()}
"""
        return await self.send_message(message)

    async def send_price_change_notification(self, game_name: str, old_price: float, new_price: float,
                                            market_price: float, reason: str = "автоизменение",
                                            min_competitor_price: float = None, change_reason: str = None):
        """
        ✅ ИСПРАВЛЕНО: Отправка уведомления об изменении цены
        Добавлены:
        • reason - причина изменения (автоизменение, ручное, etc)
        • min_competitor_price - минимальная цена конкурента
        • change_reason - подробная причина
        """
        if not self.enabled:
            return False

        # Определяем направление
        if new_price < old_price:
            direction = "📉 Снижение цены"
        elif new_price > old_price:
            direction = "📈 Повышение цены"
        else:
            direction = "➡️ Без изменений"

        # Размер изменения
        change_amount = abs(new_price - old_price)
        percentage_change = (change_amount / old_price * 100) if old_price > 0 else 0

        message = f"""
{direction}

🎮 Игра: {game_name}

💰 Старая цена: €{old_price:.2f}
💸 Новая цена: €{new_price:.2f}
📊 Рыночная: €{market_price:.2f}

💹 Изменение: €{change_amount:.2f} ({percentage_change:.1f}%)
🔄 Причина: {reason}"""

        # Добавляем информацию о конкурентах если есть
        if min_competitor_price is not None:
            message += f"""

🏆 Мин. цена конкурента: €{min_competitor_price:.2f}"""
            advantage = min_competitor_price - new_price
            if advantage > 0:
                message += f" (вы ниже на €{advantage:.2f})"
            elif advantage < 0:
                message += f" (выше на €{abs(advantage):.2f})"

        if change_reason:
            message += f"""
ℹ️ Подробно: {change_reason}"""

        message += f"""

🕐 Время: {self._get_current_time()}
"""
        return await self.send_message(message)

    async def send_competitor_alert(self, game_name: str, your_price: float, 
                                   competitor_price: float, competitor_count: int = 1):
        """
        ✅ НОВОЕ: Отправка уведомления о конкуренции
        """
        if not self.enabled:
            return False

        difference = your_price - competitor_price
        
        message = f"""
⚠️ КОНКУРЕНТСКОЕ ПРЕДЛОЖЕНИЕ

🎮 Игра: {game_name}

🏆 Цена конкурента: €{competitor_price:.2f}
💰 Ваша цена: €{your_price:.2f}

📊 Разница: €{abs(difference):.2f}"""

        if difference > 0:
            message += f"""
✅ Вы ниже на €{difference:.2f}"""
        else:
            message += f"""
⚠️ Вы выше на €{abs(difference):.2f}"""

        message += f"""

👥 Конкурентов: {competitor_count}

🕐 Время: {self._get_current_time()}
"""
        return await self.send_message(message)

    def _get_current_time(self):
        """Получение текущего времени"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S %d.%m.%Y")

    def update_credentials(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """Обновление учётных данных"""
        if bot_token:
            self.bot_token = bot_token
        if chat_id:
            self.chat_id = chat_id
        
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if self.enabled:
            print(f"✅ Telegram учётные данные обновлены")
        else:
            print("⚠️ Telegram отключен (нет токена/chat_id)")


def create_notifier():
    """Создание notifier с загрузкой из конфига"""
    try:
        from g2a_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        return TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    except ImportError:
        print("⚠️ Не удалось загрузить настройки Telegram из g2a_config")
        return TelegramNotifier()


# Глобальный экземпляр
notifier = create_notifier()
