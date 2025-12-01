# packaging/views.py
import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from Inventory.models import Product, Supermarket, Supplier
from .models import ProductPackaging, OrderBatch, OrderLine


# -----------------------------
# Helper: only superadmin can edit packaging
# -----------------------------
def is_superadmin(user):
    # Adapt this to your own custom flag/role
    return user.is_superuser or getattr(user, "is_superadmin", False)


# -----------------------------
# 1. PACKAGING MAPPING (CU → DU)
# -----------------------------

@login_required(login_url='account_login')
def scan_unit_view(request, supermarket_id):
    """
    Step 1: Scan CU barcode.
    If packaging exists => show info.
    If not => redirect to carton scan (superadmin only).
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    return render(request, "packaging/scan_unit.html", {
        "supermarket": supermarket
    })


@login_required(login_url='account_login')
@require_POST
def check_unit_api(request):
    """
    AJAX API:
    Input: unit barcode
    Output:
        - status: "not_found" | "carton_exists" | "need_carton"
    """
    barcode = (request.POST.get("barcode") or "").strip()

    if not barcode:
        return JsonResponse({"status": "error", "message": "No barcode provided."}, status=400)

    product = Product.objects.filter(barcode=barcode).first()
    if not product:
        return JsonResponse({"status": "not_found"}, status=200)

    # multiple packaging options allowed for same CU
    pack_options = ProductPackaging.objects.filter(
        product=product,
        unit_barcode=barcode,
        is_active=True,
    )

    if pack_options.exists():
        data = {
            "status": "carton_exists",
            "product_name": product.name,
            "unit_barcode": barcode,
            "options": [
                {
                    "id": p.id,
                    "carton_barcode": p.carton_barcode,
                    "units_per_carton": p.units_per_carton,
                    "supplier": p.supplier.name if p.supplier else None,
                }
                for p in pack_options
            ]
        }
        return JsonResponse(data)

    # No packaging yet => only superadmin may create
    return JsonResponse({
        "status": "need_carton",
        "product_name": product.name,
        "unit_barcode": barcode,
    })


@login_required(login_url='account_login')
@user_passes_test(is_superadmin)
def scan_carton_view(request, supermarket_id, unit_barcode):
    """
    Page to scan / enter CARTON config for given CU.
    Only superadmin can access.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id)
    product = get_object_or_404(Product, barcode=unit_barcode)

    existing_packs = ProductPackaging.objects.filter(
        product=product, unit_barcode=unit_barcode
    )

    return render(request, "packaging/scan_carton.html", {
        "supermarket": supermarket,
        "product": product,
        "unit_barcode": unit_barcode,
        "existing_packs": existing_packs,
    })


@login_required(login_url='account_login')
@user_passes_test(is_superadmin)
@require_POST
def save_carton_api(request):
    """
    AJAX API to save carton barcode & units_per_carton.
    Only superadmin can save.
    """
    unit_barcode = (request.POST.get("unit_barcode") or "").strip()
    carton_barcode = (request.POST.get("carton_barcode") or "").strip()
    units_str = (request.POST.get("units_per_carton") or "").strip()
    supplier_id = request.POST.get("supplier_id") or None

    if not unit_barcode or not carton_barcode or not units_str:
        return JsonResponse({"success": False, "message": "Missing required fields."}, status=400)

    product = Product.objects.filter(barcode=unit_barcode).first()
    if not product:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)

    try:
        units = int(units_str)
        if units <= 0:
            raise ValueError
    except ValueError:
        return JsonResponse({"success": False, "message": "Invalid units_per_carton."}, status=400)

    supplier = None
    if supplier_id:
        supplier = Supplier.objects.filter(pk=supplier_id).first()

    packaging, created = ProductPackaging.objects.update_or_create(
        product=product,
        unit_barcode=unit_barcode,
        carton_barcode=carton_barcode,
        defaults={
            "units_per_carton": units,
            "supplier": supplier,
            "is_active": True,
        }
    )

    return JsonResponse({
        "success": True,
        "message": "Carton mapping saved.",
        "id": packaging.id,
        "unit_barcode": packaging.unit_barcode,
        "carton_barcode": packaging.carton_barcode,
        "units_per_carton": packaging.units_per_carton,
        "supplier": packaging.supplier.name if packaging.supplier else None,
    })


# -----------------------------
# 2. ORDER BUILDER
# -----------------------------

def _get_or_create_draft_batch(supermarket, user):
    """
    Helper: one open draft batch per (supermarket, user).
    """
    batch = (
        OrderBatch.objects
        .filter(supermarket=supermarket, created_by=user, status="draft")
        .order_by("-created_at")
        .first()
    )
    if not batch:
        batch = OrderBatch.objects.create(
            supermarket=supermarket,
            created_by=user,
        )
    return batch


