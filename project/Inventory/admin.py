from django.contrib import admin
from .models import Supermarket, Category, Product, InventoryItem


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


from django.contrib import admin
from .models import ProductPrice


@admin.register(ProductPrice)
class ProductPriceAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ProductPrice (Price List) model.
    """

    # --- List View ---
    # Customize what's shown in the main admin list
    list_display = (
        'product',
        'supermarket',
        'price',
        'last_updated'
    )

    # --- Editing ---
    # Allow editing the price directly from the list view
    list_editable = ('price',)

    # --- Filtering & Searching ---
    # Add a filter sidebar. Filtering by supermarket is most useful.
    list_filter = ('supermarket',)

    # Enable searching by product name or supermarket name
    search_fields = ('product__name', 'supermarket__name')

    # --- Form View ---
    # Fields to display when editing a single entry
    fields = (
        'supermarket',
        'product',
        'price',
        'last_updated'
    )

    # Make 'last_updated' read-only, as it's set automatically
    readonly_fields = ('last_updated',)

    # --- Performance Optimization ---
    # For large numbers of products or supermarkets,
    # this replaces slow dropdowns with a search-based lookup widget.
    raw_id_fields = ('product', 'supermarket')

    # Set default ordering
    ordering = ('product__name', 'supermarket__name')