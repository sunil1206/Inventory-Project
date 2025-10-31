from django.contrib import admin
from django.urls import path, include

from pricing import views
app_name = 'pricing'
urlpatterns = [

path('supermarket/<int:supermarket_id>/alerts/', views.alert_monitor_view, name='alert_monitor'),
    path('supermarket/<int:supermarket_id>/strategy/', views.pricing_strategy_view, name='pricing_strategy'),

# --- ✅ ADD THESE ---
    # Edit Pricing Rule
    path('supermarket/<int:supermarket_id>/rule/<int:rule_id>/edit/', views.pricing_rule_edit_view, name='pricing_rule_edit'),
    # Delete Pricing Rule
    path('supermarket/<int:supermarket_id>/rule/<int:rule_id>/delete/', views.pricing_rule_delete_view, name='pricing_rule_delete'),
    # --- END ADD ---

    path('supermarket/<int:supermarket_id>/promotions/', views.promotion_list_view, name='promotion_list'),
path('supermarket/<int:supermarket_id>/item/<int:item_id>/apply-discount/', views.apply_discount_view, name='apply_discount'),
    # path('<int:supermarket_id>/item/<int:item_id>/wastage/', views.mark_item_wastage, name='mark_item_wastage'),
path('<int:supermarket_id>/item/<int:item_id>/sell/', views.mark_item_sold, name='mark_item_sold'),

    path('supermarket/<int:supermarket_id>/inventory/item/<int:item_id>/delete/', views.delete_inventory_item_from_alert,
         name='delete_inventory_item'),

    path('supermarket/<int:supermarket_id>/item/<int:item_id>/apply-discount/',
         views.apply_specific_discount_view,
         name='apply_specific_discount'),
path('api/supermarket/<int:supermarket_id>/available-discounts/', views.get_available_discounts_api, name='get_available_discounts_api'),
    path('supermarket/<int:supermarket_id>/item/<int:item_id>/waste/', views.remove_as_wastage_view,
         name='remove_as_wastage'),
    path('<int:supermarket_id>/item/<int:item_id>/wastage/', views.mark_item_wastage, name='mark_item_wastage'),

]

