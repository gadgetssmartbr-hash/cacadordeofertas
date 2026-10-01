"""
Test script for Telegram Bot credentials.
Sends a test alert to verify that the bot token and chat ID are working.
"""

import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from config.settings import settings
from notifier.telegram import notifier

from scrapers.base import ScrapedProduct
from engine.anomaly import AnomalyResult


def main():
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "seu_bot_token_aqui":
        print("\n❌ ERRO: 'TELEGRAM_BOT_TOKEN' não está configurado no arquivo .env!")
        print("Abra o arquivo .env e insira o token fornecido pelo @BotFather.\n")
        sys.exit(1)

    if not settings.TELEGRAM_CHAT_ID or settings.TELEGRAM_CHAT_ID == "seu_chat_id_ou_canal_aqui":
        print("\n❌ ERRO: 'TELEGRAM_CHAT_ID' não está configurado no arquivo .env!")
        print("Abra o arquivo .env e insira seu ID numérico ou canal.\n")
        sys.exit(1)

    print(f"📡 Testando envio para o Chat ID: {settings.TELEGRAM_CHAT_ID}...")

    # Dummy product to test alert layout
    dummy_product = ScrapedProduct(
        marketplace="amazon",
        product_id="B0TEST123",
        title="Fone de Ouvido Sem Fio Bluetooth Noise Cancelling (TESTE)",
        current_price=119.90,
        original_price=399.00,
        discount_percent=70.0,
        url="https://www.amazon.com.br",
        image_url="https://m.media-amazon.com/images/I/51IQDm9ayjL._AC_UL320_.jpg",
        category="Tech",
    )

    dummy_anomaly = AnomalyResult(
        is_anomaly=True,
        alert_type="GLITCH_EXTREME",
        discount_percent=70.0,
        reason="Teste de integração do Telegram",
        urgency_score=99,
    )

    dummy_affiliate_url = f"https://www.amazon.com.br/?tag={settings.AMAZON_TAG}"

    success = notifier.send_alert(dummy_product, dummy_anomaly, dummy_affiliate_url)

    if success:
        print("\n✅ SUCESSO! A mensagem de teste foi enviada para o seu Telegram.")
        print("Confira o seu aplicativo do Telegram agora!\n")
    else:
        print("\n❌ Falha ao enviar para o Telegram. Verifique se o bot foi iniciado (/start) ou se o token está correto.\n")


if __name__ == "__main__":
    main()
