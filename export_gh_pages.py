"""
Static Site Generator for GitHub Pages.
Exports the SQLite price history and deal alerts into static HTML files (docs/ folder).
Ready to be hosted for free on GitHub Pages.
"""

import json
import logging
import os
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from config.settings import settings
from database.db import db
from monetizer.affiliate import monetizer

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
DOCS_DIR = BASE_DIR / "docs"


def export_to_github_pages(output_dir: Path = DOCS_DIR, limit_deals: int = 100) -> dict:
    """
    Renders all templates and writes static HTML files into output_dir (docs/).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create .nojekyll (tells GitHub Pages not to process files with Jekyll)
    nojekyll_file = output_dir / ".nojekyll"
    nojekyll_file.touch(exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    # Fetch latest deals and active radar items from database
    deals = db.get_latest_deals(limit=limit_deals)
    radar_items = db.get_active_radar_items()

    # 2. Render index.html (Homepage)
    index_template = env.get_template("index.html")
    index_html = index_template.render(
        deals=deals,
        radar_items=radar_items,
        base_path="./",
        is_static=True,
        current_market=None,
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    # 3. Render 404.html (Dynamic SPA fallback)
    try:
        template_404 = env.get_template("404.html")
        html_404 = template_404.render(
            base_path="./",
            is_static=True,
        )
        (output_dir / "404.html").write_text(html_404, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not render 404.html: {e}")

    # 4. Render individual product pages: docs/p/{marketplace}/{product_id}/index.html
    product_template = env.get_template("product.html")
    products_exported = 0
    all_products_data = {}

    # Collect unique products from deals, alerts, and database
    seen_products = set()
    for deal in deals:
        seen_products.add((deal["marketplace"], deal["product_id"]))

    for alert in db.get_recent_alerts(limit=200):
        seen_products.add((alert["marketplace"], alert["product_id"]))

    for prod in db.get_all_tracked_products(limit=300):
        seen_products.add((prod["marketplace"], prod["product_id"]))

    for mkt, pid in seen_products:
        prod = db.get_product(mkt, pid)
        if not prod:
            continue

        timeline = db.get_product_price_timeline(mkt, pid)
        stats = db.get_historical_stats(mkt, pid)
        raw_url = prod.get("url") or ""
        affiliate_url = monetizer.monetize(raw_url, mkt)

        # Store in json data lookup
        prod_key = f"{mkt.lower()}:{pid}"
        all_products_data[prod_key] = {
            "marketplace": mkt,
            "product_id": pid,
            "title": prod.get("title", ""),
            "url": raw_url,
            "affiliate_url": affiliate_url,
            "image_url": prod.get("image_url", ""),
            "current_price": prod.get("current_price", 0.0),
            "original_price": prod.get("original_price"),
            "discount_percent": prod.get("discount_percent"),
            "min_price": stats.get("min_price", prod.get("current_price", 0.0)),
            "avg_price": stats.get("avg_price", prod.get("current_price", 0.0)),
            "count": stats.get("count", len(timeline)),
            "timeline": timeline,
        }

        prod_dir = output_dir / "p" / mkt / pid
        prod_dir.mkdir(parents=True, exist_ok=True)

        prod_html = product_template.render(
            product=prod,
            timeline=timeline,
            stats=stats,
            affiliate_url=affiliate_url,
            base_path="../../../",
            is_static=True,
        )
        (prod_dir / "index.html").write_text(prod_html, encoding="utf-8")
        products_exported += 1

    # 5. Export JSON data feed for dynamic lookups
    (data_dir / "products.json").write_text(
        json.dumps({"products": all_products_data}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    logger.info(f"GitHub Pages export completed: {products_exported} product pages generated in '{output_dir}'.")
    return {
        "output_dir": str(output_dir),
        "total_deals": len(deals),
        "products_exported": products_exported,
    }


if __name__ == "__main__":
    import sys
    # Enforce UTF-8 for console
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    print("🚀 Gerando arquivos estáticos para o GitHub Pages...")
    res = export_to_github_pages()
    print(f"✅ Concluído com sucesso!")
    print(f"📁 Pasta de destino: {res['output_dir']}")
    print(f"📦 Páginas de produtos geradas: {res['products_exported']}")
    print(f"⚡ Feed de ofertas: {res['total_deals']} itens incluídos no index.html")
