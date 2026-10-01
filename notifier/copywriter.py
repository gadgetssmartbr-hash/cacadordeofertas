"""
Copywriter for High-Converting Telegram Alerts.
Generates compelling, urgency-focused copy with FOMO triggers (both rule-based templates and Gemini AI).
"""

import logging
import random
from typing import Optional
from config.settings import settings
from scrapers.base import ScrapedProduct
from engine.anomaly import AnomalyResult

logger = logging.getLogger(__name__)


class AlertCopywriter:
    def __init__(self, gemini_api_key: Optional[str] = None):
        self.api_key = gemini_api_key or settings.GEMINI_API_KEY
        self.ai_client = None
        if self.api_key:
            try:
                from google import genai
                self.ai_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def generate_alert_text(
        self,
        product: ScrapedProduct,
        anomaly: AnomalyResult,
        affiliate_url: str,
    ) -> str:
        """
        Creates an attention-grabbing Telegram alert formatted in HTML.
        Uses Gemini AI if configured, otherwise falls back to battle-tested high-converting templates.
        """
        # Try AI copy if Gemini is available and it's a severe glitch
        if self.ai_client and anomaly.alert_type == "GLITCH_EXTREME":
            ai_copy = self._generate_ai_copy(product, anomaly, affiliate_url)
            if ai_copy:
                return ai_copy

        # High-converting template fallback
        return self._generate_template_copy(product, anomaly, affiliate_url)

    def _generate_template_copy(
        self,
        product: ScrapedProduct,
        anomaly: AnomalyResult,
        affiliate_url: str,
    ) -> str:
        store_display = {
            "amazon": "Amazon Brasil 🛒",
            "mercadolivre": "Mercado Livre 💛",
            "shopee": "Shopee 🧡",
        }.get(product.marketplace.lower(), product.marketplace.capitalize())

        # Formatted Prices
        curr_price_str = f"R$ {product.current_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        orig_price_str = ""
        if product.original_price and product.original_price > product.current_price:
            orig_price_str = f"R$ {product.original_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Hooks by Alert Type
        glitch_hooks = [
            "🚨 <b>POSSÍVEL ERRO DE PREÇO / BUG?</b> 🚨\n<i>Corre antes que o estagiário perceba e conserte!</i>",
            "🔥 <b>PREÇO ANÔMALO DETECTADO!</b> 🔥\n<i>Valor absurdamente fora da curva. Chance real de bug de sistema!</i>",
            "⚡ <b>QUEBROU O SISTEMA?!</b> ⚡\n<i>Preço despencou sem aviso prévio. Corre para garantir!</i>",
        ]

        drop_hooks = [
            "⚡ <b>MEGA QUEDA DE PREÇO RELÂMPAGO</b> ⚡\n<i>Desconto expressivo detectado pelo nosso agente!</i>",
            "💥 <b>SUPER OFERTA DETECTADA</b> 💥\n<i>Caiu muito! Preço bem abaixo do mercado.</i>",
        ]

        low_hooks = [
            "📉 <b>MENOR PREÇO HISTÓRICO REGISTRADO</b> 📉\n<i>Nosso algoritmo nunca viu esse item tão barato!</i>",
        ]

        if anomaly.alert_type == "GLITCH_EXTREME":
            hook = random.choice(glitch_hooks)
            urgency_tag = "⚠️ <b>ATENÇÃO:</b> Erros de preço costumam durar poucos minutos!"
        elif anomaly.alert_type == "HISTORICAL_LOW":
            hook = random.choice(low_hooks)
            urgency_tag = "💡 <b>DICA:</b> Preço mínimo das últimas semanas."
        else:
            hook = random.choice(drop_hooks)
            urgency_tag = "⏳ <b>AVISO:</b> Oferta sujeita a término de estoque."

        # Pricing Block
        discount_text = f" (-{anomaly.discount_percent:.0f}%)" if anomaly.discount_percent > 0 else ""
        if orig_price_str:
            price_block = f"❌ De: <s>{orig_price_str}</s>\n🔥 <b>Por apenas: {curr_price_str}</b>{discount_text}"
        else:
            price_block = f"🔥 <b>Preço Atual: {curr_price_str}</b>{discount_text}"

        # Clean Product Title (up to 120 chars)
        safe_title = product.title[:110].strip()
        if len(product.title) > 110:
            safe_title += "..."

        history_block = ""
        if settings.MICRO_SITE_URL and not any(h in settings.MICRO_SITE_URL.lower() for h in ("localhost", "127.0.0.1")):
            history_url = f"{settings.MICRO_SITE_URL}/p/{product.marketplace}/{product.product_id}"
            history_block = f"📊 <b>Histórico:</b> <a href=\"{history_url}\">Ver Gráfico de Preço</a>\n"

        # Compose HTML message
        message = (
            f"{hook}\n\n"
            f"📦 <b>{safe_title}</b>\n\n"
            f"{price_block}\n"
            f"🏬 Loja: {store_display}\n"
            f"{history_block}\n"
            f"{urgency_tag}\n\n"
            f"👉 <b>COMPRE AQUI:</b>\n{affiliate_url}"
        )
        return message



    def _generate_ai_copy(
        self,
        product: ScrapedProduct,
        anomaly: AnomalyResult,
        affiliate_url: str,
    ) -> Optional[str]:
        try:
            prompt = (
                f"Você é um copywriter especialista em grupos de ofertas no Telegram com foco em 'erros de preço' e 'bugs'. "
                f"Crie uma mensagem curta, super persuasiva e urgente em HTML (usando <b>, <i>, <s>) para o seguinte produto:\n"
                f"- Produto: {product.title}\n"
                f"- Preço Original: R$ {product.original_price}\n"
                f"- Preço com Erro/Desconto: R$ {product.current_price}\n"
                f"- Desconto: {anomaly.discount_percent:.1f}%\n"
                f"- Loja: {product.marketplace}\n"
                f"- Link: {affiliate_url}\n"
                f"Regras:\n"
                f"1. Comece com '🚨 POSSÍVEL ERRO DE PREÇO / BUG?'\n"
                f"2. Use gatilhos de urgência extrema (ex: 'o estagiário vai ser demitido', 'corre antes de tirarem do ar').\n"
                f"3. Mostre o De/Por claramente.\n"
                f"4. Inclua o link no final.\n"
                f"5. Responda apenas com o texto final da mensagem."
            )
            response = self.ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            logger.debug(f"AI copy generation skipped: {e}")
            return None


copywriter = AlertCopywriter()
