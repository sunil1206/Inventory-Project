# expiry_ai/adapters.py
from django.contrib.auth import get_user_model

# ✅ CHANGE THIS to your real inventory model
# Example options you might have:
# from Inventory.models import InventoryItem
# from pricing.models import InventoryItem
from Inventory.models import InventoryItem  # <-- change if needed

User = get_user_model()

# Role weights (tune)
ROLE_WEIGHT = {
    "superadmin": 1.0,
    "manager": 0.7,
    "staff": 0.5,
}


def get_role_for_user(user: User | None) -> str:
    """
    Map your auth to superadmin/manager/staff.
    Adjust group checks if you have them.
    """
    if not user:
        return "staff"
    if user.is_superuser:
        return "superadmin"
    # if user.groups.filter(name="Manager").exists(): return "manager"
    return "staff"


def fetch_inventory_rows():
    """
    Must return iterable rows with:
      supermarket_id, barcode, product_name, expiry_date, created_by_id(optional)
    """
    # ✅ Adjust field names here if your schema differs
    return (
        InventoryItem.objects
        .select_related("supermarket", "product", "created_by")
        .values(
            "supermarket_id",
            "product__barcode",
            "product__name",
            "expiry_date",
            "created_by_id",
        )
    )


def fetch_store_inventory_signatures(supermarket_id: int):
    """
    Returns unique signatures present in a store inventory:
    (barcode, normalized_name, expiry_date)
    """
    # If your inventory table already stores barcode/name directly, change below accordingly.
    qs = (
        InventoryItem.objects
        .filter(supermarket_id=supermarket_id)
        .select_related("product")
        .values("product__barcode", "product__name", "expiry_date")
        .distinct()
    )
    return qs
