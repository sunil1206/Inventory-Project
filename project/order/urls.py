# packaging/urls.py
from django.urls import path
from . import views

app_name = "packaging"

urlpatterns = [
    # Packaging mapping (unit → carton)
    path("scan/unit/", views.scan_unit_view, name="scan_unit"),
    path("api/check-unit/", views.check_unit_api, name="check_unit_api"),
    path("scan/carton/<str:unit_barcode>/", views.scan_carton_view, name="scan_carton"),
    path("api/save-carton/", views.save_carton_api, name="save_carton_api"),
path("order/<int:supermarket_id>/line/<int:line_id>/update/",
     views.update_order_line, name="update_order_line"),

path("order/<int:supermarket_id>/line/<int:line_id>/delete/",
     views.delete_order_line, name="delete_order_line"),

    # Order builder
    path("order/<int:supermarket_id>/", views.order_builder_view, name="order_builder"),
    path("order/<int:supermarket_id>/reset/", views.reset_order_batch_view, name="reset_order_batch"),
    path("order/<int:supermarket_id>/scan/", views.add_scanned_item, name="add_scanned_item"),
]
