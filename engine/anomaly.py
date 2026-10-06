"""
Statistical and Heuristic Price Anomaly Detector.
Identifies authentic price drops, system glitches, and verified historical lows.
Filters out artificial 'half of the double' discounts and habituated promotional prices.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from config.settings import settings
from database.db import db
from scrapers.base import ScrapedProduct
from engine.glitch_filter import GlitchFilter

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    is_anomaly: bool
    alert_type: Optional[str] = None  # 'GLITCH_EXTREME', 'FLASH_DROP', 'HISTORICAL_LOW'
    discount_percent: float = 0.0
    z_score: Optional[float] = None
    historical_min: Optional[float] = None
    historical_avg: Optional[float] = None
    sample_count: int = 0
    reason: str = ""
    urgency_score: int = 0  # 0 to 100


class AnomalyDetector:
    def __init__(self, database=None):
        self.db = database or db

    def evaluate_product(self, product: ScrapedProduct, ignore_cooldown: bool = False) -> AnomalyResult:
        """
        Analyzes a scraped product against filtering guardrails, historical price benchmarks,
        and market expertise to ensure alerts are genuine, interesting opportunities.
        """
        # Step 1: Run filter guardrails
        is_valid, invalid_reason = GlitchFilter.is_valid_candidate(product)
        if not is_valid:
            return AnomalyResult(
                is_anomaly=False,
                reason=f"Ignorado pelo filtro: {invalid_reason}",
            )

        # Step 2: Retrieve historical statistics BEFORE recording the new price
        stats = self.db.get_historical_stats(product.marketplace, product.product_id)
        count = stats["count"]
        hist_min = stats["min_price"]
        hist_avg = stats["avg_price"]
        std_dev = stats["std_dev"]

        # Step 3: Persist product and current price in database
        self.db.upsert_product(
            marketplace=product.marketplace,
            product_id=product.product_id,
            title=product.title,
            url=product.url,
            image_url=product.image_url,
            category=product.category,
        )
        self.db.record_price(
            marketplace=product.marketplace,
            product_id=product.product_id,
            price=product.current_price,
            original_price=product.original_price,
            discount_percent=product.discount_percent,
        )

        # Step 4: Strict Anti-Repetition Check
        # Product is only eligible if it has never been alerted, or beats its previous lowest alerted price
        if not ignore_cooldown and not self.db.should_alert(product.marketplace, product.product_id, product.current_price):
            return AnomalyResult(
                is_anomaly=False,
                reason="Preço igual ou superior ao já alertado anteriormente (Anti-Repetição ativado)",
                sample_count=count,
            )

        # Step 5: Calculate declared discount & statistical Z-Score
        declared_discount = product.discount_percent or product.calculate_discount()
        z_score = None
        if count >= 4 and std_dev > 0 and hist_avg is not None:
            z_score = round((product.current_price - hist_avg) / std_dev, 2)

        # =========================================================================
        # MARKET EXPERTISE: DETECTING REAL DISCOUNTS VS. "METADE DO DOBRO"
        # =========================================================================

        # CASE A: Product has verified historical data (count >= 2)
        if count >= 2 and hist_avg and hist_avg > 0:
            real_drop_from_avg = (hist_avg - product.current_price) / hist_avg
            drop_from_avg_pct = round(real_drop_from_avg * 100, 1)

            # 🛑 1. FAKE DISCOUNT FILTER:
            # If current price is within 10% of the historical average, it is just normal everyday pricing,
            # regardless of whether the seller painted a "50% OFF" badge on the store!
            if product.current_price >= (hist_avg * 0.90):
                return AnomalyResult(
                    is_anomaly=False,
                    discount_percent=declared_discount,
                    historical_min=hist_min,
                    historical_avg=hist_avg,
                    sample_count=count,
                    reason=f"Falsa promoção descartada: Preço atual (R$ {product.current_price:.2f}) está na média histórica habitual (R$ {hist_avg:.2f})",
                )

            # 🚨 2. GLITCH EXTREME (Severe real market drop / Possible bug):
            # Price is >= 50% lower than the actual historical average, OR 65%+ discount with negative Z-Score
            if real_drop_from_avg >= 0.50 or (declared_discount >= settings.GLITCH_DISCOUNT_PERCENT and (z_score is not None and z_score <= -2.0)):
                effective_drop = max(declared_discount, drop_from_avg_pct)
                return AnomalyResult(
                    is_anomaly=True,
                    alert_type="GLITCH_EXTREME",
                    discount_percent=effective_drop,
                    z_score=z_score,
                    historical_min=hist_min,
                    historical_avg=hist_avg,
                    sample_count=count,
                    reason=f"Possível erro/glitch: Preço despencou {drop_from_avg_pct}% abaixo da média real de mercado (Média: R$ {hist_avg:.2f})",
                    urgency_score=95,
                )

            # 📉 3. HISTORICAL LOW (Verified lowest price recorded):
            if hist_min and product.current_price < hist_min and real_drop_from_avg >= 0.12:
                return AnomalyResult(
                    is_anomaly=True,
                    alert_type="HISTORICAL_LOW",
                    discount_percent=max(declared_discount, drop_from_avg_pct),
                    z_score=z_score,
                    historical_min=hist_min,
                    historical_avg=hist_avg,
                    sample_count=count,
                    reason=f"Menor preço histórico comprovado! (Novo recorde: R$ {product.current_price:.2f} vs anterior R$ {hist_min:.2f})",
                    urgency_score=85,
                )

            # ⚡ 4. FLASH DROP (Authentic price drop against market average):
            # Must be at least 15% below historical average AND have declared discount >= 35%
            if real_drop_from_avg >= 0.15 and declared_discount >= settings.MIN_DISCOUNT_PERCENT:
                return AnomalyResult(
                    is_anomaly=True,
                    alert_type="FLASH_DROP",
                    discount_percent=declared_discount,
                    z_score=z_score,
                    historical_min=hist_min,
                    historical_avg=hist_avg,
                    sample_count=count,
                    reason=f"Queda real de {drop_from_avg_pct}% abaixo da média observada (R$ {hist_avg:.2f})",
                    urgency_score=75,
                )

        # CASE B: Product is brand new in database (count < 2)
        # Apply higher scrutiny to avoid fake baseline discounts on initial discovery
        else:
            # Require a high declared discount (55%+) and a minimum price threshold
            if declared_discount >= 55.0 and product.current_price >= 35.0:
                return AnomalyResult(
                    is_anomaly=True,
                    alert_type="GLITCH_EXTREME" if declared_discount >= 70.0 else "FLASH_DROP",
                    discount_percent=declared_discount,
                    sample_count=count,
                    reason=f"Super oferta inicial detectada ({declared_discount:.0f}% de desconto de vitrine)",
                    urgency_score=70,
                )

        return AnomalyResult(
            is_anomaly=False,
            discount_percent=declared_discount,
            z_score=z_score,
            historical_min=hist_min,
            historical_avg=hist_avg,
            sample_count=count,
            reason="Variação normal ou desconto não comprovado estatisticamente",
        )
