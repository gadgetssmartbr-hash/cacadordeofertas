"""
Base definitions and data classes for scrapers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
import re
import urllib.parse


@dataclass
class ScrapedProduct:
    marketplace: str
    product_id: str
    title: str
    current_price: float
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    url: str = ""
    image_url: Optional[str] = None
    category: Optional[str] = None
    in_stock: bool = True

    def calculate_discount(self) -> float:
        """Calculates discount percentage if original_price is provided."""
        if self.original_price and self.original_price > self.current_price and self.original_price > 0:
            return round(((self.original_price - self.current_price) / self.original_price) * 100, 1)
        return self.discount_percent or 0.0


class BaseScraper(ABC):
    @property
    @abstractmethod
    def marketplace_name(self) -> str:
        pass

    @abstractmethod
    def scrape_deals(self, max_pages: int = 1) -> List[ScrapedProduct]:
        """Scrapes the main flash sales / deals section."""
        pass

    @abstractmethod
    def scrape_search(self, query: str, max_pages: int = 1) -> List[ScrapedProduct]:
        """Scrapes search results for high discount opportunities."""
        pass

    @staticmethod
    def parse_br_price(price_str: Optional[str]) -> Optional[float]:
        """
        Parses Brazilian Real formatted price string like 'R$ 1.250,99' or '399' or '19,90' into float.
        """
        if not price_str:
            return None

        # Remove 'R$', non-breaking spaces, and extra whitespace
        cleaned = re.sub(r"[^\d,\.]", "", price_str).strip()
        if not cleaned:
            return None

        # Format: 1.250,99 -> 1250.99
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def clean_url(raw_url: str) -> str:
        """Strips tracking query parameters (utm_*, ref, etc.) from URL."""
        if not raw_url:
            return ""
        parsed = urllib.parse.urlparse(raw_url)
        # Keep base URL path and drop tracking parameters
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return clean_url

    @staticmethod
    def clean_image_url(image_url: Optional[str], marketplace: Optional[str] = None) -> Optional[str]:
        """Upgrades low-res thumbnails to clean, ultra-high resolution real product photos."""
        if not image_url:
            return None
        url = image_url.strip()
        # Amazon: Upgrade to high-resolution direct photo
        if (marketplace and "amazon" in marketplace.lower()) or "media-amazon.com" in url or "ssl-images-amazon" in url:
            url = re.sub(r"\._[A-Z0-9_,]+_\.(jpg|jpeg|png|webp)", r"._AC_SL1500_.\1", url)
        # Mercado Livre: Upgrade from thumbnail (-I, -V) to original high-res photo (-O)
        elif (marketplace and "mercadolivre" in marketplace.lower()) or "mlstatic.com" in url:
            url = re.sub(r"-([IVTC])\.(jpg|webp|jpeg|png)", r"-O.\2", url)
        return url
