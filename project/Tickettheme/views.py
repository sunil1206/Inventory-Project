from decimal import Decimal
import json
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction

# MODELS
from Inventory.models import Product, Supermarket, ProductPrice, Category
from pricing.models import Promotion
from .models import TicketLabel, TicketTheme, LabelSheet

# PDF + BARCODE
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
import barcode
from barcode.writer import ImageWriter


# ============================================================
# HELPER — GET STORE PRICE
# ============================================================
def get_store_price(product, supermarket):
    """
    Returns the current store price or 0.00 if not set
    """
    pp = ProductPrice.objects.filter(product=product, supermarket=supermarket).first()
    return pp.price if pp and pp.price else Decimal("0.00")


# ============================================================
# HELPER — FIND PRODUCT BY BARCODE AND PRICE
# ============================================================
def get_product_and_price(barcode_value, supermarket):
    """
    Lookup product globally + price for a supermarket
    """
    product = Product.objects.filter(barcode=barcode_value).first()
    if not product:
        return None, None

    return product, get_store_price(product, supermarket)


# ============================================================
# PROMOTION CALCULATION
# ============================================================
def apply_best_promotion(product, supermarket, base_price: Decimal):
    """
    Checks:
      - product promotions
      - category promotions
      - active + within date

    Returns:
        (final_price, display_text, original_price)
    """

    now = timezone.now()

    promos = Promotion.objects.filter(
        supermarket=supermarket,
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    ).filter(
        # product or category match
        category__in=[product.category] if hasattr(product, "category") else None
    ) | Promotion.objects.filter(
        supermarket=supermarket,
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
        products=product
    )

    if not promos.exists():
        return base_price, None, None

    best_price = base_price
    best_label = None

    for promo in promos:
        # % OFF
        if promo.discount_type == "PERCENTAGE":
            discounted = base_price * (Decimal(100 - promo.discount_value) / 100)
            text = f"-{promo.discount_value}%"

        # FIXED €
        elif promo.discount_type == "FIXED_AMOUNT":
            discounted = base_price - promo.discount_value
            text = f"-{promo.discount_value}€"

        # MULTIPACK (3 for 10€)
        elif promo.discount_type == "MULTIPACK":
            eff = promo.pack_price / promo.pack_qty
            discounted = eff
            text = f"{promo.pack_qty} for {promo.pack_price}€"

        # BOGO
        elif promo.discount_type == "BOGO":
            eff = (base_price * promo.buy_qty) / (promo.buy_qty + promo.free_qty)
            discounted = eff
            text = f"Buy {promo.buy_qty} get {promo.free_qty} free"

        else:
            continue

        if discounted < best_price:
            best_price = discounted
            best_label = text

    if not best_label:
        return base_price, None, None

    return best_price, best_label, base_price


# ============================================================
# CREATE TICKET SNAPSHOT
# ============================================================
def create_ticket_snapshot(product, supermarket, unit_price, theme, created_by,
                           price_per_liter=None, include_carton=False,
                           promo_display=None, promo_original=None):
    """
    Freeze the label information at creation time.
    """

    return TicketLabel.objects.create(
        supermarket=supermarket,
        product=product,
        theme=theme,

        # PRICE SNAPSHOT
        unit_price=unit_price,
        price_per_liter=price_per_liter,

        # PRODUCT INFO SNAPSHOT
        product_name=product.name,
        product_brand=getattr(product, "brand", None),
        unit_barcode=product.barcode,
        carton_barcode=getattr(product, "carton_barcode", None),
        units_per_carton=getattr(product, "units_per_carton", None),
        include_carton_barcode=include_carton,

        # PROMO SNAPSHOT
        promo_display=promo_display,
        promo_original_price=promo_original,

        created_by=created_by
    )


# ============================================================
# TICKET LIST
# ============================================================
@login_required
def ticket_list_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)

    tickets = TicketLabel.objects.filter(
        supermarket=supermarket,
        printed_at__isnull=True
    ).order_by("-created_at")

    return render(request, "tickettheme/ticket_list.html", {
        "supermarket": supermarket,
        "tickets": tickets,
    })


