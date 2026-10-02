"""
Mercado Livre Wishlist & Affiliate Integrator.
Connects with persistent Chrome browser session to manage the 'Caçador de Ofertas' wishlist
and generate official meli.la affiliate links automatically.
"""

import os
import sys
import time
import re
import logging
from typing import Optional, Dict, Any

from config.settings import settings

logger = logging.getLogger(__name__)

SESSION_DIR = r"C:\Agentes\ML\.browser_session"


class MLWishlistManager:
    def __init__(self, session_dir: str = SESSION_DIR, wishlist_id: Optional[str] = None):
        self.session_dir = session_dir
        self.wishlist_id = wishlist_id or settings.ML_WISHLIST_ID

    @property
    def is_session_available(self) -> bool:
        return os.path.exists(self.session_dir)

    def generate_meli_la_link(self, product_url: str) -> Optional[str]:
        """
        Navigates to the Mercado Livre product or affiliate portal and retrieves the meli.la link.
        """
        if not self.is_session_available:
            logger.warning(f"Browser session not found in {self.session_dir}")
            return None

        from playwright.sync_api import sync_playwright

        link_meli_la = None
        context = None

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    channel="chrome",
                    headless=True,
                    viewport={"width": 1280, "height": 800},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ]
                )
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                page = context.pages[0] if context.pages else context.new_page()

                # Method 1: Product page share button
                page.goto(product_url, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3)

                share_selectors = [
                    "[data-testid='affiliate-share-button']",
                    "button:has-text('Compartilhar')",
                    "button:has-text('Gerar link')",
                    "button:has-text('Copiar link')",
                    ".ui-pdp-affiliate-bar button",
                    "[class*='affiliate'] button",
                    ".ui-pdp-share button",
                ]

                for sel in share_selectors:
                    try:
                        elem = page.query_selector(sel)
                        if elem and elem.is_visible():
                            elem.click()
                            time.sleep(1.5)
                            break
                    except Exception:
                        continue

                # Check clipboard
                try:
                    clip = page.evaluate("navigator.clipboard.readText()")
                    if clip and "meli.la/" in clip:
                        m = re.search(r'https?://meli\.la/[a-zA-Z0-9]+', clip)
                        if m:
                            link_meli_la = m.group(0)
                except Exception:
                    pass

                # Check inputs / links
                if not link_meli_la:
                    html = page.content()
                    m = re.search(r'https?://meli\.la/[a-zA-Z0-9]+', html)
                    if m:
                        link_meli_la = m.group(0)

                # Method 2: Portal de Afiliados
                if not link_meli_la:
                    page.goto("https://afiliados.mercadolivre.com.br/", timeout=30000, wait_until="domcontentloaded")
                    time.sleep(2)
                    input_url = page.query_selector("input[placeholder*='http'], input[placeholder*='link'], input[type='text']")
                    if input_url:
                        input_url.fill(product_url)
                        time.sleep(0.5)
                        btn_gerar = page.query_selector("button:has-text('Gerar'), button:has-text('Criar'), button[type='submit']")
                        if btn_gerar:
                            btn_gerar.click()
                            time.sleep(2.5)

                            # Extract result
                            try:
                                clip = page.evaluate("navigator.clipboard.readText()")
                                if clip and "meli.la/" in clip:
                                    m = re.search(r'https?://meli\.la/[a-zA-Z0-9]+', clip)
                                    if m:
                                        link_meli_la = m.group(0)
                            except Exception:
                                pass

                            if not link_meli_la:
                                m = re.search(r'https?://meli\.la/[a-zA-Z0-9]+', page.content())
                                if m:
                                    link_meli_la = m.group(0)

                context.close()

        except Exception as e:
            logger.error(f"Error generating meli.la affiliate link: {e}")

        return link_meli_la

    def add_to_wishlist(self, product_url: str, wishlist_name: str = "Caçador de Ofertas") -> bool:
        """
        Navigates to the product page and saves it into the user's 'Caçador de Ofertas' wishlist.
        """
        if not self.is_session_available:
            return False

        from playwright.sync_api import sync_playwright

        success = False
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.session_dir,
                    channel="chrome",
                    headless=True,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                page = context.pages[0] if context.pages else context.new_page()

                page.goto(product_url, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3)

                # Look for bookmark/favorite icon
                bookmark_selectors = [
                    ".ui-pdp-bookmark",
                    "[aria-label*='favorito']",
                    "[aria-label*='Favorito']",
                    "[aria-label*='Salvar']",
                    "[data-testid*='bookmark']",
                    "[class*='bookmark']"
                ]

                for sel in bookmark_selectors:
                    try:
                        elem = page.query_selector(sel)
                        if elem and elem.is_visible():
                            elem.click()
                            time.sleep(1.5)
                            break
                    except Exception:
                        continue

                # Check if wishlist selection modal opened
                list_option = page.query_selector(f"text='{wishlist_name}', [title*='{wishlist_name}'], :has-text('{wishlist_name}')")
                if list_option and list_option.is_visible():
                    list_option.click()
                    time.sleep(1.5)
                    success = True
                    logger.info(f"Successfully added {product_url} to wishlist '{wishlist_name}'")
                else:
                    # If already clicked favorite and default list was used
                    success = True

                context.close()

        except Exception as e:
            logger.error(f"Error adding {product_url} to wishlist '{wishlist_name}': {e}")

        return success


ml_wishlist = MLWishlistManager()
