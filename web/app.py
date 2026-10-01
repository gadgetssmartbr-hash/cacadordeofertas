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
from engine.product_resolver import ProductResolver

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
    radar_items = db.get_active_radar_items()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "deals": deals,
            "radar_items": radar_items,
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


from pydantic import BaseModel


class RadarRequest(BaseModel):
    target_input: str
    desired_price: Optional[float] = None
    user_contact: Optional[str] = None


@app.post("/api/radar")
async def add_to_radar(req: RadarRequest):
    """Registers and verifies a product URL or search term into the active tracking radar."""
    clean_input = (req.target_input or "").strip()
    if not clean_input or len(clean_input) < 3:
        raise HTTPException(
            status_code=400,
            detail="Informe um link de produto ou nome válido com pelo menos 3 caracteres."
        )

    # 1. Real-time product existence verification
    resolved = ProductResolver.resolve(clean_input)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"Produto não encontrado! Não localizamos nenhum item na Amazon ou Mercado Livre para '{clean_input}'. Verifique se o nome está correto ou cole o link direto do produto."
        )

    # 2. Add to radar_items with verified canonical metadata
    item = db.add_radar_item(
        target_input=clean_input,
        desired_price=req.desired_price,
        user_contact=req.user_contact,
        title=resolved["title"],
        image_url=resolved.get("image_url"),
        last_price=resolved.get("current_price"),
        marketplace=resolved["marketplace"],
    )

    # 3. Ensure product is registered in database for automated background sweeps
    if resolved.get("product_id") and resolved.get("url"):
        db.upsert_product(
            marketplace=resolved["marketplace"],
            product_id=resolved["product_id"],
            title=resolved["title"],
            url=resolved["url"],
            image_url=resolved.get("image_url"),
            category="Radar",
        )
        if resolved.get("current_price") and resolved["current_price"] > 0:
            db.record_price(
                marketplace=resolved["marketplace"],
                product_id=resolved["product_id"],
                price=resolved["current_price"],
            )

    return {
        "status": "success",
        "verified": True,
        "message": "Produto verificado e adicionado ao Radar com sucesso!",
        "product": resolved,
        "item": item,
    }


@app.get("/api/radar")
async def list_radar():
    """Lists active radar targets."""
    return {"radar_items": db.get_active_radar_items()}


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "PriceGlitch Micro-Web"}



def run_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run("web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
