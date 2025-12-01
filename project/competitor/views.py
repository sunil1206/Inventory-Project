from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.db.models import Min, Avg
from django.db.models.functions import TruncDate

from Inventory.models import Product, ProductPrice, Supermarket
from competitor.models import CompetitorPriceSnapshot

# from competitor.tasks import (
#     scrape_product_competitors_task,
#     scrape_supermarket_products_task,
# )

# competitor/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.db.models import Min, Avg
from django.db.models.functions import TruncDate

from Inventory.models import Product, ProductPrice, Supermarket
from competitor.models import CompetitorPriceSnapshot
# from competitor.tasks import (
#     scrape_product_competitors_task,
#     scrape_supermarket_products_task,
# )

@login_required
def competitor_compare_all(request, supermarket_id):
    """
    View competitor pricing for all products in a supermarket.
    Includes:
     - Best price logic
     - Overpriced logic
     - Competitive threshold
     - Preloading of competitor snapshots
    """

    supermarket = get_object_or_404(
        Supermarket,
        pk=supermarket_id,
        owner=request.user
    )

    # Store price list
    products_qs = (
        ProductPrice.objects
        .filter(supermarket=supermarket)
        .select_related("product")
        .order_by("product__name")
    )

    # Preload ALL snapshots once
    snapshots = (
        CompetitorPriceSnapshot.objects
        .filter(product__in=[p.product for p in products_qs])
        .select_related("competitor", "product")
        .order_by("-scraped_at")
    )

    # Group snapshots by product
    snaps_by_product = {}
    for s in snapshots:
        snaps_by_product.setdefault(s.product.barcode, []).append(s)

    analysis = []

    for price_row in products_qs:
        product = price_row.product
        snaps = snaps_by_product.get(product.barcode, [])

        latest_per_competitor = {}

        # keep FIRST snapshot per competitor_id
        for s in snaps:
            latest_per_competitor[s.competitor_id] = s

        competitor_prices = []
        competitor_details = []

        for s in latest_per_competitor.values():
            competitor_prices.append(s.price)
            competitor_details.append({
                "name": s.competitor.name,
                "price": s.price,
                "url": s.product_url,
                "time": s.scraped_at,
            })

        # Stats
        min_price = min(competitor_prices) if competitor_prices else None
        avg_price = (
            sum(competitor_prices) / len(competitor_prices)
            if competitor_prices else None
        )

        store_price = price_row.price
        diff = None
        status = "No Data"

        if store_price and min_price:
            diff = store_price - min_price

            if store_price <= min_price:
                status = "Best Price"
            elif store_price <= avg_price:
                status = "Competitive"
            else:
                status = "Overpriced"

        analysis.append({
            "product": product,
            "store_price": store_price,
            "competitors": competitor_details,
            "stats": {
                "min_price": min_price,
                "avg_price": avg_price,
            },
            "status": status,
            "difference": diff,
        })

    return render(request, "competitor/compare_all.html", {
        "supermarket": supermarket,
        "analysis": analysis,
    })


@login_required
def price_trend_data(request):
    """
    Returns:
    - date
    - min competitor price that day
    - avg competitor price

    Returned format:
    {
        "points": [
            {"date": "2025-01-01", "min_price": 2.49, "avg_price": 2.99},
            ...
        ]
    }
    """
    barcode = request.GET.get("barcode")

    if not barcode:
        return JsonResponse({"points": []})

    product = get_object_or_404(Product, pk=barcode)

    qs = (
        CompetitorPriceSnapshot.objects
        .filter(product=product)
        .annotate(date=TruncDate("scraped_at"))
        .values("date")
        .annotate(
            min_price=Min("price"),
            avg_price=Avg("price"),
        )
        .order_by("date")
    )

    points = [
        {
            "date": row["date"].isoformat(),
            "min_price": float(row["min_price"]),
            "avg_price": float(row["avg_price"]),
        }
        for row in qs
    ]

    return JsonResponse({"points": points})

# @login_required
# def refresh_price(request, product_id):
#     """
#     Background job to scrape competitor prices for ONE product.
#     Product PK = barcode string.
#     """
#     scrape_product_competitors_task.delay(product_id)
#
#     messages.success(
#         request,
#         f"Refreshing competitor prices for: {product_id}"
#     )
#
#     return redirect(request.META.get("HTTP_REFERER", "/"))
from competitor.tasks import scrape_product_competitors_task

@login_required
def refresh_price(request, product_id):
    scrape_product_competitors_task.delay(product_id)
    messages.success(request, f"Scraping started: {product_id}")
    return redirect(request.META.get("HTTP_REFERER", "/"))