# ============================================================
# TICKET CREATE PAGE
# ============================================================
@login_required
def ticket_create_view(request, supermarket_id, product_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)
    product = get_object_or_404(Product, pk=product_id)

    themes = TicketTheme.objects.filter(supermarket=supermarket)

    base_price = get_store_price(product, supermarket)
    final_price, promo_text, original_price = apply_best_promotion(product, supermarket, base_price)

    if request.method == "POST":
        raw_price = request.POST.get("price")
        raw_ppl = request.POST.get("ppl")
        include_carton = request.POST.get("include_carton") == "on"
        theme_id = request.POST.get("theme")

        try:
            unit_price = Decimal(raw_price) if raw_price else final_price
        except:
            unit_price = final_price

        ppl = raw_ppl or None
        theme = TicketTheme.objects.filter(id=theme_id, supermarket=supermarket).first()

        create_ticket_snapshot(
            product=product,
            supermarket=supermarket,
            unit_price=unit_price,
            theme=theme,
            created_by=request.user,
            price_per_liter=ppl,
            include_carton=include_carton,
            promo_display=promo_text,
            promo_original=original_price,
        )

        messages.success(request, "Ticket added to queue.")
        return redirect("ticket:ticket_list", supermarket_id=supermarket.id)

    return render(request, "tickettheme/ticket_create.html", {
        "supermarket": supermarket,
        "product": product,
        "themes": themes,
        "base_price": base_price,
        "promo_price": final_price,
        "promo_display": promo_text,
        "promo_original_price": original_price,
    })


# ============================================================
# SCAN API — BARCODE FROM CAMERA
# ============================================================
@csrf_exempt
@login_required
def scan_ticket_api(request, supermarket_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    try:
        body = json.loads(request.body)
    except:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    barcode_value = body.get("barcode")
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)

    if not barcode_value:
        return JsonResponse({"error": "Barcode missing"}, status=400)

    product, base_price = get_product_and_price(barcode_value, supermarket)
    if not product:
        return JsonResponse({"error": "Product not found"}, status=404)

    final_price, promo_text, original_price = apply_best_promotion(product, supermarket, base_price)
    theme = TicketTheme.objects.filter(supermarket=supermarket).first()

    create_ticket_snapshot(
        product=product,
        supermarket=supermarket,
        unit_price=final_price,
        price_per_liter=None,
        theme=theme,
        created_by=request.user,
        include_carton=False,
        promo_display=promo_text,
        promo_original=original_price,
    )

    return JsonResponse({"ok": True, "product": product.name, "price": float(final_price)})


# ============================================================
# DELETE TICKET
# ============================================================
@login_required
def ticket_delete_view(request, supermarket_id, ticket_id):
    ticket = get_object_or_404(TicketLabel, id=ticket_id, supermarket_id=supermarket_id)
    ticket.delete()
    messages.success(request, "Ticket removed.")
    return redirect("ticket:ticket_list", supermarket_id=supermarket_id)


# ============================================================
# SINGLE TICKET PDF EXPORT
# ============================================================
@login_required
def ticket_pdf_export(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)

    tickets = list(TicketLabel.objects.filter(
        supermarket=supermarket,
        printed_at__isnull=True
    ).order_by("created_at"))

    if not tickets:
        messages.warning(request, "No tickets in queue.")
        return redirect("ticket:ticket_list", supermarket_id=supermarket.id)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=tickets.pdf"

    # Default thermal roll size 80×50mm
    width_mm = 80
    height_mm = 50
    c = canvas.Canvas(response, pagesize=(width_mm * mm, height_mm * mm))

    for t in tickets:
        draw_ticket(c, t, width_mm, height_mm)
        c.showPage()

    c.save()

    TicketLabel.objects.filter(id__in=[t.id for t in tickets]).update(printed_at=timezone.now())

    return response


# ============================================================
# DRAW TICKET
# ============================================================
def draw_ticket(canvas_obj, ticket, width_mm, height_mm):
    W = width_mm * mm
    H = height_mm * mm

    y = H

    # Title
    canvas_obj.setFont("Helvetica-Bold", 11)
    canvas_obj.drawString(4*mm, y-6*mm, ticket.product_name[:35])

    # Brand small
    if ticket.product_brand:
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.drawString(4*mm, y-10*mm, ticket.product_brand[:32])

    # PRICE BIG — FRANPRIX STYLE
    canvas_obj.setFont("Helvetica-Bold", 28)
    canvas_obj.drawString(4*mm, y-26*mm, f"{ticket.unit_price:.2f}€")

    # price per liter small
    if ticket.price_per_liter:
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.drawString(4*mm, y-33*mm, ticket.price_per_liter)

    # Promo Chip
    if ticket.promo_display:
        canvas_obj.setFont("Helvetica-Bold", 9)
        canvas_obj.drawString(4*mm, y-40*mm, f"{ticket.promo_display}")

    # BARCODE
    EAN = barcode.get_barcode_class("ean13")
    try:
        img = EAN(ticket.unit_barcode, writer=ImageWriter())
        buf = BytesIO()
        img.write(buf)
        canvas_obj.drawImage(ImageReader(buf), 4*mm, 3*mm, width=W*0.78, height=13*mm)
    except:
        pass


# ============================================================
# LABEL SHEETS CRUD — keep same as your version
# ============================================================
@login_required
def label_sheet_list_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)
    sheets = LabelSheet.objects.filter(supermarket=supermarket)
    return render(request, "tickettheme/sheet_list.html", {
        "supermarket": supermarket,
        "sheets": sheets,
    })


