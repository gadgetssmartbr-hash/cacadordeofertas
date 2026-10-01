"""
Affiliate Link Converter and Monetizer.
Converts clean product URLs into tracked affiliate links for Amazon, Mercado Livre, Shopee, and Lomadee/Awin.
"""

import urllib.parse
from typing import Optional
from config.settings import settings


class AffiliateLinkGenerator:
    def __init__(
        self,
        amazon_tag: Optional[str] = None,
        mlb_tag: Optional[str] = None,
        shopee_id: Optional[str] = None,
        lomadee_id: Optional[str] = None,
    ):
        self.amazon_tag = amazon_tag or settings.AMAZON_TAG
        self.mlb_tag = mlb_tag or settings.MERCADOLIVRE_AFFILIATE_TAG
        self.shopee_id = shopee_id or settings.SHOPEE_AFFILIATE_ID
        self.lomadee_id = lomadee_id or settings.LOMADEE_SOURCE_ID

    def monetize(self, url: str, marketplace: str) -> str:
        """
        Converts a raw product URL into a monetized affiliate link.
        """
        if not url:
            return ""

        marketplace = marketplace.lower()

        # 1. Amazon Associates
        if marketplace == "amazon":
            return self._build_amazon_link(url)

        # 2. Mercado Livre
        if marketplace in ("mercadolivre", "mlb"):
            return self._build_mlb_link(url)

        # 3. Shopee
        if marketplace == "shopee":
            return self._build_shopee_link(url)

        # 4. Fallback: Lomadee wrapper if configured
        if self.lomadee_id:
            return self._wrap_lomadee(url)

        return url

    def _build_amazon_link(self, url: str) -> str:
        tag = self.amazon_tag
        if not tag:
            return url

        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        params["tag"] = [tag]
        # Keep clean
        params.pop("ref", None)
        params.pop("ref_", None)
        params.pop("psc", None)

        new_query = urllib.parse.urlencode(params, doseq=True)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

    def _build_mlb_link(self, url: str) -> str:
        # If Lomadee is set up, Lomadee supports Mercado Livre with high conversion
        if self.lomadee_id:
            return self._wrap_lomadee(url)

        # If direct Mercado Livre Afiliados tag is available
        if self.mlb_tag:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}matt_tool={self.mlb_tag}"

        return url

    def _build_shopee_link(self, url: str) -> str:
        if self.lomadee_id:
            return self._wrap_lomadee(url)

        if self.shopee_id:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}aff_id={self.shopee_id}"

        return url

    def _wrap_lomadee(self, target_url: str) -> str:
        encoded = urllib.parse.quote(target_url, safe="")
        return f"https://redir.lomadee.com/v2/{self.lomadee_id}?url={encoded}"


# Default singleton
monetizer = AffiliateLinkGenerator()
