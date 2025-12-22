from django.utils import timezone
from decimal import Decimal

from competitor.models import CompetitorPriceSnapshot
from .carrefour_api import scrape_carrefour
from .leclerc_api import scrape_leclerc
from .selenium_scraper import scrape_selenium
from .confidence import compute_confidence


def scrape_competitor(product, competitor):
    """
    Selects the best scraping method per competitor
    """
    name = competitor.name.lower()

    if competitor.scrape_method == "api":
        if "carrefour" in name:
            return scrape_carrefour(product)
        if "leclerc" in name or "e.leclerc" in name:
            return scrape_leclerc(product)

    # fallback (Franprix, Lidl, Aldi, others)
    return scrape_selenium(product, competitor)


def scrape_all_competitors(product, competitors):
    """
    MAIN ENTRY POINT
    Called by Celery task

    Returns structured result for logging / monitoring
    """
    results = []

    for competitor in competitors:
        try:
            data = scrape_competitor(product, competitor)

            if not data:
                results.append({
                    "competitor": competitor.name,
                    "status": "no_data"
                })
                continue

            # --- Confidence score ---
            confidence = compute_confidence(product, data)

            # --- Save snapshot ---
            CompetitorPriceSnapshot.objects.create(
                product=product,
                competitor=competitor,
                price=Decimal(data["price"]),
                product_url=data.get("url"),
                scraped_at=timezone.now()
            )

            results.append({
                "competitor": competitor.name,
                "price": float(data["price"]),
                "confidence": confidence,
                "status": "ok"
            })

        except Exception as e:
            results.append({
                "competitor": competitor.name,
                "status": "error",
                "error": str(e)
            })

    return {
        "product": product.barcode,
        "competitors_checked": len(competitors),
        "results": results
    }
