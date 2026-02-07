from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from Inventory.models import InventoryItem, Supermarket

from collections import defaultdict
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from Inventory.models import Supermarket, InventoryItem

from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

def ai_expiry_recommendations(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, id=supermarket_id)
    today = timezone.localdate()

    # 1️⃣ Fetch inventory from ALL supermarkets
    items = InventoryItem.objects.select_related(
        "product", "supermarket"
    ).filter(expiry_date__isnull=False)

    grouped = defaultdict(list)

    # 2️⃣ Group by global batch signature
    for item in items:
        key = (item.product.barcode.strip(), item.expiry_date)
        grouped[key].append(item)

    recommendations = []

    for (barcode, expiry_date), group_items in grouped.items():

        days_left = (expiry_date - today).days

        # ⛔ Performance-safe cutoff
        if days_left > 30:
            continue

        # 3️⃣ Time-based expiry risk
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

        # 4️⃣ Cross-store validation strength
        store_ids = set(i.supermarket_id for i in group_items)
        store_count = len(store_ids)
        support_score = min(1.0, store_count / 3)

        # 5️⃣ AI confidence score
        ai_score = round((0.7 * time_risk + 0.3 * support_score), 2)

        if ai_score < 0.3:
            continue

        sample = group_items[0]

        # ✅ Key AI distinction
        observed_locally = supermarket.id in store_ids

        recommendations.append({
            "product": sample.product,
            "barcode": barcode,
            "expiry_date": expiry_date,
            "expiry_date_str": expiry_date.strftime("%d-%m-%Y"),
            "days_left": days_left,
            "ai_score": ai_score,
            "confidence": int(ai_score * 100),
            "store_count": store_count,
            "observed_locally": observed_locally,  # ⭐ IMPORTANT
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
