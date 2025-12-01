from .models import CompetitorPriceSnapshot
from decimal import Decimal

def competitor_stats(product):
    qs = CompetitorPriceSnapshot.objects.filter(
        competitor_product__product=product
    )

    if not qs.exists():
        return None

    prices = [s.price for s in qs]
    return {
        "min": min(prices),
        "max": max(prices),
        "avg": sum(prices) / len(prices),
    }
