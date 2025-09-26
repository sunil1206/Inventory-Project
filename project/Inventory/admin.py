from django.contrib import admin
from .models import Supermarket, Category, Product, InventoryItem, CompetitorPrice


@admin.register(Supermarket)
class SupermarketAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Supermarket model.
    """
    list_display = ('name', 'owner', 'location', 'created_at')
    search_fields = ('name', 'owner__username', 'location')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Category model.
    """
    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin configuration for the central Product catalog.
    """
    list_display = ('barcode', 'name', 'brand', 'last_scraped')
    search_fields = ('barcode', 'name', 'brand')
    ordering = ('name',)
    readonly_fields = ('last_scraped',)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    """
    Admin configuration for the InventoryItem model.
    This is the most detailed view for day-to-day management.
    """
    list_display = ('product', 'supermarket', 'category', 'quantity', 'store_price', 'expiry_date', 'status')
    list_filter = ('supermarket', 'category', 'expiry_date')
    search_fields = ('product__barcode', 'product__name', 'supermarket__name')
    ordering = ('expiry_date',)

    # Use raw_id_fields for better performance on large datasets
    raw_id_fields = ('product', 'supermarket', 'category')

    # Add a field to display the calculated status property
    readonly_fields = ('status', 'added_at', 'last_updated')
    list_select_related = ('product', 'supermarket', 'category')


@admin.register(CompetitorPrice)
class CompetitorPriceAdmin(admin.ModelAdmin):
    """
    Admin configuration for the CompetitorPrice model.
    """
    list_display = ('product', 'competitor_name', 'price', 'scraped_at')
    list_filter = ('competitor_name', 'scraped_at')
    search_fields = ('product__name', 'competitor_name')
    ordering = ('-scraped_at',)
    raw_id_fields = ('product',)

