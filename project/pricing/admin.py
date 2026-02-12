from django.contrib import admin

# Register your models here.
from pricing.models import CompetitorPrice, WastageRecord, DiscountedSale

import csv
from django.http import HttpResponse
from django.contrib import admin


def export_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=export.csv'

    writer = csv.writer(response)

    # Get field names
    fields = [field.name for field in modeladmin.model._meta.fields]
    writer.writerow(fields)

    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in fields])

    return response

export_as_csv.short_description = "Download selected records as CSV"


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


@admin.register(DiscountedSale)
class DiscountedSaleAdmin(admin.ModelAdmin):
    list_display = (
    'product', 'supermarket', 'quantity_sold', 'original_price', 'final_price', 'date_sold', 'triggering_rule',
    'promotion')
    list_filter = ('date_sold', 'supermarket', 'category', 'triggering_rule', 'promotion')
    search_fields = ('product__name', 'supermarket__name')
    date_hierarchy = 'date_sold'

    actions = [export_as_csv]

    # Make this model read-only in the admin, as it's a log file
    # def has_add_permission(self, request):
    #     return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WastageRecord)
class WastageRecordAdmin(admin.ModelAdmin):
    list_display = ('product', 'supermarket', 'quantity_wasted', 'expiry_date', 'date_removed')
    list_filter = ('date_removed', 'supermarket', 'category')
    search_fields = ('product__name', 'supermarket__name')
    date_hierarchy = 'date_removed'

    actions = [export_as_csv]

    # Make this model read-only in the admin
    def has_add_permission(self, request):
        return False

    # def has_change_permission(self, request, obj=None):
    #     return False
