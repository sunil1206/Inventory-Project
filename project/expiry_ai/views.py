from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from Inventory.models import InventoryItem, Supermarket

from collections import defaultdict
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from Inventory.models import Supermarket, InventoryItem


def ai_expiry_recommendations(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)
    today = timezone.localdate()

    # 1️⃣ Fetch inventory across ALL stores
    items = InventoryItem.objects.select_related(
        "product", "supermarket"
    ).filter(
        expiry_date__isnull=False
    )

    grouped = defaultdict(list)

    # 2️⃣ Group by (barcode + expiry_date)
    for item in items:
        key = (item.product.barcode.strip(), item.expiry_date)
        grouped[key].append(item)

    recommendations = []

    for (barcode, expiry_date), group_items in grouped.items():

        days_left = (expiry_date - today).days

        # ❌ Ignore far expiry (performance-safe)
        if days_left > 30:
            continue

        # 3️⃣ TIME RISK
        if days_left <= 0:
            time_risk = 1.0
        elif days_left <= 3:
            time_risk = 0.9
        elif days_left <= 7:
            time_risk = 0.7
        elif days_left <= 14:
            time_risk = 0.5
        else:
            time_risk = 0.3

        # 4️⃣ CROSS-STORE SUPPORT
        store_count = len(set(i.supermarket_id for i in group_items))
        support_score = min(1.0, store_count / 3)

        # 5️⃣ FINAL AI SCORE
        ai_score = round((0.7 * time_risk + 0.3 * support_score), 2)

        # ❗ Even ONE product must show
        if ai_score < 0.3:
            continue

        # 6️⃣ Show only if THIS supermarket has it
        if not any(i.supermarket_id == supermarket.id for i in group_items):
            continue

        sample = group_items[0]

        recommendations.append({
            "product": sample.product,
            "barcode": barcode,
            "expiry_date": expiry_date,                         # date object
            "expiry_date_str": expiry_date.strftime("%d-%m-%Y"),# ✅ STRING (FIX)
            "days_left": days_left,
            "ai_score": ai_score,
            "confidence": int(ai_score * 100),
            "store_count": store_count,
            "category_id": getattr(sample.product.category, "id", ""),
        })

    recommendations.sort(key=lambda x: x["ai_score"], reverse=True)

    return render(request, "expiry_ai/ai_recommendations.html", {
        "supermarket": supermarket,
        "ai_recommendations": recommendations,
    })


from django.shortcuts import render, get_object_or_404
from Inventory.models import Supermarket
from django.utils import timezone
from datetime import timedelta

def expired_products(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)

    expired_items = (
        supermarket.inventory_items
        .filter(expiry_date__lt=timezone.now().date())
        .select_related("product")
        .order_by("-expiry_date")
    )

    return render(
        request,
        "expiry_ai/expired.html",
        {
            "supermarket": supermarket,
            "expired_items": expired_items,
        }
    )
