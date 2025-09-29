from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # --- Page Rendering URLs ---
    path('', views.home_view, name='home'),
    # path('home/', views.home_view, name='home'),
    path('supermarket/<int:supermarket_id>/', views.supermarket_dashboard_view, name='supermarket_dashboard'),
    path('supermarket/<int:supermarket_id>/scan/', views.scan_item_page_view, name='scan_item'),
    path('supermarket/<int:supermarket_id>/inventory/', views.inventory_list_view, name='inventory_list'),
    path('supermarket/<int:supermarket_id>/alerts/', views.alert_monitor_view, name='alert_monitor'),
    path('supermarket/<int:supermarket_id>/pricing/', views.competitive_price_view, name='competitive_pricing'),

    path('inventory/<int:supermarket_id>/item/<int:item_id>/edit/', views.edit_inventory_item, name='edit_inventory_item'),
    path('inventory/<int:supermarket_id>/item/<int:item_id>/delete/', views.delete_inventory_item, name='delete_inventory_item'),
    path('inventory/<int:supermarket_id>/export/', views.export_inventory_csv, name='export_inventory_csv'),

# Product Catalog & CRUD
    path('products/<int:supermarket_id>/', views.product_list_view, name='product_list'),
    path('products/<int:supermarket_id>/new/', views.create_product_view, name='create_product'),
    path('products/<int:supermarket_id>/<str:product_barcode>/', views.product_detail_view, name='product_detail'),
    path('products/<int:supermarket_id>/<str:product_barcode>/edit/', views.edit_product_view, name='edit_product'),
    path('products/<int:supermarket_id>/<str:product_barcode>/delete/', views.delete_product_view, name='delete_product'),
    path('products/<int:supermarket_id>/<str:product_barcode>/add-to-inventory/', views.add_inventory_from_product_list, name='add_from_product_list'),



    # --- NEW MANAGEMENT URLs ---
    path('supermarket/<int:supermarket_id>/staff/', views.staff_management_view, name='staff_management'),
    path('supermarket/<int:supermarket_id>/suppliers/', views.supplier_list_view, name='supplier_list'),
    path('supermarket/<int:supermarket_id>/strategy/', views.pricing_strategy_view, name='pricing_strategy'),
    path('supermarket/<int:supermarket_id>/promotions/', views.promotion_list_view, name='promotion_list'),

    # URL for deleting an item
    path('supermarket/<int:supermarket_id>/inventory/delete/<int:item_id>/', views.delete_inventory_item,
         name='delete_item'),

    # --- API Endpoints ---
    path('api/supermarkets/', views.supermarket_list_api, name='supermarket_list_api'),
    path('api/supermarket/<int:supermarket_id>/stats/', views.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/supermarket/<int:supermarket_id>/urgent-items/', views.urgent_items_api, name='urgent_items_api'),
    path('api/scan/', views.scan_api, name='scan_api'),
    path('api/supermarket/<int:supermarket_id>/scrape-prices/<str:product_barcode>/', views.scrape_prices_api,
         name='scrape_prices_api'),

path('api/products/', views.product_search_api, name='product_search_api'),
]

