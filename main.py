"""
PriceGlitch & Drop Agent - Main Orchestrator.
Coordinates scrapers, statistical anomaly detection, monetization, and Telegram notifications.
"""

import argparse
import logging
import sys
import time
from datetime import datetime

# Enforce UTF-8 encoding on Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config.settings import settings
from database.db import db
from scrapers.amazon import AmazonScraper
from scrapers.mercadolivre import MercadoLivreScraper
from scrapers.shopee import ShopeeScraper
from engine.anomaly import AnomalyDetector
from monetizer.affiliate import monetizer
from notifier.telegram import notifier

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("PriceGlitchAgent")
console = Console(force_terminal=True)



class PriceGlitchOrchestrator:
    def __init__(self, target_marketplace: str = "all", force_alert: bool = False):
        self.detector = AnomalyDetector(database=db)
        self.scrapers = []
        self.force_alert = force_alert

        target = target_marketplace.lower()
        if target in ("all", "mercadolivre", "mlb"):
            self.scrapers.append(MercadoLivreScraper())
        if target in ("all", "amazon"):
            self.scrapers.append(AmazonScraper())
        if target in ("all", "shopee"):
            self.scrapers.append(ShopeeScraper())

    def run_cycle(self, include_search: bool = True) -> dict:

        """
        Executes one full sweep across configured scrapers.
        """
        start_time = time.time()
        total_scraped = 0
        total_anomalies = 0
        total_alerts = 0
        found_opportunities = []

        console.print(f"\n[bold yellow]🔍 INICIANDO VARREDURA MULTI-MARKETPLACE ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})...[/bold yellow]")

        for scraper in self.scrapers:
            market_name = scraper.marketplace_name.upper()
            console.print(f"\n[bold cyan]📦 Coletando ofertas de: {market_name}...[/bold cyan]")

            # 1. Scrape deals / flash sales
            products = scraper.scrape_deals(max_pages=2)
            console.print(f"  └ Ofertas relâmpago coletadas: [green]{len(products)}[/green]")

            # 2. Targeted search queries (optional for deeper scanning)
            if include_search:
                for query in settings.SEARCH_QUERIES[:2]:
                    search_items = scraper.scrape_search(query, max_pages=1)
                    products.extend(search_items)
                    console.print(f"  └ Busca por '{query}': [green]{len(search_items)}[/green]")

            total_scraped += len(products)

            # 3. Analyze products with AnomalyDetector
            for product in products:
                anomaly = self.detector.evaluate_product(product, ignore_cooldown=self.force_alert)

                if anomaly.is_anomaly:
                    total_anomalies += 1
                    # 4. Generate Monetized Affiliate Link
                    affiliate_url = monetizer.monetize(product.url, product.marketplace)

                    # 5. Send Alert (Telegram or Terminal Preview)
                    sent = notifier.send_alert(product, anomaly, affiliate_url, force=self.force_alert)
                    if sent:

                        total_alerts += 1
                        # Record alert in DB to enforce cooldown
                        db.record_alert(
                            marketplace=product.marketplace,
                            product_id=product.product_id,
                            price_alerted=product.current_price,
                            alert_type=anomaly.alert_type or "ANOMALY",
                        )

                    found_opportunities.append({
                        "marketplace": product.marketplace,
                        "title": product.title,
                        "price": product.current_price,
                        "orig_price": product.original_price,
                        "discount": anomaly.discount_percent,
                        "type": anomaly.alert_type,
                    })

        duration = round(time.time() - start_time, 2)

        # Print Cycle Summary
        self._display_summary(total_scraped, total_anomalies, total_alerts, duration, found_opportunities)

        return {
            "scraped": total_scraped,
            "anomalies": total_anomalies,
            "alerts": total_alerts,
            "duration": duration,
        }

    def _display_summary(
        self,
        total_scraped: int,
        total_anomalies: int,
        total_alerts: int,
        duration: float,
        opportunities: list,
    ) -> None:
        table = Table(title="📊 RESUMO DO CICLO DE VARREDURA", border_style="bright_blue")
        table.add_column("Métrica", style="cyan", no_wrap=True)
        table.add_column("Valor", style="magenta")

        table.add_row("Total de Produtos Inspecionados", str(total_scraped))
        table.add_row("Anomalias / Descontos Críticos", f"[bold red]{total_anomalies}[/bold red]")
        table.add_row("Alertas Disparados", f"[bold green]{total_alerts}[/bold green]")
        table.add_row("Tempo de Execução", f"{duration}s")
        table.add_row("Status Telegram", "[green]Ativo[/green]" if notifier.is_configured else "[yellow]Simulação (Dry-Run / Preview)[/yellow]")
        hours_status = "[green]Aberta[/green]" if notifier.is_within_alert_hours() else "[yellow]Silêncio Noturno (Sem disparos)[/yellow]"
        table.add_row("Janela de Disparos", f"{settings.ALERT_START_HOUR}h às {settings.ALERT_END_HOUR}h ({hours_status})")

        console.print(table)


        if opportunities:
            opp_table = Table(title="🔥 OPORTUNIDADES DETECTADAS NESTE CICLO", border_style="red")
            opp_table.add_column("Loja", style="cyan")
            opp_table.add_column("Tipo", style="bold red")
            opp_table.add_column("Título", style="white", max_width=45)
            opp_table.add_column("De (R$)", style="dim")
            opp_table.add_column("Por (R$)", style="bold green")
            opp_table.add_column("Queda", style="bold yellow")

            for op in opportunities[:10]:
                orig_str = f"R$ {op['orig_price']:.2f}" if op['orig_price'] else "N/A"
                opp_table.add_row(
                    op["marketplace"].upper(),
                    op["type"] or "DROP",
                    op["title"],
                    orig_str,
                    f"R$ {op['price']:.2f}",
                    f"-{op['discount']:.0f}%",
                )
            console.print(opp_table)