@login_required
def label_sheet_create_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)

    if request.method == "POST":
        LabelSheet.objects.create(
            supermarket=supermarket,
            name=request.POST.get("name"),
            cols=request.POST.get("cols"),
            rows=request.POST.get("rows"),
            label_width_mm=request.POST.get("label_width_mm"),
            label_height_mm=request.POST.get("label_height_mm"),
            margin_top_mm=request.POST.get("margin_top_mm"),
            margin_left_mm=request.POST.get("margin_left_mm"),
            gap_horizontal_mm=request.POST.get("gap_horizontal_mm"),
            gap_vertical_mm=request.POST.get("gap_vertical_mm"),
        )
        messages.success(request, "Sheet layout created.")
        return redirect("ticket:label_sheet_list", supermarket_id=supermarket.id)

    return render(request, "tickettheme/sheet_create.html", {"supermarket": supermarket})


@login_required
def label_sheet_edit_view(request, supermarket_id, sheet_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)
    sheet = get_object_or_404(LabelSheet, pk=sheet_id, supermarket=supermarket)

    if request.method == "POST":
        for field in [
            "name", "cols", "rows",
            "label_width_mm", "label_height_mm",
            "margin_top_mm", "margin_left_mm",
            "gap_horizontal_mm", "gap_vertical_mm"
        ]:
            setattr(sheet, field, request.POST.get(field))
        sheet.save()

        messages.success(request, "Sheet updated.")
        return redirect("ticket:label_sheet_list", supermarket_id=supermarket.id)

    return render(request, "tickettheme/sheet_edit.html", {"sheet": sheet})


@login_required
def label_sheet_delete_view(request, supermarket_id, sheet_id):
    sheet = get_object_or_404(LabelSheet, pk=sheet_id, supermarket_id=supermarket_id)
    sheet.delete()
    messages.success(request, "Sheet deleted.")
    return redirect("ticket:label_sheet_list", supermarket_id=supermarket_id)


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from Inventory.models import Supermarket
from .models import TicketTheme


# ===========================
# List all Themes
# ===========================
@login_required
def ticket_theme_list_view(request, supermarket_id):
    """
    Show all label themes created for this supermarket.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)

    themes = TicketTheme.objects.filter(
        supermarket=supermarket
    ).order_by("-id")

    return render(request, "tickettheme/theme_list.html", {
        "supermarket": supermarket,
        "themes": themes,
    })


# ===========================
# Create new Theme
# ===========================
@login_required
def ticket_theme_create_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()

        if not name:
            messages.error(request, "Theme name is required.")
            return redirect("ticket:ticket_theme_create", supermarket_id=supermarket_id)

        TicketTheme.objects.create(
            supermarket=supermarket,
            name=name,
            background_color=request.POST.get("background_color") or "#FFFFFF",
            text_color=request.POST.get("text_color") or "#000000",
            accent_color=request.POST.get("accent_color") or "#E53935",

            # cm or mm — guaranteed fallback
            width_mm=request.POST.get("width_mm") or 80,
            height_mm=request.POST.get("height_mm") or 40,

            match_product_color=request.POST.get("match_product_color") == "on",
        )

        messages.success(request, "Theme created successfully.")
        return redirect("ticket:ticket_theme_list", supermarket_id=supermarket.id)

    return render(request, "tickettheme/theme_create.html", {
        "supermarket": supermarket,
    })


# ===========================
# Edit Theme
# ===========================
@login_required
def ticket_theme_edit_view(request, supermarket_id, theme_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)
    theme = get_object_or_404(TicketTheme, pk=theme_id, supermarket=supermarket)

    if request.method == "POST":
        theme.name = request.POST.get("name") or theme.name
        theme.background_color = request.POST.get("background_color") or theme.background_color
        theme.text_color = request.POST.get("text_color") or theme.text_color
        theme.accent_color = request.POST.get("accent_color") or theme.accent_color

        theme.width_mm = request.POST.get("width_mm") or theme.width_mm
        theme.height_mm = request.POST.get("height_mm") or theme.height_mm

        theme.match_product_color = request.POST.get("match_product_color") == "on"
        theme.save()

        messages.success(request, "Theme updated successfully.")
        return redirect("ticket:ticket_theme_list", supermarket_id=supermarket_id)

    return render(request, "tickettheme/theme_edit.html", {
        "theme": theme,
        "supermarket": supermarket,
    })


# ===========================
# Delete Theme
# ===========================
@login_required
def ticket_theme_delete_view(request, supermarket_id, theme_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)
    theme = get_object_or_404(TicketTheme, pk=theme_id, supermarket=supermarket)

    theme.delete()
    messages.success(request, "Theme deleted.")
    return redirect("ticket:ticket_theme_list", supermarket_id=supermarket_id)
