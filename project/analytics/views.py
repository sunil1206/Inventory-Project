from datetime import timedelta
import json

from django.contrib.auth.decorators import login_required
from django.db.models import (
    Sum, Count, F, Avg, Q,
    DecimalField, ExpressionWrapper
)
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

# Inventory models
from Inventory.models import (
    InventoryItem,
    ProductPrice,
    Supermarket,
    Rack,
)

# Pricing models
from pricing.models import DiscountedSale, WastageRecord, Promotion, PricingRule

# Competitor models
from competitor.models import CompetitorPriceSnapshot

# Order models
from order.models import OrderBatch, OrderLine


# ✅ Helper expression for revenue calculation
REVENUE_EXPR = ExpressionWrapper(
    F("final_price") * F("quantity_sold"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)



from django.db.models.functions import TruncDate


# ✅ Revenue expression (price × quantity)
REVENUE_EXPR = ExpressionWrapper(
    F("final_price") * F("quantity_sold"),
    output_field=DecimalField(max_digits=14, decimal_places=2)
)


@login_required
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
    # SALES
    # ============================
    sales = DiscountedSale.objects.filter(supermarket=supermarket)

    total_revenue = sales.aggregate(total=Sum(REVENUE_EXPR))["total"] or 0
    total_units_sold = sales.aggregate(total=Sum("quantity_sold"))["total"] or 0

    # ============================
    # SALES TREND (30 DAYS)
    # ============================
    trend_raw = (
        sales.filter(date_sold__date__gte=today - timedelta(days=30))
        .values("date_sold__date")
        .annotate(total=Sum(REVENUE_EXPR))
        .order_by("date_sold__date")
    )

    trend_labels = [r["date_sold__date"].strftime("%d %b") for r in trend_raw]
    trend_values = [float(r["total"] or 0) for r in trend_raw]

    sales_trend = {"labels": trend_labels, "values": trend_values}

    # ============================
    # WASTAGE ANALYTICS
    # ============================
    wastage = WastageRecord.objects.filter(supermarket=supermarket)

    total_wastage_loss = wastage.aggregate(
        loss=Sum(F("original_store_price") * F("quantity_wasted"))
    )["loss"] or 0

    # Wastage by category
    wastage_cat_raw = (
        wastage.values("category__name")
            .annotate(
            loss=Sum(F("original_store_price") * F("quantity_wasted"))
        )
            .order_by("-loss")
    )

    wastage_cat_labels = [
        w["category__name"] or "Uncategorized" for w in wastage_cat_raw
    ]
    wastage_cat_values = [
        float(w["loss"] or 0) for w in wastage_cat_raw
    ]

    # ============================
    # DISCOUNT VS FULL PRICE SALES
    # ============================
    discount_split = sales.aggregate(
        discounted_units=Sum(
            "quantity_sold",
            filter=Q(triggering_rule__isnull=False) | Q(promotion__isnull=False)
        ),
        fullprice_units=Sum(
            "quantity_sold",
            filter=Q(triggering_rule__isnull=True) & Q(promotion__isnull=True)
        ),
    )

    discount_split_values = [
        discount_split["fullprice_units"] or 0,
        discount_split["discounted_units"] or 0,
    ]

    sales_vs_wastage = [
        float(total_revenue),
        float(total_wastage_loss),
    ]

    # ============================
    # REVENUE BY CATEGORY
    # ============================
    revenue_cat_raw = (
        sales.values("category__name")
        .annotate(total=Sum(REVENUE_EXPR))
        .order_by("-total")
    )

    cat_labels = [r["category__name"] or "Uncategorized" for r in revenue_cat_raw]
    cat_values = [float(r["total"] or 0) for r in revenue_cat_raw]

    # ============================
    # SUPPLIERS
    # ============================
    supplier_raw = (
        OrderBatch.objects.filter(supermarket=supermarket)
        .values("supplier__name")
        .annotate(cartons=Sum("lines__cartons"))
        .order_by("-cartons")
    )

    supplier_labels = [s["supplier__name"] or "Unknown" for s in supplier_raw]
    supplier_values = [s["cartons"] or 0 for s in supplier_raw]

    # ============================
    # RACK LOAD
    # ============================
    rack_raw = (
        items.filter(rack__isnull=False)
        .values("rack__name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")
    )

    rack_labels = [r["rack__name"] or "No Rack" for r in rack_raw]
    rack_values = [r["qty"] or 0 for r in rack_raw]

    # ============================
    # COMPETITOR LOG
    # ============================
    competitor_records = (
        CompetitorPriceSnapshot.objects
        .select_related("product", "competitor")
        .order_by("-scraped_at")[:12]
    )

    # ============================
    # PRICING RULES
    # ============================
    active_rules = PricingRule.objects.filter(supermarket=supermarket, is_active=True).count()
    rule_impacts = sales.filter(triggering_rule__isnull=False).count()

    rule_raw = (
        PricingRule.objects.filter(supermarket=supermarket, is_active=True)
        .values("rule_type")
        .annotate(count=Count("id"))
    )

    rule_labels = [r["rule_type"] for r in rule_raw]
    rule_values = [r["count"] for r in rule_raw]

    # ============================
    # PROMOTIONS
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
    # AVG DISCOUNT
    # ============================
    discounted = (
        sales.exclude(original_price__isnull=True)
        .annotate(
            disc=((F("original_price") - F("final_price")) / F("original_price") * 100)
        )
    )
    avg_discount = round(discounted.aggregate(avg=Avg("disc"))["avg"] or 0, 2)

    # ============================
    # DISCOUNT IMPACT
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
        "total_units_sold": total_units_sold,
        "active_rules": active_rules,
        "active_promos": active_promos,
        "rule_impacts": rule_impacts,
        "promo_hits": promo_hits,
        "avg_discount": avg_discount,

        # Records
        "competitor_records": competitor_records,

        # Charts
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
        "total_wastage_loss": round(float(total_wastage_loss), 2),

        "wastage_cat_labels": json.dumps(wastage_cat_labels),
        "wastage_cat_values": json.dumps(wastage_cat_values),

        "discount_split_labels": json.dumps(
            ["Full Price Sales", "Discounted Sales"]
        ),
        "discount_split_values": json.dumps(discount_split_values),

        "sales_vs_wastage": json.dumps(sales_vs_wastage),
    }



    return render(request, "analytics/dashboard.html", context)



@login_required
def sales_detail(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    rows = (
        DiscountedSale.objects.filter(supermarket=supermarket)
        .values("category__name")
        .annotate(
            qty=Sum("quantity_sold"),
            revenue=Sum(REVENUE_EXPR)   # ✅ FIXED
        )
        .order_by("-revenue")
    )

    return render(request, "analytics/sales_detail.html", {
        "supermarket": supermarket,
        "rows": rows,
    })


@login_required
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


@login_required
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


@login_required
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


@login_required
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


@login_required
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


@login_required
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
