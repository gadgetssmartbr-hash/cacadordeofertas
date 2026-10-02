"""
Telegram Notifier Integration.
Dispatches formatted alert messages with photos and inline affiliate buttons to Telegram channels or groups.
"""

import logging
from datetime import datetime
from typing import Optional
from curl_cffi import requests
from rich.console import Console
from rich.panel import Panel

from config.settings import settings
from scrapers.base import ScrapedProduct
from engine.anomaly import AnomalyResult
from notifier.copywriter import copywriter

logger = logging.getLogger(__name__)
console = Console(force_terminal=True)


class TelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and self.bot_token != "seu_bot_token_aqui")

    @staticmethod
    def is_within_alert_hours() -> bool:
        """Checks if current time is within configured allowed alert hours (e.g. 7h to 21h)."""
        current_hour = datetime.now().hour
        if settings.ALERT_START_HOUR <= settings.ALERT_END_HOUR:
            return settings.ALERT_START_HOUR <= current_hour <= settings.ALERT_END_HOUR
        return current_hour >= settings.ALERT_START_HOUR or current_hour <= settings.ALERT_END_HOUR

    def send_alert(
        self,
        product: ScrapedProduct,
        anomaly: AnomalyResult,
        affiliate_url: str,
        force: bool = False,
    ) -> bool:
        """
        Sends the alert to Telegram. If credentials are not configured, prints a rich preview to console.
        Suppresses notifications outside allowed hours (e.g. 7h to 21h) unless force is True.
        """
        message_text = copywriter.generate_alert_text(product, anomaly, affiliate_url)

        if not self.is_configured:
            self._print_local_preview(product, anomaly, message_text, affiliate_url)
            return True

        # Check allowed alert hours
        if not force and not self.is_within_alert_hours():
            logger.info(
                f"Horário de silêncio ({datetime.now().strftime('%H:%M')}). "
                f"Alerta suprimido (período permitido: {settings.ALERT_START_HOUR}h às {settings.ALERT_END_HOUR}h)."
            )
            return False


        # Build inline keyboard with direct buy button
        buttons = [
            [{"text": "🛒 COMPRAR COM DESCONTO AGORA", "url": affiliate_url}]
        ]

        # Telegram rejects 'localhost' and '127.0.0.1' in inline button URLs
        if settings.MICRO_SITE_URL and not any(h in settings.MICRO_SITE_URL.lower() for h in ("localhost", "127.0.0.1")):
            history_url = f"{settings.MICRO_SITE_URL.rstrip('/')}/p/{product.marketplace}/{product.product_id}/"
            buttons.append([{"text": "📊 VER GRÁFICO DE PREÇOS", "url": history_url}])

        reply_markup = {"inline_keyboard": buttons}



        # Try sending with Photo first if available
        if product.image_url:
            success = self._send_photo(product.image_url, message_text, reply_markup)
            if success:
                return True
            logger.info("Photo send failed or was rejected; falling back to text message...")

        # Text fallback
        return self._send_message(message_text, reply_markup)

    def _send_photo(self, photo_url: str, caption: str, reply_markup: dict) -> bool:
        url = f"{self.api_base}/sendPhoto"
        # Telegram captions max 1024 chars
        safe_caption = caption[:1020]
        payload = {
            "chat_id": self.chat_id,
            "photo": photo_url,
            "caption": safe_caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
        }
        try:
            r = requests.post(url, json=payload, timeout=12)
            if r.status_code == 200:
                logger.info(f"Telegram photo alert sent successfully to {self.chat_id}")
                return True
            logger.warning(f"Telegram sendPhoto error ({r.status_code}): {r.text}")
            return False
        except Exception as e:
            logger.error(f"Telegram sendPhoto exception: {e}")
            return False

    def _send_message(self, text: str, reply_markup: dict) -> bool:
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": reply_markup,
        }
        try:
            r = requests.post(url, json=payload, timeout=12)
            if r.status_code == 200:
                logger.info(f"Telegram message alert sent successfully to {self.chat_id}")
                return True
            logger.warning(f"Telegram sendMessage error ({r.status_code}): {r.text}")
            return False
        except Exception as e:
            logger.error(f"Telegram sendMessage exception: {e}")
            return False

    def _print_local_preview(
        self,
        product: ScrapedProduct,
        anomaly: AnomalyResult,
        message_text: str,
        affiliate_url: str,
    ) -> None:
        title_tag = f"[{anomaly.alert_type}] {product.marketplace.upper()}"
        preview_body = (
            f"[bold cyan]URL Monetizada:[/bold cyan] {affiliate_url}\n"
            f"[bold cyan]Imagem:[/bold cyan] {product.image_url or 'N/A'}\n"
            f"[bold cyan]Gatilho:[/bold cyan] {anomaly.reason}\n\n"
            f"[bold green]=== CONTEÚDO TELEGRAM (HTML) ===[/bold green]\n"
            f"{message_text}"
        )
        console.print(Panel(
            preview_body,
            title=f"🚨 [DRY-RUN PREVIEW] {title_tag}",
            border_style="yellow",
        ))


notifier = TelegramNotifier()
