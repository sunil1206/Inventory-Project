from datetime import timedelta
from django.db.models import Sum, Count, F, Avg
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import json
from django.db.models import Q

# Corrected Imports based on project structure
from Inventory.models import (
    InventoryItem,
    ProductPrice,
    Supermarket,
    Rack,
)
# Assuming these models exist in these apps based on your provided code
# If they are in 'inventory', change 'pricing' or 'order' to 'inventory'
from pricing.models import DiscountedSale, WastageRecord, Promotion, PricingRule
# from Inventory import WastageRecord  # WastageRecord was previously in inventory
from competitor.models import CompetitorPriceSnapshot
from order.models import OrderBatch, OrderLine
def dashboard(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)
    today = timezone.now().date()

    # ============================
    # INVENTORY STATS
    # ============================
    items = InventoryItem.objects.filter(supermarket=supermarket)
    total_items = items.count()

    expired = items.filter(expiry_date__lt=today).count()
    expiring = items.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=7)
    ).count()
    fresh = max(total_items - expired - expiring, 0)

    # ============================
    # SALES — REVENUE
    # ============================
    sales = DiscountedSale.objects.filter(supermarket=supermarket)
    total_revenue = (
        sales.aggregate(total=Sum("final_price"))["total"] or 0
    )

    # Revenue by category
    revenue_cat_raw = (
        sales.values("category__name")
        .annotate(total=Sum("final_price"))
        .order_by("-total")
    )
    cat_labels = []
    cat_values = []
    for r in revenue_cat_raw:
        cat_labels.append(r["category__name"] or "Uncategorized")
        cat_values.append(float(r["total"]))

    # ============================
    # SALES TREND (30 days)
    # ============================
    trend_raw = (
        sales.filter(date_sold__date__gte=today - timedelta(days=30))
        .values("date_sold__date")
        .annotate(total=Sum("final_price"))
        .order_by("date_sold__date")
    )
    trend_labels, trend_values = [], []
    for r in trend_raw:
        trend_labels.append(r["date_sold__date"].strftime("%d %b"))
        trend_values.append(float(r["total"]))
    sales_trend = {"labels": trend_labels, "values": trend_values}

    # ============================
    # SUPPLIERS
    # ============================
    supplier_raw = (
        OrderBatch.objects.filter(supermarket=supermarket)
        .values("supplier__name")
        .annotate(cartons=Sum("lines__cartons"))
        .order_by("-cartons")
    )
    supplier_labels = []
    supplier_values = []
    for s in supplier_raw:
        supplier_labels.append(s["supplier__name"])
        supplier_values.append(s["cartons"] or 0)

    # ============================
    # RACK LOAD
    # ============================
    rack_raw = (
        items.filter(rack__isnull=False)
        .values("rack__name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")
    )
    rack_labels = []
    rack_values = []
    for r in rack_raw:
        rack_labels.append(r["rack__name"])
        rack_values.append(r["qty"])

    # ============================
    # COMPETITOR LOG
    # ============================
    competitor_records = (
        CompetitorPriceSnapshot.objects
        .select_related("product", "competitor")
        .order_by("-scraped_at")[:12]
    )

    # ============================
    # PRICING RULES KPI
    # ============================
    active_rules = PricingRule.objects.filter(supermarket=supermarket, is_active=True).count()
    rule_impacts = sales.filter(triggering_rule__isnull=False).count()

    # Rule breakdown
    rule_raw = (
        PricingRule.objects.filter(supermarket=supermarket, is_active=True)
        .values("rule_type")
        .annotate(count=Count("id"))
    )
    rule_labels = [r["rule_type"] for r in rule_raw]
    rule_values = [r["count"] for r in rule_raw]

    # ============================
    # PROMOTIONS KPI
    # ============================
    active_promos = Promotion.objects.filter(supermarket=supermarket, is_active=True).count()
    promo_hits = sales.filter(promotion__isnull=False).count()

    promo_raw = (
        Promotion.objects.filter(supermarket=supermarket, is_active=True)
        .values("discount_type")
        .annotate(count=Count("id"))
    )
    promo_labels = [p["discount_type"] for p in promo_raw]
    promo_values = [p["count"] for p in promo_raw]

    # ============================
    # AVERAGE DISCOUNT STRENGTH
    # ============================
    # (orig - final) / orig * 100
    discounted = (
        sales.exclude(original_price__isnull=True)
        .annotate(
            disc=((F("original_price") - F("final_price")) / F("original_price") * 100)
        )
    )
    avg_discount = round(discounted.aggregate(avg=Avg("disc"))["avg"] or 0, 2)

    # ============================
    # SALES IMPACT (Stacked)
    # ============================
    impact_data = sales.aggregate(
        regular=Count("id", filter=Q(triggering_rule__isnull=True) & Q(promotion__isnull=True)),
        rule=Count("id", filter=Q(triggering_rule__isnull=False)),
        promo=Count("id", filter=Q(promotion__isnull=False)),
    )
    impact_labels = ["No Discount", "Rule-Based", "Promotion"]
    impact_values = [
        impact_data["regular"],
        impact_data["rule"],
        impact_data["promo"],
    ]

    # ============================
    # CONTEXT
    # ============================
    context = {
        "supermarket": supermarket,

        # KPI
        "expired": expired,
        "expiring": expiring,
        "fresh": fresh,
        "total_revenue": total_revenue,
        "active_rules": active_rules,
        "active_promos": active_promos,
        "rule_impacts": rule_impacts,
        "promo_hits": promo_hits,
        "avg_discount": avg_discount,

        # Records
        "competitor_records": competitor_records,

        # Charts JSON
        "expiry_data": json.dumps([expired, expiring, fresh]),
        "cat_labels": json.dumps(cat_labels),
        "cat_values": json.dumps(cat_values),
        "sales_trend": json.dumps(sales_trend),
        "supplier_labels": json.dumps(supplier_labels),
        "supplier_values": json.dumps(supplier_values),
        "rack_labels": json.dumps(rack_labels),
        "rack_values": json.dumps(rack_values),

        "rule_labels": json.dumps(rule_labels),
        "rule_values": json.dumps(rule_values),
        "promo_labels": json.dumps(promo_labels),
        "promo_values": json.dumps(promo_values),

        "impact_labels": json.dumps(impact_labels),
        "impact_values": json.dumps(impact_values),
    }

    return render(request, "analytics/dashboard.html", context)
