from django.contrib import admin
from .models import Competitor, CompetitorPriceSnapshot


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'search_url_template')
    search_fields = ('name',)
    list_filter = ('is_active',)

    fieldsets = (
        (None, {
            'fields': ('name', 'is_active')
        }),
        ('Scraping Configuration', {
            'fields': ('search_url_template', 'price_selector'),
            'description': "Use {barcode} as a placeholder in the URL. Example: https://site.com/search?q={barcode}"
        }),
    )


@admin.register(CompetitorPriceSnapshot)
class CompetitorPriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ('product', 'competitor', 'price', 'scraped_at')
    list_filter = ('competitor', 'scraped_at')
    search_fields = ('product__name', 'product__barcode')
    readonly_fields = ('scraped_at',)