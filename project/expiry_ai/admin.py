from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import BatchSignature, StoreExpiryRecommendation


@admin.register(BatchSignature)
class BatchSignatureAdmin(admin.ModelAdmin):
    list_display = ("barcode", "name_norm", "expiry_date", "confidence", "distinct_store_count", "updated_at")
    list_filter = ("expiry_date",)
    search_fields = ("barcode", "name_norm")


@admin.register(StoreExpiryRecommendation)
class StoreExpiryRecommendationAdmin(admin.ModelAdmin):
    list_display = ("supermarket", "barcode", "name_norm", "expiry_date", "risk", "confidence", "level", "is_active")
    list_filter = ("is_active", "level", "expiry_date")
    search_fields = ("barcode", "name_norm", "supermarket__name")
