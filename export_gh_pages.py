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


def export_to_github_pages(output_dir: Path = DOCS_DIR, limit_deals: int = 60) -> dict:
    """
    Renders all templates and writes static HTML files into output_dir (docs/).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # 3. Render individual product pages: docs/p/{marketplace}/{product_id}/index.html
    product_template = env.get_template("product.html")
    products_exported = 0

    # Collect unique products from alerts and database
    seen_products = set()
    for deal in deals:
        mkt = deal["marketplace"]
        pid = deal["product_id"]
        seen_products.add((mkt, pid))

    for mkt, pid in seen_products:
        prod = db.get_product(mkt, pid)
        if not prod:
            continue

        timeline = db.get_product_price_timeline(mkt, pid)
        stats = db.get_historical_stats(mkt, pid)
        raw_url = prod.get("url") or ""
        affiliate_url = monetizer.monetize(raw_url, mkt)

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
