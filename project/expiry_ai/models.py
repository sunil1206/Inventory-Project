from django.db import models

# Create your models here.
# expiry_ai/models.py
from django.db import models
from django.utils import timezone


class BatchSignature(models.Model):
    """
    One row per Batch Signature:
    (barcode + normalized_name + expiry_date)

    This is the network intelligence table.
    """
    barcode = models.CharField(max_length=64, db_index=True)
    name_norm = models.CharField(max_length=255, db_index=True)
    expiry_date = models.DateField(db_index=True)

    distinct_store_count = models.PositiveIntegerField(default=0)
    support_sum = models.FloatField(default=0.0)
    confidence = models.FloatField(default=0.0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("barcode", "name_norm", "expiry_date")
        indexes = [
            models.Index(fields=["expiry_date", "confidence"]),
            models.Index(fields=["barcode", "expiry_date"]),
        ]

    def __str__(self):
        return f"{self.barcode} exp={self.expiry_date} conf={self.confidence:.2f}"


class StoreExpiryRecommendation(models.Model):
    """
    Store-specific recommendations derived from BatchSignature.
    Only recommends products that exist in THAT store's inventory.
    """
    supermarket = models.ForeignKey("Inventory.Supermarket", on_delete=models.CASCADE, related_name="ai_expiry_recos")

    barcode = models.CharField(max_length=64, db_index=True)
    name_norm = models.CharField(max_length=255)
    expiry_date = models.DateField(db_index=True)

    confidence = models.FloatField(default=0.0)
    time_risk = models.FloatField(default=0.0)
    risk = models.FloatField(default=0.0)
    level = models.CharField(max_length=20, default="weak")  # weak / likely / confirmed

    # explainability
    store_confirmations = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    last_computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("supermarket", "barcode", "name_norm", "expiry_date")
        indexes = [
            models.Index(fields=["supermarket", "-risk", "expiry_date"]),
            models.Index(fields=["supermarket", "is_active", "expiry_date"]),
        ]

    def __str__(self):
        return f"Reco store={self.supermarket_id} {self.barcode} risk={self.risk:.2f}"
