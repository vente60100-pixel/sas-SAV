"""
OKTAGON SAV v4.0 — Worker Notification Telegram
Unifie telegram_admin + telegram_usine.
"""
import httpx
from logger import logger


class TelegramNotifier:
    """Envoie des notifications Telegram."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, message: str) -> bool:
        """Envoie un message Telegram (HTML)."""
        if not self.bot_token or not self.chat_id:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram erreur: {e}", extra={"action": "telegram_error"})
            return False
