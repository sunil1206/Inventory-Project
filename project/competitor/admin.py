from django.contrib import admin
from .models import Competitor, CompetitorPriceSnapshot


from django.contrib import admin
from .models import Competitor, CompetitorPriceSnapshot


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'scrape_method',
        'is_active',
        'search_url_template',
    )

    search_fields = (
        'name',
        'scrape_method',
    )

    list_filter = (
        'scrape_method',
        'is_active',
    )

    fieldsets = (
        (None, {
            'fields': ('name', 'is_active')
        }),
        ('Scraping Configuration', {
            'fields': (
                'scrape_method',
                'search_url_template',
                'price_selector',
            ),
            'description': (
                "Use {barcode} as a placeholder in the URL.<br>"
                "<b>Example:</b> https://site.com/search?q={barcode}"
            ),
        }),
    )


from django.contrib import admin
from .models import CompetitorPriceSnapshot


@admin.register(CompetitorPriceSnapshot)
class CompetitorPriceSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'competitor',
        'price',
        'scraped_at',
        'product_url',
    )

    list_filter = (
        'competitor',
        'scraped_at',
    )

    search_fields = (
        'product__name',
        'product__barcode',
        'competitor__name',
    )

    readonly_fields = (
        'scraped_at',
    )

    ordering = ('-scraped_at',)

    date_hierarchy = 'scraped_at'