@login_required(login_url="account_login")
def order_builder_view(request, supermarket_id):
    supermarket = get_object_or_404(
        Supermarket, pk=supermarket_id, owner=request.user
    )

    batch = _get_or_create_draft_batch(supermarket, request.user)
    suppliers = Supplier.objects.all().order_by("name")

    # ----------------------------
    # POST: Finalize or add item
    # ----------------------------
    if request.method == "POST":

        # FINALIZE
        if "finalize" in request.POST:
            supplier_id = request.POST.get("supplier_id") or None
            reference = (request.POST.get("reference") or "").strip()

            if supplier_id:
                batch.supplier_id = supplier_id
            batch.reference = reference
            batch.status = "finalized"
            batch.save()

            if not batch.lines.exists():
                messages.error(
                    request,
                    "Order is empty. Scan at least 1 product before finalizing."
                )
                batch.status = "draft"
                batch.save()
                return redirect("packaging:order_builder", supermarket_id)

            return _generate_order_pdf(batch)

        # ADD SINGLE PRODUCT (Manual)
        barcode = (request.POST.get("barcode") or "").strip()

        if not barcode:
            messages.error(request, "Barcode is empty.")
            return redirect("packaging:order_builder", supermarket_id)

        _add_barcode_to_batch(batch, barcode)
        messages.success(request, f"Added product {barcode}.")
        return redirect("packaging:order_builder", supermarket_id)

    # ----------------------------
    # GET page
    # ----------------------------
    context = {
        "supermarket": supermarket,
        "batch": batch,
        "suppliers": suppliers,
        "lines": batch.lines.select_related("product").all()
    }
    return render(request, "packaging/order_builder.html", context)



def _add_barcode_to_batch(batch: OrderBatch, barcode: str):
    """
    Core logic: add scanned CU barcode to batch.
    If multiple carton configs exist, we pick the first one for now.
    (Later you can add a UI to choose between 12/24 etc.)
    """
    with transaction.atomic():
        product, _created = Product.objects.get_or_create(
            barcode=barcode,
            defaults={"name": f"Product {barcode}"}
        )

        # Get the first active packaging config (if any)
        packaging = ProductPackaging.objects.filter(
            product=product,
            unit_barcode=barcode,
            is_active=True,
        ).order_by("units_per_carton").first()

        line, created_line = OrderLine.objects.get_or_create(
            batch=batch,
            product=product,
            unit_barcode=barcode,
            packaging=packaging,
            defaults={"cartons": 1},
        )

        if not created_line:
            line.cartons += 1
            line.save()


@login_required(login_url="account_login")
def reset_order_batch_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    OrderBatch.objects.filter(
        supermarket=supermarket,
        created_by=request.user,
        status="draft",
    ).delete()

    messages.info(request, "Started a new empty order.")
    return redirect("packaging:order_builder", supermarket_id=supermarket.id)


def _generate_order_pdf(batch: OrderBatch) -> HttpResponse:
    """
    Simple ReportLab PDF for the given order batch.
    """
    response = HttpResponse(content_type="application/pdf")
    filename = f"order_{batch.id}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 50

    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, y, f"Order #{batch.id} - {batch.supermarket.name}")
    y -= 20

    p.setFont("Helvetica", 11)
    supplier_name = batch.supplier.name if batch.supplier else "N/A"
    p.drawString(40, y, f"Supplier: {supplier_name}")
    y -= 15
    if batch.reference:
        p.drawString(40, y, f"Reference: {batch.reference}")
        y -= 15
    p.drawString(40, y, f"Created: {batch.created_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 25

    # Table headers
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Product")
    p.drawString(220, y, "Unit EAN")
    p.drawString(320, y, "Carton Code")
    p.drawString(430, y, "Cartons")
    p.drawString(490, y, "Total Units")
    y -= 12
    p.line(40, y, width - 40, y)
    y -= 15

    p.setFont("Helvetica", 9)
    for line in batch.lines.select_related("product", "packaging").all():
        if y < 60:  # new page
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 9)

        name = (line.product.name or "")[:30]
        p.drawString(40, y, name)
        p.drawString(220, y, line.unit_barcode or "")
        p.drawString(320, y, line.carton_barcode or "-")
        p.drawRightString(470, y, str(line.cartons))
        p.drawRightString(560, y, str(line.total_units))
        y -= 14

    p.showPage()
    p.save()
    return response


# -----------------------------
# 3. AJAX SCAN (from camera)
# -----------------------------

@csrf_exempt
@login_required(login_url="account_login")
def add_scanned_item(request, supermarket_id):
    """
    Called via AJAX every time a barcode is scanned from camera.
    Adds +1 carton to the current draft OrderBatch.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    barcode = data.get("barcode")

    if not barcode:
        return JsonResponse({"error": "Barcode required"}, status=400)

    supermarket = get_object_or_404(Supermarket, id=supermarket_id, owner=request.user)
    batch = _get_or_create_draft_batch(supermarket, request.user)

    _add_barcode_to_batch(batch, barcode)

    return JsonResponse({"status": "ok"})


# -----------------------------
# 4. Edit / Delete order lines
# -----------------------------

@login_required(login_url='account_login')
def update_order_line(request, supermarket_id, line_id):
    line = get_object_or_404(
        OrderLine,
        id=line_id,
        batch__supermarket_id=supermarket_id,
        batch__created_by=request.user,
        batch__status="draft",
    )

    if request.method == "POST":
        try:
            cartons = int(request.POST.get("cartons") or line.cartons)
            if cartons <= 0:
                cartons = 1
            line.cartons = cartons
            line.save()
            messages.success(request, "Quantity updated.")
        except (TypeError, ValueError):
            messages.error(request, "Invalid quantity.")

    return redirect("packaging:order_builder", supermarket_id=supermarket_id)


@login_required(login_url='account_login')
def delete_order_line(request, supermarket_id, line_id):
    line = get_object_or_404(
        OrderLine,
        id=line_id,
        batch__supermarket_id=supermarket_id,
        batch__created_by=request.user,
        batch__status="draft",
    )
    line.delete()
    messages.success(request, "Product removed from order.")
    return redirect("packaging:order_builder", supermarket_id=supermarket_id)
