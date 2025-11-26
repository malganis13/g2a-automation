import asyncio
from typing import Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Улучшенный класс для отправки уведомлений в Telegram"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

        if self.enabled:
            logger.info(f"✅ Telegram инициализирован | Chat ID: {chat_id}")
        else:
            logger.warning("❌ Telegram отключен (не указаны токен или chat_id)")

    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Отправить сообщение в Telegram"""
        if not self.enabled:
            logger.warning("Telegram отключен, сообщение не отправлено")
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
                logger.info("✅ Telegram: Сообщение отправлено")
                return True
            else:
                logger.error(f"❌ Telegram API ошибка {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram: {e}")
            return False

    async def send_sale_notification(self, game_name: str, key_value: str, price: float, prefix: str = "sks") -> bool:
        """Отправить уведомление о продаже"""
        if not self.enabled:
            return False

        try:
            message = f"""
<b>🎮 ПРОДАЖА</b>

<b>Игра:</b> {game_name}
<b>Цена:</b> €{price:.2f}
<b>Ключ:</b> <code>{key_value}</code>
<b>Префикс:</b> {prefix}

⏰ {self.get_current_time()}
"""
            return await self.send_message(message)
        except Exception as e:
            logger.error(f"❌ Ошибка в send_sale_notification: {e}")
            return False

    async def send_price_change_notification(self, game_name: str, old_price: float, new_price: float,
                                             market_price: float) -> bool:
        """Отправить уведомление об изменении цены"""
        if not self.enabled:
            return False

        try:
            direction = "📈 ПОВЫШЕНИЕ" if new_price > old_price else "📉 СНИЖЕНИЕ"

            message = f"""
<b>{direction}</b>

<b>Игра:</b> {game_name}
<b>Было:</b> €{old_price:.2f}
<b>Стало:</b> €{new_price:.2f}
<b>Рынок:</b> €{market_price:.2f}
<b>Изменение:</b> €{abs(new_price - old_price):.2f}

⏰ {self.get_current_time()}
"""
            return await self.send_message(message)
        except Exception as e:
            logger.error(f"❌ Ошибка в send_price_change_notification: {e}")
            return False

    @staticmethod
    def get_current_time() -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S %d.%m.%Y")

    def update_credentials(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """Обновить учетные данные Telegram - КЛЮЧЕВАЯ ФУНКЦИЯ"""
        if bot_token:
            self.bot_token = bot_token
        if chat_id:
            self.chat_id = chat_id

        self.enabled = bool(self.bot_token and self.chat_id)

        if self.enabled:
            logger.info(f"✅ Telegram обновлен | Chat ID: {self.chat_id}")
        else:
            logger.warning("❌ Telegram отключен после обновления")


# Глобальный экземпляр
def create_notifier() -> TelegramNotifier:
    """Создать экземпляр notifier из конфига"""
    try:
        from g2a_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        return TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    except ImportError:
        logger.error("Ошибка импорта g2a_config")
        return TelegramNotifier()


# Создаем глобальный notifier (может быть обновлен из GUI)
notifier = create_notifier()
