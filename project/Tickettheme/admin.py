# tickettheme/admin.py
from django.contrib import admin
from .models import TicketTheme, TicketLabel


@admin.register(TicketTheme)
class TicketThemeAdmin(admin.ModelAdmin):
    list_display = ("name", "supermarket", "width_mm", "height_mm", "match_product_color")


@admin.register(TicketLabel)
class TicketLabelAdmin(admin.ModelAdmin):
    list_display = ("product", "unit_price", "price_per_liter", "theme", "created_at")
    list_filter = ("supermarket",)
