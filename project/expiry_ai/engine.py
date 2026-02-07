# expiry_ai/engine.py
from collections import defaultdict
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .adapters import fetch_inventory_rows, fetch_store_inventory_signatures, ROLE_WEIGHT, get_role_for_user
from .models import BatchSignature, StoreExpiryRecommendation
from .scoring import normalize_name, confidence_from_support, risk as risk_score, time_risk, level_from_confidence

User = get_user_model()


def recompute_batch_signatures(alpha: float = 0.8, chunk_size: int = 5000) -> int:
    """
    Builds/updates BatchSignature from inventory rows across ALL stores.

    Important logic:
    - For each store+signature: take MAX weight (avoid one store spamming)
    - Signature support_sum = sum(max_weight_per_store)
    - confidence = 1 - exp(-alpha*support_sum)
    """
    qs = fetch_inventory_rows()

    # Cache user roles
    role_cache: dict[int, str] = {}

    def weight_for_user_id(user_id: int | None) -> float:
        if not user_id:
            return ROLE_WEIGHT["staff"]
        if user_id in role_cache:
            return ROLE_WEIGHT[role_cache[user_id]]
        try:
            u = User.objects.only("id", "is_superuser").get(id=user_id)
        except User.DoesNotExist:
            role_cache[user_id] = "staff"
            return ROLE_WEIGHT["staff"]
        r = get_role_for_user(u)
        role_cache[user_id] = r
        return ROLE_WEIGHT.get(r, 0.5)

    store_sig_max = defaultdict(float)  # (store, barcode, name_norm, expiry) -> max_w

    for row in qs.iterator(chunk_size=chunk_size):
        store_id = row["supermarket_id"]
        barcode = str(row.get("product__barcode") or "").strip()
        name_raw = str(row.get("product__name") or "").strip()
        exp = row.get("expiry_date")

        if not store_id or not barcode or not exp:
            continue

        name_norm = normalize_name(name_raw)
        w = weight_for_user_id(row.get("created_by_id"))

        key = (store_id, barcode, name_norm, exp)
        if w > store_sig_max[key]:
            store_sig_max[key] = w

    sig_support_sum = defaultdict(float)  # (barcode, name_norm, exp) -> support_sum
    sig_store_count = defaultdict(set)    # -> distinct store ids

    for (store_id, barcode, name_norm, exp), w in store_sig_max.items():
        sig_key = (barcode, name_norm, exp)
        sig_support_sum[sig_key] += float(w)
        sig_store_count[sig_key].add(store_id)

    upserts = []
    for (barcode, name_norm, exp), support_sum in sig_support_sum.items():
        conf = confidence_from_support(support_sum, alpha=alpha)
        upserts.append((barcode, name_norm, exp, support_sum, len(sig_store_count[(barcode, name_norm, exp)]), conf))

    with transaction.atomic():
        for barcode, name_norm, exp, support_sum, store_count, conf in upserts:
            BatchSignature.objects.update_or_create(
                barcode=barcode,
                name_norm=name_norm,
                expiry_date=exp,
                defaults={
                    "support_sum": support_sum,
                    "distinct_store_count": store_count,
                    "confidence": conf,
                }
            )

    return len(upserts)


def recompute_store_recommendations(
    supermarket_id: int,
    horizon_days: int = 14,
    min_confidence: float = 0.50,
    min_risk: float = 0.35,
    max_rows: int = 500,
) -> int:
    """
    For one store:
    - Only recommend signatures that EXIST in that store inventory
    - Join with BatchSignature confidence
    - Compute risk and upsert StoreExpiryRecommendation
    """
    # 1) get store inventory signatures (barcode, name, expiry)
    store_qs = fetch_store_inventory_signatures(supermarket_id)

    keys = []
    for r in store_qs.iterator():
        barcode = str(r.get("product__barcode") or "").strip()
        name_raw = str(r.get("product__name") or "").strip()
        exp = r.get("expiry_date")
        if not barcode or not exp:
            continue
        keys.append((barcode, normalize_name(name_raw), exp))

    if not keys:
        StoreExpiryRecommendation.objects.filter(supermarket_id=supermarket_id).update(is_active=False, last_computed_at=timezone.now())
        return 0

    # 2) Fetch relevant BatchSignature rows efficiently
    # (We filter by barcode list + expiry window to reduce load)
    barcodes = list({k[0] for k in keys})
    expiries = list({k[2] for k in keys})

    bs_qs = BatchSignature.objects.filter(
        barcode__in=barcodes,
        expiry_date__in=expiries,
        confidence__gte=min_confidence,
    )

    bs_map = {(b.barcode, b.name_norm, b.expiry_date): b for b in bs_qs}

    updated = 0
    now = timezone.now()

    # Deactivate all first (then reactivate the ones that qualify)
    StoreExpiryRecommendation.objects.filter(supermarket_id=supermarket_id).update(is_active=False, last_computed_at=now)

    with transaction.atomic():
        for barcode, name_norm, exp in keys[:max_rows]:
            agg = bs_map.get((barcode, name_norm, exp))
            if not agg:
                continue

            tr = time_risk(exp, horizon_days=horizon_days)
            rs = float(agg.confidence) * float(tr)
            if rs < min_risk:
                continue

            StoreExpiryRecommendation.objects.update_or_create(
                supermarket_id=supermarket_id,
                barcode=barcode,
                name_norm=name_norm,
                expiry_date=exp,
                defaults={
                    "confidence": float(agg.confidence),
                    "time_risk": float(tr),
                    "risk": float(rs),
                    "level": level_from_confidence(float(agg.confidence)),
                    "store_confirmations": int(agg.distinct_store_count),
                    "is_active": True,
                    "last_computed_at": now,
                }
            )
            updated += 1

    return updated


def recompute_all_store_recommendations(horizon_days: int = 14, min_confidence: float = 0.50, min_risk: float = 0.35) -> int:
    """
    Recompute recommendations for ALL stores.
    """
    from Inventory.models import Supermarket  # local import

    total = 0
    for sid in Supermarket.objects.values_list("id", flat=True).iterator():
        total += recompute_store_recommendations(
            supermarket_id=sid,
            horizon_days=horizon_days,
            min_confidence=min_confidence,
            min_risk=min_risk,
        )
    return total
