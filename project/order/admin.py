# packaging/admin.py
from django.contrib import admin
from .models import ProductPackaging, OrderBatch, OrderLine


@admin.register(ProductPackaging)
class ProductPackagingAdmin(admin.ModelAdmin):
    list_display = ("product", "unit_barcode", "carton_barcode", "units_per_carton", "supplier")
    search_fields = ("product__name", "unit_barcode", "carton_barcode")


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0


@admin.register(OrderBatch)
class OrderBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "supermarket", "supplier", "created_by", "status", "created_at")
    list_filter = ("status", "supermarket", "supplier")
    inlines = [OrderLineInline]
