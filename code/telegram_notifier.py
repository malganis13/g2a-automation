# telegram_notifier.py
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
            print("⚠️  Telegram уведомления отключены (токен/chat_id не заданы)")

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
                    print(f"⚠️  Ошибка Telegram API: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            print(f"⚠️  Ошибка отправки в Telegram: {e}")
            return False

    async def send_sale_notification(self, game_name: str, key_value: str, price: float, prefix: str = ""):
        """Отправка уведомления о продаже"""
        if not self.enabled:
            return False

        message = f"""
🎉 <b>ПРОДАЖА!</b>

🎮 <b>Игра:</b> {game_name}
💰 <b>Цена:</b> €{price:.2f}
🔑 <b>Ключ:</b> <code>{key_value}</code>
📦 <b>Префикс:</b> {prefix}
🕐 <b>Время:</b> {self._get_current_time()}
"""

        return await self.send_message(message)

    async def send_price_change_notification(self, game_name: str, old_price: float, new_price: float,
                                             market_price: float):
        """Отправка уведомления об изменении цены"""
        if not self.enabled:
            return False

        direction = "📉" if new_price < old_price else "📈"

        message = f"""
{direction} <b>Автоизменение цены</b>

🎮 <b>Игра:</b> {game_name}
💰 <b>Старая цена:</b> €{old_price:.2f}
💸 <b>Новая цена:</b> €{new_price:.2f}
📊 <b>Рыночная:</b> €{market_price:.2f}
🕐 <b>Время:</b> {self._get_current_time()}
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
            print("⚠️  Telegram отключен (нет токена/chat_id)")


# ✅ ИСПРАВЛЕНИЕ: Создаём глобальный объект с дефолтными значениями
def create_notifier():
    """Создание notifier с загрузкой из конфига"""
    try:
        from g2a_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        return TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    except ImportError:
        print("⚠️  Не удалось загрузить настройки Telegram из g2a_config")
        return TelegramNotifier()


# Глобальный экземпляр
notifier = create_notifier()