"""
Statistical and Heuristic Price Anomaly Detector.
Identifies severe price drops, system glitches, and historical lows.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from config.settings import settings
from database.db import db
from scrapers.base import ScrapedProduct
from engine.glitch_filter import GlitchFilter


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
        Analyzes a scraped product against filtering guardrails and historical price data.
        Returns an AnomalyResult indicating whether an alert should be triggered.
        """
        # Step 1: Run filter guardrails
        is_valid, invalid_reason = GlitchFilter.is_valid_candidate(product)
        if not is_valid:
            return AnomalyResult(
                is_anomaly=False,
                reason=f"Ignorado pelo filtro: {invalid_reason}",
            )

        # Step 2: Retrieve historical statistics before saving current reading
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

        # Step 4: Check if already alerted recently (anti-spam cooldown)
        if not ignore_cooldown and not self.db.should_alert(product.marketplace, product.product_id, product.current_price):
            return AnomalyResult(
                is_anomaly=False,
                reason="Alerta já enviado recentemente para este item (em período de cooldown)",
                sample_count=count,
            )


        # Step 5: Calculate discount & z-score
        discount = product.discount_percent or product.calculate_discount()
        z_score = None
        if count >= 4 and std_dev > 0 and hist_avg is not None:
            z_score = round((product.current_price - hist_avg) / std_dev, 2)

        # --- HEURISTIC 1: GLITCH EXTREME (Severe drop / Bug suspicion) ---
        # A) Instant discount is >= configured GLITCH threshold (default 65%+)
        if discount >= settings.GLITCH_DISCOUNT_PERCENT:
            return AnomalyResult(
                is_anomaly=True,
                alert_type="GLITCH_EXTREME",
                discount_percent=discount,
                z_score=z_score,
                historical_min=hist_min,
                historical_avg=hist_avg,
                sample_count=count,
                reason=f"Desconto extremo de {discount:.1f}% detectado (Possível erro de precificação)",
                urgency_score=95,
            )

        # B) Current price dropped >= 45% below the lowest historical price recorded!
        if count >= 3 and hist_min and product.current_price <= (hist_min * 0.55):
            drop_from_min = round(((hist_min - product.current_price) / hist_min) * 100, 1)
            return AnomalyResult(
                is_anomaly=True,
                alert_type="GLITCH_EXTREME",
                discount_percent=max(discount, drop_from_min),
                z_score=z_score,
                historical_min=hist_min,
                historical_avg=hist_avg,
                sample_count=count,
                reason=f"Queda anômala de {drop_from_min}% abaixo do menor preço histórico recente",
                urgency_score=90,
            )

        # C) Statistical anomaly (Z-score <= threshold, e.g. -2.2)
        if z_score is not None and z_score <= settings.Z_SCORE_THRESHOLD:
            return AnomalyResult(
                is_anomaly=True,
                alert_type="GLITCH_EXTREME" if z_score <= -3.0 else "FLASH_DROP",
                discount_percent=discount,
                z_score=z_score,
                historical_min=hist_min,
                historical_avg=hist_avg,
                sample_count=count,
                reason=f"Desvio estatístico significativo (Z-Score: {z_score})",
                urgency_score=85,
            )

        # --- HEURISTIC 2: FLASH DROP (Significant real discount) ---
        if discount >= settings.MIN_DISCOUNT_PERCENT:
            return AnomalyResult(
                is_anomaly=True,
                alert_type="FLASH_DROP",
                discount_percent=discount,
                z_score=z_score,
                historical_min=hist_min,
                historical_avg=hist_avg,
                sample_count=count,
                reason=f"Queda expressiva de {discount:.1f}% em relação ao preço de tabela",
                urgency_score=75,
            )

        # --- HEURISTIC 3: HISTORICAL LOW ---
        if count >= 3 and hist_min and product.current_price < hist_min and discount >= 20.0:
            return AnomalyResult(
                is_anomaly=True,
                alert_type="HISTORICAL_LOW",
                discount_percent=discount,
                z_score=z_score,
                historical_min=hist_min,
                historical_avg=hist_avg,
                sample_count=count,
                reason="Menor preço histórico registrado para este item",
                urgency_score=80,
            )

        return AnomalyResult(
            is_anomaly=False,
            discount_percent=discount,
            z_score=z_score,
            historical_min=hist_min,
            historical_avg=hist_avg,
            sample_count=count,
            reason="Variação normal de preço dentro da média esperada",
        )
