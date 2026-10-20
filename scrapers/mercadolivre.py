"""
Mercado Livre Scraper for Deals and Sudden Drops.
"""

import os
import logging
import re
import time
from typing import List, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

from config.settings import settings
from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)


class MercadoLivreScraper(BaseScraper):
    @property
    def marketplace_name(self) -> str:
        return "mercadolivre"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        })

        # Load authenticated browser session cookies if available to prevent captcha wall
        session_dir = r"C:\Agentes\ML\.browser_session"
        if os.path.exists(session_dir):
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    ctx = p.chromium.launch_persistent_context(session_dir, channel="chrome", headless=True)
                    cookie_dict = {c['name']: c['value'] for c in ctx.cookies() if 'mercadolivre.com' in c.get('domain', '')}
                    ctx.close()
                if cookie_dict:
                    self.session.cookies.update(cookie_dict)
                    logger.info(f"[MLB] Loaded {len(cookie_dict)} session cookies from browser profile.")
            except Exception as e:
                logger.debug(f"[MLB] Could not load browser session cookies: {e}")

    def scrape_deals(self, max_pages: int = 1) -> List[ScrapedProduct]:
        """Scrapes Mercado Livre's main deals and high-converting categories (Supplements, Tech, Home)."""
        products = []
        deal_endpoints = [
            ("https://www.mercadolivre.com.br/ofertas", "Ofertas"),
            ("https://www.mercadolivre.com.br/ofertas?category=MLB1271", "Suplementos e Fitness"),
            ("https://www.mercadolivre.com.br/ofertas?category=MLB1051", "Celulares"),
            ("https://www.mercadolivre.com.br/ofertas?category=MLB1000", "Eletrônicos"),
            ("https://www.mercadolivre.com.br/ofertas?category=MLB1648", "Informática"),
            ("https://www.mercadolivre.com.br/ofertas?category=MLB1144", "Games"),
        ]

        for base_url, category_tag in deal_endpoints:
            for page in range(1, max_pages + 1):
                separator = "&" if "?" in base_url else "?"
                url = f"{base_url}{separator}page={page}"
                try:
                    response = self.session.get(url, impersonate="chrome124", timeout=20)
                    if response.status_code != 200 or "account-verification" in response.url or "captcha" in response.url:
                        logger.debug(f"[MLB] Skipping verification endpoint on {url}")
                        continue

                    page_products = self._parse_items_from_html(response.text, default_category=category_tag)
                    products.extend(page_products)
                    time.sleep(settings.REQUEST_DELAY_SECONDS)
                except Exception as e:
                    logger.error(f"[MLB] Error scraping deals from {url}: {e}")
        return products

    def scrape_search(self, query: str, max_pages: int = 1) -> List[ScrapedProduct]:
        """Scrapes search results for a specific product query."""
        products = []
        encoded_query = query.replace(" ", "-")
        for page in range(1, max_pages + 1):
            offset = (page - 1) * 50 + 1
            if page == 1:
                url = f"https://lista.mercadolivre.com.br/{encoded_query}"
            else:
                url = f"https://lista.mercadolivre.com.br/{encoded_query}_Desde_{offset}"

            try:
                response = self.session.get(url, impersonate="chrome", timeout=20)
                if response.status_code != 200 or "account-verification" in response.url:
                    logger.debug(f"[MLB] Search '{query}' redirected to verification, skipping.")
                    continue

                page_products = self._parse_items_from_html(response.text, default_category=query)
                products.extend(page_products)
                time.sleep(settings.REQUEST_DELAY_SECONDS)
            except Exception as e:
                logger.error(f"[MLB] Error scraping search {query} page {page}: {e}")
        return products

    def _parse_items_from_html(self, html: str, default_category: Optional[str] = None) -> List[ScrapedProduct]:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".poly-card, .ui-search-result__wrapper, .promotion-item")
        parsed_products = []

        for item in items:
            try:
                # 1. Title & Link
                title_elem = (
                    item.select_one(".poly-component__title")
                    or item.select_one(".poly-card__title")
                    or item.select_one("a.poly-card__title")
                    or item.select_one(".ui-search-item__title")
                    or item.select_one(".promotion-item__title")
                )
                link_elem = (
                    item.select_one("a.poly-component__title")
                    or item.select_one("a.poly-card__title")
                    or item.select_one(".ui-search-link")
                    or item.select_one("a.promotion-item__link-container")
                    or item.select_one("a")
                )

                if not title_elem or not link_elem:
                    continue

                title = title_elem.get_text(strip=True)
                raw_url = link_elem.get("href", "")
                if not raw_url:
                    continue

                # 2. Extract Product ID (MLB / Item ID)
                id_match = re.search(r"MLB-?(\d+)", raw_url, re.IGNORECASE)
                product_id = f"MLB{id_match.group(1)}" if id_match else ""
                if not product_id:
                    # Alternative ID from URL path
                    path_match = re.search(r"/p/([A-Z0-9]+)", raw_url)
                    product_id = path_match.group(1) if path_match else f"MLB_{hash(title) % 10000000}"

                # 3. Clean URL
                clean_link = self.clean_url(raw_url)

                # 4. Prices
                # Current Price
                price_container = item.select_one(".poly-price__current") or item.select_one(".ui-search-price__second-line") or item
                price_fraction = price_container.select_one(".andes-money-amount__fraction")
                price_cents = price_container.select_one(".andes-money-amount__cents")

                if not price_fraction:
                    continue

                current_price_str = price_fraction.get_text(strip=True)
                if price_cents:
                    current_price_str += f",{price_cents.get_text(strip=True)}"
                current_price = self.parse_br_price(current_price_str)
                if not current_price or current_price <= 0:
                    continue

                # Original Price (Previous Price)
                original_price = None
                orig_container = item.select_one(".andes-money-amount--previous") or item.select_one(".andes-money-amount--sub-line")
                if orig_container:
                    orig_fraction = orig_container.select_one(".andes-money-amount__fraction")
                    orig_cents = orig_container.select_one(".andes-money-amount__cents")
                    if orig_fraction:
                        orig_str = orig_fraction.get_text(strip=True)
                        if orig_cents:
                            orig_str += f",{orig_cents.get_text(strip=True)}"
                        original_price = self.parse_br_price(orig_str)

                # 5. Discount Percentage
                discount_elem = item.select_one(".andes-money-amount__discount") or item.select_one(".ui-search-price__discount")
                discount_percent = None
                if discount_elem:
                    disc_text = discount_elem.get_text(strip=True)
                    match = re.search(r"(\d+)%", disc_text)
                    if match:
                        discount_percent = float(match.group(1))

                # If no explicit discount badge, calculate if original price exists
                if not discount_percent and original_price and original_price > current_price:
                    discount_percent = round(((original_price - current_price) / original_price) * 100, 1)

                # 6. Image
                img_elem = item.select_one("img.poly-component__picture") or item.select_one("img.ui-search-result-image__element") or item.select_one("img")
                image_url = None
                if img_elem:
                    raw_img = img_elem.get("data-src") or img_elem.get("src")
                    image_url = self.clean_image_url(raw_img, self.marketplace_name)

                product = ScrapedProduct(
                    marketplace=self.marketplace_name,
                    product_id=product_id,
                    title=title,
                    current_price=current_price,
                    original_price=original_price,
                    discount_percent=discount_percent,
                    url=clean_link,
                    image_url=image_url,
                    category=default_category or "Geral",
                )
                parsed_products.append(product)

            except Exception as e:
                logger.debug(f"[MLB] Error parsing item: {e}")
                continue

        return parsed_products