def sales_detail(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    rows = (
        DiscountedSale.objects.filter(supermarket=supermarket)
        .values("category__name")
        .annotate(
            qty=Sum("quantity_sold"),
            revenue=Sum("final_price")
        )
        .order_by("-revenue")
    )
    return render(request, "analytics/sales_detail.html", {
        "supermarket": supermarket,
        "rows": rows,
    })
def expiry_detail(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)
    today = timezone.now().date()

    items = InventoryItem.objects.filter(supermarket=supermarket)

    stats = {
        "expired": items.filter(expiry_date__lt=today).count(),
        "expiring": items.filter(
            expiry_date__lte=today + timedelta(days=7),
            expiry_date__gte=today
        ).count(),
        "fresh": items.filter(expiry_date__gt=today + timedelta(days=7)).count(),
    }
    return render(request, "analytics/expiry_detail.html", {
        "supermarket": supermarket,
        "stats": stats,
    })


def competitor_detail(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    logs = (
        CompetitorPriceSnapshot.objects
        .select_related("product", "competitor")
        .order_by("-scraped_at")
    )

    return render(request, "analytics/competitor_detail.html", {
        "supermarket": supermarket,
        "logs": logs,
    })


def pricing_detail(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    prices = ProductPrice.objects.filter(supermarket=supermarket)
    rules = PricingRule.objects.filter(supermarket=supermarket)
    promos = Promotion.objects.filter(supermarket=supermarket)

    return render(request, "analytics/pricing_detail.html", {
        "supermarket": supermarket,
        "prices": prices,
        "rules": rules,
        "promotions": promos,
    })


def rack_heatmap(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    data = (
        InventoryItem.objects.filter(supermarket=supermarket)
        .values("rack__name")
        .annotate(qty=Sum("quantity"), avg_expiry=Avg("expiry_date"))
        .order_by("-qty")
    )
    return render(request, "analytics/rack_heatmap.html", {
        "supermarket": supermarket,
        "rows": data,
    })


def supplier_performance(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    rows = (
        OrderBatch.objects.filter(supermarket=supermarket)
        .values("supplier__name")
        .annotate(
            orders=Count("id"),
            cartons=Sum("lines__cartons")
        )
        .order_by("-cartons")
    )

    return render(request, "analytics/supplier_performance.html", {
        "supermarket": supermarket,
        "rows": rows,
    })

def packaging_analytics(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    lines = (
        OrderLine.objects.filter(batch__supermarket=supermarket)
        .annotate(total_units=F("cartons") * F("packaging__units_per_carton"))
    )

    rows = (
        lines.values("product__name")
        .annotate(
            cartons=Sum("cartons"),
            units=Sum("total_units")
        )
        .order_by("-units")
    )

    return render(request, "analytics/packaging_analytics.html", {
        "supermarket": supermarket,
        "rows": rows,
    })
