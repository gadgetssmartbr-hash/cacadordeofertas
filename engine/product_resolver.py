"""
Product Resolver and Verifier for Radar de Ofertas.
Validates if a product exists across Amazon, Mercado Livre, and local price database,
and extracts verified canonical metadata (title, image, current price, URL).
"""

import logging
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper
from scrapers.amazon import AmazonScraper
from database.db import db

logger = logging.getLogger(__name__)


class ProductResolver:
    @staticmethod
    def resolve(target_input: str) -> Optional[Dict[str, Any]]:
        """
        Validates if target_input exists and resolves canonical product data.
        Returns product dictionary if found, or None if product doesn't exist.
        """
        clean = (target_input or "").strip()
        if not clean or len(clean) < 3:
            return None

        # 1. Direct URL Input
        if clean.startswith("http://") or clean.startswith("https://"):
            return ProductResolver._resolve_url(clean)

        # 2. Search Query Input
        return ProductResolver._resolve_query(clean)

    @staticmethod
    def _resolve_url(url: str) -> Optional[Dict[str, Any]]:
        """Verifies and extracts product metadata from a direct marketplace link."""
        url_lower = url.lower()

        # Amazon URL
        if "amazon.com" in url_lower or "amzn." in url_lower:
            try:
                r = requests.get(url, impersonate="chrome124", timeout=15)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    title_elem = soup.find(id="productTitle")
                    if title_elem and title_elem.text.strip():
                        title = title_elem.text.strip()
                        # Current price
                        price_elem = soup.select_one(".a-price .a-offscreen") or soup.select_one("#priceblock_ourprice") or soup.select_one("#priceblock_dealprice")
                        current_price = BaseScraper.parse_br_price(price_elem.text if price_elem else None)

                        # Image
                        img_elem = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront")
                        raw_img = img_elem.get("src") if img_elem else None
                        image_url = BaseScraper.clean_image_url(raw_img, "amazon")

                        # ASIN
                        asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
                        asin = asin_match.group(1) if asin_match else f"AMZ_{abs(hash(url)) % 1000000000}"

                        return {
                            "marketplace": "amazon",
                            "product_id": asin,
                            "title": title,
                            "current_price": current_price,
                            "image_url": image_url,
                            "url": BaseScraper.clean_url(url),
                            "target_input": url,
                        }
            except Exception as e:
                logger.warning(f"Error resolving Amazon URL '{url}': {e}")

        # Mercado Livre URL
        elif "mercadolivre.com" in url_lower or "mercadolibre.com" in url_lower:
            try:
                r = requests.get(url, impersonate="chrome124", timeout=15)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    h1 = soup.find("h1")
                    og_title = soup.find("meta", property="og:title")
                    title = (h1.text if h1 else (og_title.get("content") if og_title else "")).strip()

                    # Avoid generic site pages
                    if title and "Mercado Livre" not in title and "Suspicious" not in title:
                        og_img = soup.find("meta", property="og:image")
                        raw_img = og_img.get("content") if og_img else None
                        image_url = BaseScraper.clean_image_url(raw_img, "mercadolivre")

                        # Price
                        price_elem = soup.select_one(".andes-money-amount__fraction")
                        current_price = BaseScraper.parse_br_price(price_elem.text if price_elem else None)

                        # MLB ID
                        id_match = re.search(r"MLB-?(\d+)", url)
                        pid = f"MLB{id_match.group(1)}" if id_match else f"MLB_{abs(hash(url)) % 1000000000}"

                        # Check if product is already in our DB with price history
                        existing = db.get_product("mercadolivre", pid)
                        if existing and not current_price:
                            current_price = existing.get("current_price")

                        return {
                            "marketplace": "mercadolivre",
                            "product_id": pid,
                            "title": title,
                            "current_price": current_price,
                            "image_url": image_url,
                            "url": BaseScraper.clean_url(url),
                            "target_input": url,
                        }
            except Exception as e:
                logger.warning(f"Error resolving Mercado Livre URL '{url}': {e}")

        return None

    @staticmethod
    def _resolve_query(query: str) -> Optional[Dict[str, Any]]:
        """Resolves a product by name/search term using Amazon live search and local DB."""
        query_lower = query.lower()
        accessory_words = [
            "controle", "joystick", "gamepad", "headset", "fone de ouvido",
            "capa", "case", "capinha", "pelicula", "película", "adesivo", "skin",
            "suporte", "estojo", "bag", "protetor", "silicone", "pulseira",
            "carregador", "cabo", "base carregadora", "dock", "docking",
            "bateria extra", "fonte de alimentacao", "adaptador"
        ]
        wants_accessory = any(re.search(rf"\b{aw}\b", query_lower) for aw in accessory_words)

        # 1. Check local database (only accept if not an unwanted accessory)
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.marketplace, p.product_id, p.title, p.url, p.image_url, h.price as current_price
                FROM products p
                LEFT JOIN price_history h ON p.marketplace = h.marketplace AND p.product_id = h.product_id
                WHERE p.title LIKE ?
                ORDER BY h.timestamp DESC
                LIMIT 5
            """, (f"%{query}%",))
            rows = cur.fetchall()
            for row in rows:
                title_lower = row["title"].lower()
                is_acc = any(re.search(rf"\b{aw}\b", title_lower) for aw in accessory_words)
                if wants_accessory or not is_acc:
                    return {
                        "marketplace": row["marketplace"],
                        "product_id": row["product_id"],
                        "title": row["title"],
                        "current_price": row["current_price"],
                        "image_url": row["image_url"],
                        "url": row["url"],
                        "target_input": query,
                    }

        # 2. Search Amazon Brazil live
        try:
            amz = AmazonScraper()
            items = amz.scrape_search(query, max_pages=1)
            if not items and "console" in query_lower:
                # Retry without 'console' prefix if specific query yielded 0
                fallback_query = query_lower.replace("console", "").strip()
                items = amz.scrape_search(fallback_query, max_pages=1)

            if items:
                # Prioritize non-accessory matching items first
                valid_items = []
                for itm in items:
                    title_lower = itm.title.lower()
                    is_acc = any(re.search(rf"\b{aw}\b", title_lower) for aw in accessory_words)
                    if wants_accessory or not is_acc:
                        valid_items.append(itm)

                chosen_items = valid_items if valid_items else items
                top = chosen_items[0]

                return {
                    "marketplace": "amazon",
                    "product_id": top.product_id,
                    "title": top.title,
                    "current_price": top.current_price,
                    "image_url": top.image_url,
                    "url": top.url,
                    "target_input": query,
                }
        except Exception as e:
            logger.warning(f"Error searching Amazon for '{query}': {e}")

        return None
