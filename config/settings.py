"""
Configuration module for PriceGlitch & Drop Agent.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")


class Settings:
    # App
    PROJECT_NAME: str = "PriceGlitch & Drop Agent"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Database
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / os.getenv("DB_NAME", "prices.db")

    # Micro-Web Site URL (for price timeline charts)
    MICRO_SITE_URL: str = os.getenv("MICRO_SITE_URL", "http://localhost:8000")

    # Telegram Alerting

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Affiliate Tags & Keys
    AMAZON_TAG: str = os.getenv("AMAZON_TAG", "gadgetssmartb-20")
    MERCADOLIVRE_AFFILIATE_TAG: str = os.getenv("MERCADOLIVRE_AFFILIATE_TAG", "")
    ML_WISHLIST_ID: str = os.getenv("ML_WISHLIST_ID", "d3d29148-7134-40ad-80d6-ae644d99754c")
    ML_WISHLIST_URL: str = os.getenv("ML_WISHLIST_URL", "")
    SHOPEE_AFFILIATE_ID: str = os.getenv("SHOPEE_AFFILIATE_ID", "")
    LOMADEE_SOURCE_ID: str = os.getenv("LOMADEE_SOURCE_ID", "")


    # Google Gemini AI (Optional for automated high-converting copy)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Thresholds & Engine Rules
    MIN_PRICE_ALERT: float = float(os.getenv("MIN_PRICE_ALERT", "20.0"))  # Ignore items < R$ 20 (cables, stickers)
    MIN_DISCOUNT_PERCENT: float = float(os.getenv("MIN_DISCOUNT_PERCENT", "40.0"))  # 40%+ drop triggers alert
    GLITCH_DISCOUNT_PERCENT: float = float(os.getenv("GLITCH_DISCOUNT_PERCENT", "65.0"))  # 65%+ tagged as BUG / ERRO
    Z_SCORE_THRESHOLD: float = float(os.getenv("Z_SCORE_THRESHOLD", "-2.2"))  # Statistical anomaly
    ALERT_COOLDOWN_HOURS: int = int(os.getenv("ALERT_COOLDOWN_HOURS", "12"))  # Don't repeat product in 12h

    # Horário permitido para disparos no Telegram (ex: 7h às 21h)
    ALERT_START_HOUR: int = int(os.getenv("ALERT_START_HOUR", "7"))
    ALERT_END_HOUR: int = int(os.getenv("ALERT_END_HOUR", "21"))

    # Scraper & Poller

    SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
    REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))

    # Search categories/keywords to watch for drops (Foco em Brinquedos / Dia das Crianças)
    SEARCH_QUERIES: list[str] = [
        "lego",
        "hot wheels pista",
        "boneca barbie",
        "patinete infantil",
        "nintendo switch",
        "playstation 5",
        "jogos tabuleiro",
        "bicicleta infantil",
        "nerf",
        "massinha play doh",
        "brinquedos educativos",
        "boneco marvel homem aranha",
        "carrinho controle remoto",
        "tablet infantil",
        "pula pula cama elastica",
    ]


settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
