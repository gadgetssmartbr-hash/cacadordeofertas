"""
Amazon Brazil Scraper for Deals and Sudden Drops.
"""

import logging
import time
from typing import List, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

from config.settings import settings
from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    @property
    def marketplace_name(self) -> str:
        return "amazon"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def scrape_deals(self, max_pages: int = 1) -> List[ScrapedProduct]:
        """
        Scrapes Amazon deals across high-discount categories (40%+ and 50%+ off filters).
        """
        products = []
        # Target keywords that often feature high-converting tech and home glitches
        deal_queries = [
            "eletronicos",
            "smart home",
            "informatica",
            "games",
            "audio",
        ]

        for query in deal_queries[:max_pages]:
            # pct-off=40- filters directly for items with >= 40% discount
            url = f"https://www.amazon.com.br/s?k={query}&pct-off=40-"
            try:
                response = self.session.get(url, impersonate="chrome", timeout=20)
                if response.status_code != 200:
                    logger.warning(f"[Amazon] Unexpected status {response.status_code} on {url}")
                    continue

                items = self._parse_search_results(response.text, default_category=query)
                products.extend(items)
                time.sleep(settings.REQUEST_DELAY_SECONDS)
            except Exception as e:
                logger.error(f"[Amazon] Error scraping deals for {query}: {e}")

        return products

    def scrape_search(self, query: str, max_pages: int = 1) -> List[ScrapedProduct]:
        """
        Scrapes Amazon search results for a specific query, prioritizing products with discounts.
        """
        products = []
        for page in range(1, max_pages + 1):
            url = f"https://www.amazon.com.br/s?k={query.replace(' ', '+')}&page={page}"
            try:
                response = self.session.get(url, impersonate="chrome", timeout=20)
                if response.status_code != 200:
                    logger.warning(f"[Amazon] Status {response.status_code} for search {query}")
                    continue

                items = self._parse_search_results(response.text, default_category=query)
                products.extend(items)
                time.sleep(settings.REQUEST_DELAY_SECONDS)
            except Exception as e:
                logger.error(f"[Amazon] Error scraping search {query} page {page}: {e}")

        return products

    def _parse_search_results(self, html: str, default_category: Optional[str] = None) -> List[ScrapedProduct]:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all("div", attrs={"data-component-type": "s-search-result"})
        parsed_products = []

        for item in items:
            try:
                asin = item.get("data-asin", "").strip()
                if not asin:
                    continue

                # Title
                title_elem = item.find("h2")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # Current Price
                price_elem = item.find("span", class_="a-price")
                if not price_elem:
                    continue

                offscreen_price = price_elem.find("span", class_="a-offscreen")
                price_str = offscreen_price.get_text(strip=True) if offscreen_price else None
                current_price = self.parse_br_price(price_str)
                if not current_price or current_price <= 0:
                    continue

                # Original Price (Strike-through)
                original_price = None
                orig_elem = item.find("span", class_="a-text-price")
                if orig_elem:
                    orig_offscreen = orig_elem.find("span", class_="a-offscreen")
                    if orig_offscreen:
                        original_price = self.parse_br_price(orig_offscreen.get_text(strip=True))

                # Image
                image_url = None
                img_elem = item.find("img", class_="s-image")
                if img_elem:
                    image_url = img_elem.get("src")

                # Clean Amazon URL
                clean_url = f"https://www.amazon.com.br/dp/{asin}"

                product = ScrapedProduct(
                    marketplace=self.marketplace_name,
                    product_id=asin,
                    title=title,
                    current_price=current_price,
                    original_price=original_price,
                    url=clean_url,
                    image_url=image_url,
                    category=default_category or "Geral",
                )
                product.discount_percent = product.calculate_discount()
                parsed_products.append(product)

            except Exception as e:
                logger.debug(f"[Amazon] Error parsing item: {e}")
                continue

        return parsed_products
