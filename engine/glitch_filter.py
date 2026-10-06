"""
Glitch Filter & Guardrails.
Filters out false positives (accessories, artificial price inflations, placeholder prices, spam keywords).
"""

import re
from typing import Tuple
from config.settings import settings
from scrapers.base import ScrapedProduct


class GlitchFilter:
    # Common accessory keywords that cause false price alerts when searching high-value items
    ACCESSORY_KEYWORDS = [
        "capa", "case", "capinha", "película", "pelicula", "adesivo",
        "suporte para", "suporte de", "cabo usb", "cabo tipo c", "adaptador",
        "alça", "cordão", "bag de transporte", "estojo para", "protetor de",
        "skin para", "parafuso", "plugue", "flanela", "pilha"
    ]

    # Categories/Keywords where accessories often mask as the main product
    HIGH_VALUE_TARGETS = [
        "iphone", "galaxy s", "macbook", "notebook", "playstation", "ps5",
        "xbox", "placa de video", "rtx", "smart tv", "ipad", "kindle", "drone", "camera"
    ]

    # Spam/low-value item patterns that simulate massive fake discounts
    JUNK_KEYWORDS = [
        "amostra grátis", "amostra gratis", "manual digital", "pdf", "curso",
        "pack de fotos", "ebook", "chaveiro", "botton"
    ]

    @classmethod
    def is_valid_candidate(cls, product: ScrapedProduct) -> Tuple[bool, str]:
        """
        Validates whether a product is a legitimate deal candidate or a false positive.
        Returns: (is_valid, reason_if_invalid)
        """
        # 1. Price sanity checks
        if product.current_price is None or product.current_price <= 0:
            return False, "Preço inválido ou zerado"

        if product.current_price < settings.MIN_PRICE_ALERT:
            return False, f"Preço abaixo do limite mínimo configurado (R$ {settings.MIN_PRICE_ALERT:.2f})"

        # 2. Title length check
        if not product.title or len(product.title.strip()) < 6:
            return False, "Título do produto muito curto ou ausente"

        title_lower = product.title.lower()

        # 3. Junk & spam check
        for junk in cls.JUNK_KEYWORDS:
            if junk in title_lower:
                return False, f"Item descartado por conter termo de baixo valor: '{junk}'"

        # 4. Accessory false-positive check for high-value tech
        # If the search or category is a high-value item, make sure it's not just a R$ 25 phone case or mount
        is_high_value_target = any(target in title_lower or target in (product.category or "").lower() for target in cls.HIGH_VALUE_TARGETS)
        if is_high_value_target:
            has_accessory_word = any(re.search(rf"\b{re.escape(kw)}\b", title_lower) for kw in cls.ACCESSORY_KEYWORDS)
            if has_accessory_word and product.current_price < 250.0:
                return False, "Falso positivo descartado: Acessório genérico em busca de item nobre"

        # 5. Detection of ridiculously inflated baseline prices (Fake "De/Por")
        # E.g. a R$ 40 item listing "De R$ 400" (10x higher) without verified historical justification
        if product.original_price and product.current_price < 150.0:
            if product.original_price > (product.current_price * 4.0):
                return False, f"Preço de tabela artificialmente inflado pelo vendedor (De R$ {product.original_price:.2f} por R$ {product.current_price:.2f})"

        # 6. Out-of-stock check
        if not product.in_stock:
            return False, "Produto sem estoque"

        return True, "Válido"
