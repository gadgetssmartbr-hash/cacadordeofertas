"""
Shopee Brazil Scraper / Deals Provider.
Handles Shopee flash sales, search, and offers.
"""

import logging
import time
from typing import List, Optional
from curl_cffi import requests

from config.settings import settings
from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)


class ShopeeScraper(BaseScraper):
    @property
    def marketplace_name(self) -> str:
        return "shopee"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://shopee.com.br/flash_sale",
            "X-Requested-With": "XMLHttpRequest",
        })

    def scrape_deals(self, max_pages: int = 1) -> List[ScrapedProduct]:
        """
        Fetches Shopee flash sale / deals items via Shopee's public web endpoint.
        """
        products = []
        try:
            # Shopee Flash Sale Public API endpoint
            url = "https://shopee.com.br/api/v4/flash_sale/get_all_itemids?need_cart_info=true"
            response = self.session.get(url, impersonate="chrome", timeout=15)
            if response.status_code == 200:
                data = response.json()
                item_ids = data.get("data", {}).get("item_brief_list", [])[:20]

                if item_ids:
                    # Fetch details for the first batch of flash sale items
                    details_url = "https://shopee.com.br/api/v4/flash_sale/flash_sale_batch_get_items"
                    payload = {"item_ids": [it.get("itemid") for it in item_ids if it.get("itemid")]}
                    res_details = self.session.post(details_url, json=payload, impersonate="chrome", timeout=15)
                    if res_details.status_code == 200:
                        items_data = res_details.json().get("data", {}).get("items", [])
                        for item in items_data:
                            item_id = str(item.get("itemid", ""))
                            shop_id = str(item.get("shopid", ""))
                            title = item.get("name", "")
                            # Shopee stores prices in cents * 100000 or cents * 100
                            raw_price = item.get("price", 0)
                            current_price = raw_price / 100000 if raw_price > 10000 else raw_price / 100

                            raw_orig = item.get("price_before_discount", 0)
                            orig_price = raw_orig / 100000 if raw_orig > 10000 else raw_orig / 100

                            discount_percent = float(item.get("raw_discount", 0))

                            img_hash = item.get("image", "")
                            image_url = f"https://down-br.img.susercontent.com/file/{img_hash}" if img_hash else None
                            product_url = f"https://shopee.com.br/product/{shop_id}/{item_id}"

                            if current_price > 0 and title:
                                p = ScrapedProduct(
                                    marketplace=self.marketplace_name,
                                    product_id=f"SHP_{shop_id}_{item_id}",
                                    title=title,
                                    current_price=round(current_price, 2),
                                    original_price=round(orig_price, 2) if orig_price > current_price else None,
                                    discount_percent=discount_percent,
                                    url=product_url,
                                    image_url=image_url,
                                    category="Flash Sale",
                                )
                                products.append(p)
        except Exception as e:
            logger.debug(f"[Shopee] Flash sale scraping exception: {e}")

        return products

    def scrape_search(self, query: str, max_pages: int = 1) -> List[ScrapedProduct]:
        """Shopee search implementation (with fallback)."""
        products = []
        try:
            url = f"https://shopee.com.br/api/v4/search/search_items?by=relevancy&keyword={query}&limit=30&newest=0&order=desc&page_type=search"
            response = self.session.get(url, impersonate="chrome", timeout=15)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                for entry in items:
                    item = entry.get("item_basic", {})
                    if not item:
                        continue
                    item_id = str(item.get("itemid", ""))
                    shop_id = str(item.get("shopid", ""))
                    title = item.get("name", "")
                    raw_price = item.get("price", 0)
                    current_price = raw_price / 100000 if raw_price > 10000 else raw_price / 100
                    raw_orig = item.get("price_before_discount", 0)
                    orig_price = raw_orig / 100000 if raw_orig > 10000 else raw_orig / 100

                    discount_percent = float(item.get("raw_discount", 0))
                    img_hash = item.get("image", "")
                    image_url = f"https://down-br.img.susercontent.com/file/{img_hash}" if img_hash else None
                    product_url = f"https://shopee.com.br/product/{shop_id}/{item_id}"

                    if current_price > 0 and title:
                        p = ScrapedProduct(
                            marketplace=self.marketplace_name,
                            product_id=f"SHP_{shop_id}_{item_id}",
                            title=title,
                            current_price=round(current_price, 2),
                            original_price=round(orig_price, 2) if orig_price > current_price else None,
                            discount_percent=discount_percent,
                            url=product_url,
                            image_url=image_url,
                            category=query,
                        )
                        products.append(p)
        except Exception as e:
            logger.debug(f"[Shopee] Search scraping exception: {e}")

        return products
