"""
Glitch Filter & Guardrails.
Filters out false positives (accessories, placeholder prices, spam keywords).
"""

import re
from typing import Tuple
from config.settings import settings
from scrapers.base import ScrapedProduct


class GlitchFilter:
    # Common accessory keywords that cause false price alerts when searching high-value items
    ACCESSORY_KEYWORDS = [
        "capa", "case", "capinha", "película", "pelicula", "adesivo",
        "suporte para", "cabo usb", "adaptador de tomada", "alça",
        "cordão", "bag de transporte", "estojo para", "protetor de"
    ]

    # Categories where accessories often mask as the main product
    HIGH_VALUE_TARGETS = [
        "iphone", "galaxy s", "macbook", "notebook", "playstation", "ps5",
        "xbox", "placa de video", "rtx", "smart tv", "ipad"
    ]

    @classmethod
    def is_valid_candidate(cls, product: ScrapedProduct) -> Tuple[bool, str]:
        """
        Validates whether a product is a legitimate deal candidate or a false positive.
        Returns: (is_valid, reason_if_invalid)
        """
        # 1. Price checks
        if product.current_price is None or product.current_price <= 0:
            return False, "Preço inválido ou zerado"

        if product.current_price < settings.MIN_PRICE_ALERT:
            return False, f"Preço abaixo do limite mínimo configurado (R$ {settings.MIN_PRICE_ALERT:.2f})"

        # 2. Title length check
        if not product.title or len(product.title.strip()) < 5:
            return False, "Título do produto muito curto ou ausente"

        title_lower = product.title.lower()

        # 3. Accessory false-positive check for high-value tech
        # If the search or category is a high-value item, make sure it's not just a R$ 25 phone case
        is_high_value_target = any(target in (product.category or "").lower() for target in cls.HIGH_VALUE_TARGETS)
        if is_high_value_target:
            has_accessory_word = any(re.search(rf"\b{kw}\b", title_lower) for kw in cls.ACCESSORY_KEYWORDS)
            if has_accessory_word and product.current_price < 200.0:
                return False, "Falso positivo detectado: Acessório em busca de item de alto valor"

        # 4. Out-of-stock check
        if not product.in_stock:
            return False, "Produto sem estoque"

        return True, "Válido"