def display_banner():
    banner_text = (
        "[bold red]╔════════════════════════════════════════════════════════════════╗[/bold red]\n"
        "[bold red]║[/bold red]       [bold yellow]⚡ PRICEGLITCH & DROP AGENT v1.0 ⚡[/bold yellow]                       [bold red]║[/bold red]\n"
        "[bold red]║[/bold red]   [white]Caçador de Erros de Preço e Descontos Extremos Multi-Marketplace[/white]   [bold red]║[/bold red]\n"
        "[bold red]╚════════════════════════════════════════════════════════════════╝[/bold red]"
    )
    console.print(banner_text)


def show_database_stats():
    """Displays stats about the SQLite database."""
    with db._get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT count(*) as total FROM products")
        total_products = c.fetchone()["total"]

        c.execute("SELECT count(*) as total FROM price_history")
        total_history = c.fetchone()["total"]

        c.execute("SELECT count(*) as total FROM alerts_sent")
        total_alerts = c.fetchone()["total"]

    table = Table(title="💾 ESTATÍSTICAS DA MEMÓRIA LOCAL (SQLITE)", border_style="green")
    table.add_column("Tabela", style="cyan")
    table.add_column("Registros", style="bold yellow")
    table.add_row("Produtos Únicos Rastreados", str(total_products))
    table.add_row("Pontos de Histórico de Preço", str(total_history))
    table.add_row("Alertas Registrados (Histórico)", str(total_alerts))
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="PriceGlitch & Drop Agent - Caçador de Erros de Preço")
    parser.add_argument("--test", action="store_true", help="Executa um teste rápido de varredura com preview dos alertas")
    parser.add_argument("--once", action="store_true", help="Executa um ciclo completo de varredura e finaliza")
    parser.add_argument("--force", action="store_true", help="Força o disparo de alertas ignorando o cooldown de 12 horas")
    parser.add_argument("--marketplace", default="all", choices=["all", "amazon", "mercadolivre", "shopee"], help="Marketplace alvo")
    parser.add_argument("--interval", type=int, default=settings.SCAN_INTERVAL_MINUTES, help="Intervalo em minutos entre varreduras contínuas")
    parser.add_argument("--stats", action="store_true", help="Exibe estatísticas do banco de dados local SQLite")
    parser.add_argument("--web", action="store_true", help="Inicia o servidor da micro-página de histórico e linha do tempo")
    parser.add_argument("--port", type=int, default=8000, help="Porta para o servidor web (padrão: 8000)")
    parser.add_argument("--export-gh", action="store_true", help="Gera os arquivos HTML estáticos na pasta docs/ para o GitHub Pages")

    args = parser.parse_args()
    display_banner()

    if args.stats:
        show_database_stats()
        return

    if args.export_gh:
        console.print("[bold green]🚀 Gerando arquivos estáticos para o GitHub Pages na pasta docs/...[/bold green]")
        from export_gh_pages import export_to_github_pages
        res = export_to_github_pages()
        console.print(f"[bold green]✅ Concluído! {res['products_exported']} páginas de produtos e {res['total_deals']} ofertas em {res['output_dir']}.[/bold green]")
        return

    if args.web:
        console.print(f"[bold green]🌐 Iniciando Micro-Página em http://127.0.0.1:{args.port}...[/bold green]")
        console.print("[dim]Pressione Ctrl+C para encerrar o servidor web.[/dim]\n")
        from web.app import run_server
        run_server(port=args.port)
        return


    orchestrator = PriceGlitchOrchestrator(target_marketplace=args.marketplace, force_alert=args.force)



    if args.test or args.once:
        console.print("[bold yellow]Modo de execução única ativado.[/bold yellow]")
        orchestrator.run_cycle(include_search=not args.test)
        console.print("\n[bold green]✅ Ciclo concluído com sucesso![/bold green]")
        return

    # Continuous Polling Loop
    interval_seconds = args.interval * 60
    console.print(f"[bold green]🚀 Modo Contínuo Iniciado! Varreduras a cada {args.interval} minutos.[/bold green]")
    console.print("[dim]Pressione Ctrl+C para encerrar.[/dim]\n")

    try:
        while True:
            orchestrator.run_cycle(include_search=True)
            console.print(f"\n[dim]Aguardando {args.interval} minutos para a próxima varredura...[/dim]")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrompido pelo usuário. Encerrando agente com segurança.[/bold red]")
        sys.exit(0)


if __name__ == "__main__":
    main()
