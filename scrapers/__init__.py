from .base import BaseScraper, ScrapedProduct
from .amazon import AmazonScraper
from .mercadolivre import MercadoLivreScraper
from .shopee import ShopeeScraper

__all__ = [
    "BaseScraper",
    "ScrapedProduct",
    "AmazonScraper",
    "MercadoLivreScraper",
    "ShopeeScraper",
]
