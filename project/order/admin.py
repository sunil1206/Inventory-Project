# packaging/admin.py
from django.contrib import admin
from .models import ProductPackaging, OrderBatch, OrderLine

@admin.register(ProductPackaging)
class ProductPackagingAdmin(admin.ModelAdmin):
    list_display = ("product", "unit_barcode", "carton_barcode", "units_per_carton", "supplier", "is_active")
    list_filter = ("is_active", "supplier")
    search_fields = ("product__name", "unit_barcode", "carton_barcode")
    ordering = ("product__name",)

    readonly_fields = ("created_at",)


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    readonly_fields = ("product", "unit_barcode", "packaging", "cartons")


@admin.register(OrderBatch)
class OrderBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "supermarket", "supplier", "created_by", "status", "created_at")
    list_filter = ("status", "supplier", "supermarket")
    search_fields = ("reference",)
    ordering = ("-created_at",)
    inlines = [OrderLineInline]

    readonly_fields = ("created_at", "updated_at")


@admin.register(OrderLine)
class OrderLineAdmin(admin.ModelAdmin):
    list_display = ("product", "unit_barcode", "carton_barcode", "cartons", "units_per_carton", "batch")
    search_fields = ("product__name", "unit_barcode", "carton_barcode")


