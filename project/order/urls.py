# packaging/urls.py
from django.urls import path
from . import views

app_name = "packaging"

urlpatterns = [
    # Packaging mapping (CU → DU)
    path(
        "<int:supermarket_id>/scan/unit/",
        views.scan_unit_view,
        name="scan_unit",
    ),
    path(
        "api/check-unit/",
        views.check_unit_api,
        name="check_unit_api",
    ),
    path(
        "<int:supermarket_id>/scan/carton/<str:unit_barcode>/",
        views.scan_carton_view,
        name="scan_carton",
    ),
    path(
        "api/save-carton/",
        views.save_carton_api,
        name="save_carton_api",
    ),

    # Order builder
    path(
        "<int:supermarket_id>/order-builder/",
        views.order_builder_view,
        name="order_builder",
    ),
    path(
        "<int:supermarket_id>/order/reset/",
        views.reset_order_batch_view,
        name="reset_order_batch",
    ),
    path(
        "<int:supermarket_id>/order/line/<int:line_id>/update/",
        views.update_order_line,
        name="update_order_line",
    ),
    path(
        "<int:supermarket_id>/order/line/<int:line_id>/delete/",
        views.delete_order_line,
        name="delete_order_line",
    ),
    path(
        "<int:supermarket_id>/order/add-scanned/",
        views.add_scanned_item,
        name="add_scanned_item",
    ),
]
