"""
FastAPI Micro-Web Application for PriceGlitch & Drop Agent.
Serves interactive price timeline pages and recent deal alerts without portal bloat.
"""

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database.db import db
from monetizer.affiliate import monetizer
from config.settings import settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Caçador de Ofertas • Linha do Tempo",
    description="Micro-web app para visualização da linha do tempo e validação de preços anômalos.",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request, marketplace: Optional[str] = Query(None)):
    """Homepage: Minimalist feed of recent price drops and system glitches."""
    deals = db.get_latest_deals(limit=40, marketplace=marketplace)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "deals": deals,
            "current_market": marketplace,
        },
    )


@app.get("/p/{marketplace}/{product_id}", response_class=HTMLResponse)
async def product_timeline_page(request: Request, marketplace: str, product_id: str):
    """Product Page: Detailed price statistics, Chart.js timeline graph, and direct affiliate CTA."""
    product = db.get_product(marketplace, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado na base de dados.")

    # Get chronological timeline points for Chart.js
    timeline = db.get_product_price_timeline(marketplace, product_id)

    # Get aggregated stats
    stats = db.get_historical_stats(marketplace, product_id)

    # Generate monetized affiliate link
    raw_url = product.get("url") or ""
    affiliate_url = monetizer.monetize(raw_url, marketplace)

    return templates.TemplateResponse(
        request=request,
        name="product.html",
        context={
            "product": product,
            "timeline": timeline,
            "stats": stats,
            "affiliate_url": affiliate_url,
        },
    )



@app.get("/api/product/{marketplace}/{product_id}")
async def get_product_json(marketplace: str, product_id: str):
    """JSON API endpoint returning price history and stats."""
    product = db.get_product(marketplace, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    timeline = db.get_product_price_timeline(marketplace, product_id)
    stats = db.get_historical_stats(marketplace, product_id)

    return {
        "product": product,
        "timeline": timeline,
        "stats": stats,
    }


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "PriceGlitch Micro-Web"}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run("web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
