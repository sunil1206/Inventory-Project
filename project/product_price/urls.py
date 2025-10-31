from django.contrib import admin
from django.urls import path, include
from .views import dashboard_competitor_api,dashboard_competitor_api
from . import views
app_name = 'product_pricing'
urlpatterns = [
    path('api/supermarket/<int:supermarket_id>/financial-kpis/', views.dashboard_financial_kpi_api,
         name='dashboard_financial_kpi_api'),
    path('api/supermarket/<int:supermarket_id>/competitor-watch/', views.dashboard_competitor_api,
         name='dashboard_competitor_api'),
path('api/supermarket/<int:supermarket_id>/urgent-items/', views.urgent_items_api, name='urgent_items_api'),
path('api/supermarket/<int:supermarket_id>/stats/', views.dashboard_stats_api, name='dashboard_stats_api'),

path('supermarket/<int:supermarket_id>/manage-prices/', views.manage_product_prices_view, name='manage_product_prices'),
path(
        '<int:supermarket_id>/manage-prices/',
        views.manage_product_prices_view,
        name='product_price_list'  # <-- This name must match the one in your template
    ),
path(
        '<int:supermarket_id>/manage-prices/<str:product_barcode>/update/',
        views.update_product_defaults_view,
        name='update_product_defaults'
    ),
]

