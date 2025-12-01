from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [

    # =======================
    # MAIN DASHBOARD
    # =======================
    path("<int:supermarket_id>/",
         views.dashboard,
         name="dashboard"),

    # =======================
    # SALES & REVENUE
    # =======================
    path("<int:supermarket_id>/sales/",
         views.sales_detail,
         name="sales_detail"),

    # =======================
    # EXPIRY ANALYTICS
    # =======================
    path("<int:supermarket_id>/expiry/",
         views.expiry_detail,
         name="expiry_detail"),

    # =======================
    # COMPETITOR PRICING
    # =======================
    path("<int:supermarket_id>/competitors/",
         views.competitor_detail,
         name="competitor_detail"),

    # =======================
    # PRICING HEALTH
    # =======================
    path("<int:supermarket_id>/pricing/",
         views.pricing_detail,
         name="pricing_detail"),

    # =======================
    # RACK HEATMAP
    # =======================
    path("<int:supermarket_id>/racks/",
         views.rack_heatmap,
         name="rack_heatmap"),

    # =======================
    # SUPPLIER PERFORMANCE
    # =======================
    path("<int:supermarket_id>/suppliers/",
         views.supplier_performance,
         name="supplier_performance"),

    # =======================
    # PACKAGING ANALYTICS
    # =======================
    path("<int:supermarket_id>/packaging/",
         views.packaging_analytics,
         name="packaging_analytics"),
]
