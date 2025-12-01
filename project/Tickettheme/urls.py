from django.urls import path
from . import views

app_name = "ticket"

urlpatterns = [

    # List + manual barcode entry
    path("<int:supermarket_id>/", views.ticket_list_view, name="ticket_list"),

    # Manual ticket creation from product detail
    path("<int:supermarket_id>/create/<int:product_id>/", views.ticket_create_view, name="ticket_create"),

    # Delete ticket
    path("<int:supermarket_id>/delete/<int:ticket_id>/", views.ticket_delete_view, name="ticket_delete"),

    # API: scanner POST form (handheld USB)
    # path("<int:supermarket_id>/scan/", views.ticket_scan_api, name="ticket_scan_api"),

    # API: scanner mobile JSON
    # path("<int:supermarket_id>/scan/json/", views.scan_ticket_api, name="scan_ticket_api"),

    # PDF export (1 label per page)
    path("<int:supermarket_id>/pdf/", views.ticket_pdf_export, name="ticket_pdf_export"),

    # Bulk PDF (grid)
    # path("<int:supermarket_id>/sheet/<int:sheet_id>/", views.bulk_ticket_pdf, name="bulk_ticket_pdf"),

    # Label sheet layouts
    path("<int:supermarket_id>/sheets/", views.label_sheet_list_view, name="label_sheet_list"),
    path("<int:supermarket_id>/sheets/create/", views.label_sheet_create_view, name="label_sheet_create"),
    path("<int:supermarket_id>/sheets/<int:sheet_id>/edit/", views.label_sheet_edit_view, name="label_sheet_edit"),
    path("<int:supermarket_id>/sheets/<int:sheet_id>/delete/", views.label_sheet_delete_view, name="label_sheet_delete"),

    # Ticket themes
    path("<int:supermarket_id>/themes/", views.ticket_theme_list_view, name="ticket_theme_list"),
    path("<int:supermarket_id>/themes/create/", views.ticket_theme_create_view, name="ticket_theme_create"),
    path("<int:supermarket_id>/themes/<int:theme_id>/edit/", views.ticket_theme_edit_view, name="ticket_theme_edit"),
    path("<int:supermarket_id>/themes/<int:theme_id>/delete/", views.ticket_theme_delete_view, name="ticket_theme_delete"),


    path("<int:supermarket_id>/delete/<int:ticket_id>/", views.ticket_delete_view, name="ticket_delete"),
path("<int:supermarket_id>/scan-api/", views.scan_ticket_api, name="scan_ticket_api"),


]
