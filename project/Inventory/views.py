import csv
import random

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Avg, Min, Max, Count
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from pricing.models import CompetitorPrice, WastageRecord, DiscountedSale
from product_price import models
from .tasks import scrape_product_task  # Correctly import the Celery task
from .scraping_utils import get_product_info_cascade  # Correctly import the cascade function


# --- Page Rendering Views ---

def landing_page_view(request):
    if request.user.is_authenticated:
        return redirect('inventory:home')
    return render(request, 'inventory/landing_page.html')



def home_view(request):
    return render(request, 'inventory/home.html')


@login_required
def supermarket_dashboard_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    return render(request, 'inventory/dashboard.html', {'supermarket': supermarket})


# --- ✅ ADD THESE NEW API VIEWS AT THE END OF THE FILE ---

@login_required
def scan_item_page_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    categories = Category.objects.all()
    racks = Rack.objects.filter(supermarket=supermarket).order_by('name')
    return render(request, 'inventory/scan.html', {'supermarket': supermarket, 'categories': categories, 'racks': racks})



@login_required(login_url='account_login')
def inventory_list_view(request, supermarket_id):
    """
    Displays a filterable list of all inventory items, GROUPED BY PRODUCT.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # ✅ FIX: Efficiently pre-fetch all related models, including the new 'rack'
    inventory_items = supermarket.inventory_items.all().select_related(
        'product', 'category', 'product__category', 'rack'
    )

    # Get filter parameters from the URL
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    rack_filter = request.GET.get('rack', '')  # ✅ ADDED: Get new rack filter

    if search_query:
        inventory_items = inventory_items.filter(
            Q(product__name__icontains=search_query) |
            Q(product__brand__icontains=search_query) |
            Q(product__barcode__icontains=search_query)
        )
    if category_filter:
        inventory_items = inventory_items.filter(
            Q(category__id=category_filter) | Q(product__category__id=category_filter)
        ).distinct()

    if status_filter:
        today = timezone.now().date()
        if status_filter == 'fresh':
            inventory_items = inventory_items.filter(expiry_date__gt=today + timezone.timedelta(days=7))
        elif status_filter == 'expires_soon':
            inventory_items = inventory_items.filter(
                expiry_date__range=[today + timezone.timedelta(days=1), today + timezone.timedelta(days=7)])
        elif status_filter == 'expires_today':
            inventory_items = inventory_items.filter(expiry_date=today)
        elif status_filter == 'expired':
            inventory_items = inventory_items.filter(expiry_date__lt=today)

    # ✅ ADDED: New filter logic for rack
    if rack_filter:
        inventory_items = inventory_items.filter(rack__id=rack_filter)

    categories = Category.objects.all()
    # ✅ ADDED: Get all racks for this supermarket to populate the dropdown
    racks = Rack.objects.filter(supermarket=supermarket).order_by('name')

    context = {
        'supermarket': supermarket,
        'inventory_items': inventory_items.order_by('expiry_date'),  # Order the final list
        'categories': categories,
        'racks': racks,  # ✅ Pass racks to the template
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'rack_filter': rack_filter,  # ✅ Pass rack_filter to the template
    }
    return render(request, 'inventory/inventory_list.html', context)



@login_required(login_url='account_login')
def edit_inventory_item(request, supermarket_id, item_id):
    """
    Handles the editing of a single batch of an inventory item.
    ✅ Updated to use the 'rack' ForeignKey.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)

    if request.method == 'POST':
        item.quantity = request.POST.get('quantity', item.quantity)
        item.expiry_date = request.POST.get('expiry_date', item.expiry_date)
        item.store_price = request.POST.get('store_price') or None

        # ✅ FIX: Save the rack_id from the dropdown
        item.rack_id = request.POST.get('rack') or None

        # (Optional: you can clear the old field if you are migrating)
        # item.rack_zone = None

        category_id = request.POST.get('category')
        item.category_id = category_id if category_id else None

        item.save()
        messages.success(request, f"Updated {item.product.name}.")
        return redirect('inventory:inventory_list', supermarket_id=supermarket.id)

    categories = Category.objects.all()
    # ✅ FIX: Fetch all racks *for this supermarket* to show in the dropdown
    racks = Rack.objects.filter(supermarket=supermarket)

    context = {
        'supermarket': supermarket,
        'item': item,
        'categories': categories,
        'racks': racks,  # ✅ Pass the racks to the template
    }
    return render(request, 'inventory/edit_inventory_item.html', context)


@login_required
def export_inventory_csv(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{supermarket.name}_inventory_{timezone.now().date()}.csv"'

    writer = csv.writer(response)
    writer.writerow(
        ['Barcode', 'Product Name', 'Brand', 'Category', 'Quantity', 'Store Price', 'Expiry Date', 'Rack',
         'Status'])

    inventory_items = supermarket.inventory_items.all().select_related('product', 'category')
    for item in inventory_items:
        writer.writerow([
            item.product.barcode,
            item.product.name,
            item.product.brand,
            item.category.name if item.category else 'N/A',
            item.quantity,
            item.store_price,
            item.expiry_date,
            item.manufacture_date,
            item.rack,
            item.status
        ])

    return response




@login_required
def product_list_view(request, supermarket_id):
    """
    Displays a master list of all unique products (the "Product Catalog")
    with pagination and filtering.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # --- ✅ QUERY FOR RACKS ---
    racks = Rack.objects.filter(supermarket=supermarket).order_by('name')

    products_list = Product.objects.all().order_by('name')
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')

    if search_query:
        products_list = products_list.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    if category_filter:
        products_list = products_list.filter(category__id=category_filter)

    categories = Category.objects.all()

    paginator = Paginator(products_list, 100)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    context = {
        'supermarket': supermarket,
        'products': products_page,
        'categories': categories,
        'racks': racks,  # ✅ PASS 'racks' (PLURAL)
        'search_query': search_query,
        'category_filter': category_filter,
    }
    return render(request, 'inventory/product_list.html', context)

@login_required
def product_detail_view(request, supermarket_id, product_barcode):
    """(READ) Displays detailed information about a single product."""
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    product = get_object_or_404(Product, barcode=product_barcode)
    inventory_items = InventoryItem.objects.filter(supermarket=supermarket, product=product).order_by('expiry_date')
    competitor_prices = CompetitorPrice.objects.filter(product=product).order_by('price')
    context = {
        'supermarket': supermarket,
        'product': product,
        'inventory_items': inventory_items,
        'competitor_prices': competitor_prices,
    }
    return render(request, 'inventory/product_detail.html', context)


# from models import Supplier  # Make sure Supplier is imported


# ... (all other view functions like product_list_view, scan_api, etc.)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from .models import Supermarket, StaffProfile, Supplier, Rack, ProductPrice


User = get_user_model()


# Import your models and forms



@login_required(login_url='account_login')
def rack_list_create_view(request, supermarket_id):
    """
    Handles listing all racks for a supermarket AND creating new ones.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    if request.method == 'POST':
        rack_form = RackForm(request.POST)
        if rack_form.is_valid():
            try:
                rack = rack_form.save(commit=False)
                rack.supermarket = supermarket
                rack.save()
                messages.success(request, f"Rack '{rack.name}' created successfully.")
            except IntegrityError:
                messages.error(request, f"A rack with the name '{rack_form.cleaned_data['name']}' already exists.")
            return redirect('inventory:rack_list', supermarket_id=supermarket.id)
    else:
        rack_form = RackForm()

    racks = Rack.objects.filter(supermarket=supermarket).order_by('name')
    context = {
        'supermarket': supermarket,
        'racks': racks,
        'rack_form': rack_form  # Use the specific variable name
    }
    return render(request, 'inventory/management/rack_management.html', context)


@login_required(login_url='account_login')
def rack_edit_view(request, supermarket_id, rack_id):
    """
    Handles editing an existing rack.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    rack = get_object_or_404(Rack, pk=rack_id, supermarket=supermarket)

    if request.method == 'POST':
        rack_form = RackForm(request.POST, instance=rack)
        if rack_form.is_valid():
            try:
                rack_form.save()
                messages.success(request, f"Rack '{rack.name}' updated successfully.")
                return redirect('inventory:rack_list', supermarket_id=supermarket.id)
            except IntegrityError:
                messages.error(request, f"A rack with this name already exists.")
    else:
        rack_form = RackForm(instance=rack)

    context = {
        'supermarket': supermarket,
        'rack': rack,
        'rack_form': rack_form  # Use the specific variable name
    }
    return render(request, 'inventory/management/rack_edit.html', context)


@login_required(login_url='account_login')
@require_POST  # Ensures this view can only be called with a POST request
def rack_delete_view(request, supermarket_id, rack_id):
    """
    Handles deleting a specific rack.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    rack = get_object_or_404(Rack, pk=rack_id, supermarket=supermarket)

    rack_name = rack.name
    rack.delete()
    messages.success(request, f"Rack '{rack_name}' has been deleted.")

    return redirect('inventory:rack_list', supermarket_id=supermarket.id)


# In your inventory/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import F
from .models import Supermarket, Product, Category, Rack, InventoryItem, ProductPrice


@require_POST
@login_required(login_url='account_login')
def add_inventory_from_product_list(request, supermarket_id, product_barcode):
    """
    Handles the form submission from the 'Add to Inventory' modal,
    now with auto-fetching for price, category, and rack.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    product = get_object_or_404(Product, barcode=product_barcode)

    # --- 1. Get all data from the form ---
    # We get the user's explicit choices from the form first
    form_category_id = request.POST.get('category_id')
    form_rack_id = request.POST.get('rack_id')  # Assumes form field is 'rack_id'
    form_price_str = request.POST.get('store_price')

    form_expiry_date = request.POST.get('expiry_date')
    form_manufacture_date = request.POST.get('manufacture_date') or None
    form_quantity = int(request.POST.get('quantity', 1))

    # --- 2. Initialize final values ---
    # The value will be the form value, or None if the user left it blank
    final_category_id = form_category_id if form_category_id else None
    final_rack_id = form_rack_id if form_rack_id else None
    final_store_price = form_price_str if form_price_str and form_price_str.strip() else None

    # --- 3. ✅ NEW: AUTO-FETCH LOGIC for Price, Category, and Rack ---
    try:
        # Get the single default-settings object for this product
        defaults_entry = ProductPrice.objects.get(supermarket=supermarket, product=product)

        # Apply defaults ONLY if the form value was not provided
        if final_store_price is None:
            final_store_price = defaults_entry.price

        # New logic for category
        if final_category_id is None and defaults_entry.default_category_id:
            final_category_id = defaults_entry.default_category_id

        # New logic for rack
        if final_rack_id is None and defaults_entry.default_rack_id:
            final_rack_id = defaults_entry.default_rack_id

    except ProductPrice.DoesNotExist:
        # No defaults entry exists, just continue.
        # The 'final_' variables will remain as they were.
        pass

    # --- 4. ✅ NEW: Fallback for Category ---
    # If category is *still* not set (no form value, no default),
    # use the product's main category as a last resort.
    if final_category_id is None and product.category_id:
        final_category_id = product.category_id

    # --- 5. Handle optional file upload ---
    uploaded_image = request.FILES.get('cover_image')
    if uploaded_image:
        if product.cover_image:
            product.cover_image.delete()
        product.cover_image = uploaded_image
        product.save()

    # --- 6. ✅ FIX: Improved Create or Update Logic ---
    # This logic is much safer. It finds a batch based on *all* its
    # properties, and only sets quantity in the 'defaults'.
    try:
        item, created = InventoryItem.objects.get_or_create(
            supermarket=supermarket,
            product=product,
            expiry_date=form_expiry_date,
            store_price=final_store_price,
            rack_id=final_rack_id,
            category_id=final_category_id,
            manufacture_date=form_manufacture_date,
            defaults={'quantity': form_quantity}  # Only set quantity if new
        )


        if not created:
            # If the batch already exists, just add the quantity
            item.quantity = F('quantity') + form_quantity
            item.save()
            messages.success(request, f"Added {form_quantity} more to an existing batch of {product.name}.")
        else:
            # A new batch was created
            messages.success(request, f"Successfully added a new batch of {product.name} to inventory.")

    # --- 7. ✅ FIX: Cleaned up Exception Handling ---
    except IntegrityError:
        messages.error(request, "Database error. This exact item (product, expiry, price, rack) may already exist.")
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")

    return redirect('inventory:product_list', supermarket_id=supermarket.id)
# @require_POST  # Ensures this view only accepts POST requests
# @login_required(login_url='account_login')
# def add_inventory_from_product_list(request, supermarket_id, product_barcode):
#     """
#     Handles the form submission from the 'Add to Inventory' modal
#     on the product list page.
#     """
#     supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
#     product = get_object_or_404(Product, barcode=product_barcode)
#
#     # --- Handle optional file upload ---
#     uploaded_image = request.FILES.get('cover_image')
#     if uploaded_image:
#         if product.cover_image:
#             product.cover_image.delete()  # Remove old file
#         product.cover_image = uploaded_image
#         product.save()
#
#     # --- Handle optional fields ---
#     category_id = request.POST.get('category_id')
#     category = get_object_or_404(Category, id=category_id) if category_id else None
#     rack_id = request.POST.get('rack_id') or None
#     manufacture_date = request.POST.get('manufacture_date') or None
#
#
#     price_str = request.POST.get('store_price')
#     store_price = price_str if price_str and price_str.strip() else None
#
#     rack_id = request.POST.get('rack') or None
#
#     # --- ✅ FIX: Get the manufacture_date from the form ---
#     manufacture_date = request.POST.get('manufacture_date') or None
#     quantity_to_add = int(request.POST.get('quantity', 1))
#     # --- END FIX ---
#
#     # --- ✅ AUTO-FETCH PRICE LOGIC ---
#     if store_price is None:
#         try:
#             product_price_entry = ProductPrice.objects.get(supermarket=supermarket, product=product)
#             store_price = product_price_entry.price
#         except ProductPrice.DoesNotExist:
#             store_price = None
#
#     try:
#         item, created = InventoryItem.objects.get_or_create(
#             supermarket=supermarket,
#             product=product,
#             category=category,
#             quantity=request.POST.get('quantity', 1),
#             expiry_date=request.POST.get('expiry_date'),
#             manufacture_date=manufacture_date,  # ✅ FIX: Add the field here
#             rack_id=rack_id,
#             store_price=store_price,
#             defaults={
#                 'quantity': quantity_to_add,
#                 'category_id': category_id,
#             }
#         )
#
#         if not created:
#             # If the batch already exists, just add the quantity
#             item.quantity = F('quantity') + quantity_to_add
#             item.save()
#             messages.success(request, f"Added {quantity_to_add} more to an existing batch of {product.name}.")
#         else:
#             # A new batch was created
#             messages.success(request, f"Successfully added a new batch of {product.name} to inventory.")
#     except IntegrityError:
#         messages.error(request, "This exact item (product, expiry, price, rack) already exists.")
#     except Exception as e:
#         messages.error(request, f"An error occurred: {e}")
#
#         messages.success(request, f"Successfully added {product.name} to your inventory.")
#     except Exception as e:
#         messages.error(request, f"An error occurred: {e}")
#
#     return redirect('inventory:product_list', supermarket_id=supermarket.id)

# ... (rest of your views.py file) ...


# --- CRUD FOR PRODUCTS ---

@login_required
def create_product_view(request, supermarket_id):
    """(CREATE) Displays a form to create a new product in the master catalog."""
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        barcode = request.POST.get('barcode')
        name = request.POST.get('name')
        if not barcode or not name:
            messages.error(request, "Barcode and Name are required fields.")
        else:
            try:
                Product.objects.create(
                    barcode=barcode,
                    name=name,
                    brand=request.POST.get('brand'),
                    description=request.POST.get('description')
                )
                messages.success(request, f"Product '{name}' was created successfully.")
                return redirect('inventory:product_list', supermarket_id=supermarket.id)
            except IntegrityError:
                messages.error(request, f"A product with barcode '{barcode}' already exists.")

    context = {'supermarket': supermarket}
    return render(request, 'inventory/product_form.html', context)


from .forms import ProductForm, RackForm  # Import the new form


@login_required
def edit_product_view(request, supermarket_id, product_barcode):
    """(UPDATE) Displays a form to edit an existing product's details."""
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    product = get_object_or_404(Product, barcode=product_barcode)

    if request.method == 'POST':
        # Instantiate the form with all submitted data:
        # request.POST for text/select data
        # request.FILES for file data
        # instance=product to link it to the existing product
        form = ProductForm(request.POST, request.FILES, instance=product)

        if form.is_valid():
            # Handle the custom 'clear_cover_image' checkbox manually
            # We only clear if the box is checked AND no new file was uploaded
            if request.POST.get('clear_cover_image') and 'cover_image' not in request.FILES:
                if product.cover_image:
                    product.cover_image.delete(save=False)  # Delete file from storage
                product.cover_image = None  # Clear the field on the model

            # Now save the form. This will:
            # 1. Update all text fields, category, and suppliers.
            # 2. Save the new 'cover_image' if one was uploaded.
            form.save()

            messages.success(request, f"Successfully updated '{product.name}'.")
            return redirect('inventory:product_detail', supermarket_id=supermarket.id, product_barcode=product.barcode)

        # If form is invalid, we fall through to the render() below
        # The 'product' and 'supermarket' variables are already set

    # --- This block now runs for GET requests OR invalid POSTs ---

    # We must query for categories and suppliers to populate the dropdowns
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()

    context = {
        'supermarket': supermarket,
        'product': product,
        'is_editing': True,
        'categories': categories,  # This was missing before
        'suppliers': suppliers,  # This was missing before
        # 'form': form # Optional: pass the form to display form.errors in the template
    }
    return render(request, 'inventory/product_form.html', context)

from django.contrib import messages

@login_required
def delete_product_view(request, supermarket_id, product_barcode):
    """(DELETE) Handles the deletion of a product from the master catalog."""
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    product = get_object_or_404(Product, barcode=product_barcode)

    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f"Product '{product_name}' was deleted successfully.")
        return redirect('inventory:product_list', supermarket_id=supermarket.id)

    context = {'supermarket': supermarket, 'product': product}
    return render(request, 'inventory/product_delete_confirm.html', context)


# --- END CRUD FOR PRODUCTS ---


@login_required
def alert_monitor_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()
    urgent_items = supermarket.inventory_items.filter(
        Q(expiry_date__lt=today) | Q(expiry_date__lte=today + timezone.timedelta(days=7))
    ).select_related('product').order_by('expiry_date')

    for item in urgent_items:
        days_diff = (item.expiry_date - today).days
        item.days_left = days_diff if days_diff >= 0 else 0
        item.days_since_expiry = abs(days_diff) if days_diff < 0 else 0

    return render(request, 'inventory/alert_monitor.html', {'supermarket': supermarket, 'urgent_items': urgent_items})


@require_POST
@login_required
def delete_inventory_item(request, supermarket_id, item_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)
    item.delete()
    return redirect('inventory:inventory_list', supermarket_id=supermarket.id)


@login_required
def competitive_price_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    products_in_inventory = Product.objects.filter(inventory_instances__supermarket=supermarket).distinct()
    product_prices = []
    for product in products_in_inventory:
        inventory_item = product.inventory_instances.filter(supermarket=supermarket).first()
        competitors = product.competitor_prices.order_by('price')
        stats = competitors.aggregate(avg_price=Avg('price'), min_price=Min('price'))
        difference = None
        if inventory_item and inventory_item.store_price and stats['avg_price']:
            difference = inventory_item.store_price - stats['avg_price']
        product_prices.append(
            {'product': product, 'store_price': inventory_item.store_price if inventory_item else None,
             'competitors': competitors, 'stats': stats, 'difference': difference})
    return render(request, 'inventory/competitive_price_dashboard.html',
                  {'supermarket': supermarket, 'product_prices': product_prices})


# --- Management Views ---
@login_required
def staff_management_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        email = request.POST.get('email')
        role = request.POST.get('role')
        try:
            user_to_add = User.objects.get(email=email)
            StaffProfile.objects.get_or_create(user=user_to_add, supermarket=supermarket, defaults={'role': role})
        except User.DoesNotExist:
            pass  # You can add a Django message here for "user not found"
        return redirect('inventory:staff_management', supermarket_id=supermarket.id)
    staff = supermarket.staff_members.all().select_related('user')
    return render(request, 'inventory/management/staff_management.html', {'supermarket': supermarket, 'staff': staff})


@login_required
def supplier_list_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        Supplier.objects.create(name=request.POST.get('name'), contact_person=request.POST.get('contact_person'),
                                email=request.POST.get('email'), phone=request.POST.get('phone'),
                                address=request.POST.get('address'))
        return redirect('inventory:supplier_list', supermarket_id=supermarket.id)
    suppliers = Supplier.objects.all()
    return render(request, 'inventory/management/supplier_list.html',
                  {'supermarket': supermarket, 'suppliers': suppliers})

# --- API Endpoints ---
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def supermarket_list_api(request):
    if request.method == 'GET':
        supermarkets = Supermarket.objects.filter(owner=request.user)
        data = [{'id': s.id, 'name': s.name, 'location': s.location} for s in supermarkets]
        return Response(data)
    elif request.method == 'POST':
        name = request.data.get('name')
        if not name: return Response({'error': 'Supermarket name is required.'}, status=400)
        supermarket = Supermarket.objects.create(owner=request.user, name=name,
                                                 location=request.data.get('location', ''))
        return Response({'id': supermarket.id, 'name': supermarket.name, 'location': supermarket.location,
                         'dashboard_url': reverse('inventory:supermarket_dashboard', args=[supermarket.id])},
                        status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scrape_prices_api(request, supermarket_id, product_barcode):
    get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    get_object_or_404(Product, pk=product_barcode)
    # Trigger the background Celery task
    scrape_product_task.delay(product_barcode)
    return Response({'message': 'Price analysis has started. The results will be updated automatically in a moment.'},
                    status=202)

from django.http import JsonResponse, HttpResponse

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Avg, Min, Max, Count, OuterRef, Exists
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.core.paginator import Paginator

from .models import Supermarket, Product, InventoryItem, Category


# ... other imports

# ... (all other views remain the same) ...

# ADD THIS NEW API VIEW
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_filter_api(request, supermarket_id):
    """
    Handles asynchronous filtering, sorting, and pagination of the Product Catalog.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # --- Filtering ---
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    stock_status = request.GET.get('stock_status', '')

    product_list = Product.objects.all()

    if search_query:
        product_list = product_list.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )

    if category_id:
        product_list = product_list.filter(category__id=category_id)

    if stock_status == 'in_stock' or stock_status == 'out_of_stock':
        # Annotate each product with a boolean indicating if it has any inventory items in this supermarket
        in_stock_query = InventoryItem.objects.filter(product=OuterRef('pk'), supermarket=supermarket)
        product_list = product_list.annotate(is_in_stock=Exists(in_stock_query))

        if stock_status == 'in_stock':
            product_list = product_list.filter(is_in_stock=True)
        else:  # out_of_stock
            product_list = product_list.filter(is_in_stock=False)

    # --- Sorting ---
    sort_by = request.GET.get('sort', 'name_asc')
    if sort_by == 'name_asc':
        product_list = product_list.order_by('name')
    elif sort_by == 'name_desc':
        product_list = product_list.order_by('-name')
    elif sort_by == 'newest':
        product_list = product_list.order_by('-id')  # Assuming higher ID is newer

    # --- Pagination ---
    page_number = request.GET.get('page', 1)
    paginator = Paginator(product_list, 20)  # Show 20 products per page
    page_obj = paginator.get_page(page_number)

    # Render the product cards using a partial template
    products_html = render_to_string(
        'inventory/partials/_product_grid.html',
        {'products': page_obj.object_list, 'supermarket': supermarket}
    )

    return JsonResponse({
        'products_html': products_html,
        'has_next_page': page_obj.has_next()
    })


# ... (the rest of your views.py) ...


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_search_api(request):
    """
    API endpoint for the live product search.
    Returns both the filtered products and all available categories.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')

    products = Product.objects.all().order_by('name')

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )

    # This filter assumes a Product might have a direct category link.
    # If not, it filters based on its instances in inventory. Adjust if your model is different.
    if category_id:
        try:  # Assuming Product has a direct ForeignKey 'category'
            products = products.filter(category__id=category_id)
        except:  # Fallback to checking inventory instances if direct link fails
            products = products.filter(inventory_instances__category__id=category_id).distinct()

    products = products[:20]  # Limit results

    product_data = [{
        'name': p.name,
        'brand': p.brand,
        'barcode': p.barcode,
        'image_url': p.image_url or '',
        'category_id': p.category.id if hasattr(p, 'category') and p.category else None
    } for p in products]

    # Always send all categories so the modal dropdown can be populated
    all_categories = Category.objects.all().order_by('name')
    category_data = [{'id': c.id, 'name': c.name} for c in all_categories]

    # Structure the response in the required format
    response_data = {
        'products': product_data,
        'categories': category_data
    }

    return JsonResponse(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def product_filter_api(request, supermarket_id):
    """
    Handles asynchronous filtering, sorting, and pagination of the Product Catalog.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # --- Filtering ---
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    stock_status = request.GET.get('stock_status', '')

    product_list = Product.objects.all()

    if search_query:
        product_list = product_list.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )

    if category_id:
        product_list = product_list.filter(category__id=category_id)

    if stock_status == 'in_stock' or stock_status == 'out_of_stock':
        # Annotate each product with a boolean indicating if it has any inventory items in this supermarket
        in_stock_query = InventoryItem.objects.filter(product=OuterRef('pk'), supermarket=supermarket)
        product_list = product_list.annotate(is_in_stock=Exists(in_stock_query))

        if stock_status == 'in_stock':
            product_list = product_list.filter(is_in_stock=True)
        else:  # out_of_stock
            product_list = product_list.filter(is_in_stock=False)

    # --- Sorting ---
    sort_by = request.GET.get('sort', 'name_asc')
    if sort_by == 'name_asc':
        product_list = product_list.order_by('name')
    elif sort_by == 'name_desc':
        product_list = product_list.order_by('-name')
    elif sort_by == 'newest':
        product_list = product_list.order_by('-id')  # Assuming higher ID is newer

    # --- Pagination ---
    page_number = request.GET.get('page', 1)
    paginator = Paginator(product_list, 20)  # Show 20 products per page
    page_obj = paginator.get_page(page_number)

    # Render the product cards using a partial template
    products_html = render_to_string(
        'inventory/partials/_product_grid.html',
        {'products': page_obj.object_list, 'supermarket': supermarket}
    )

    return JsonResponse({
        'products_html': products_html,
        'has_next_page': page_obj.has_next()
    })


# ... (all your other imports)
from django.db.models import F
from django.db import IntegrityError


# ... (all your other views)
# ... other imports ...
from django.db.models import F
from django.db import IntegrityError
import logging  # Import the logging library

# Get an instance of a logger
logger = logging.getLogger(__name__)


# ... other views ...


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_api(request):
    """
    Handles all core scanning, manual lookup, and inventory modification actions.
    """
    mode = request.data.get('mode')
    supermarket_id = request.data.get('supermarket_id')
    if not all([mode, supermarket_id]):
        return Response({'error': 'Mode and supermarket_id required.'}, status=400)

    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    if mode == 'lookup':
        barcode = request.data.get('barcode')
        if not barcode:
            return Response({'error': 'Barcode required.'}, status=400)

        try:
            product, created = Product.objects.get_or_create(barcode=barcode, defaults={'name': f'Product {barcode}'})

            # --- ✅ Scrape new fields ---
            if (created or not product.name or product.name.startswith("Product ")) and not product.cover_image:
                try:
                    product_info = get_product_info_cascade(barcode)
                    if product_info and product_info.get('name'):
                        product.name = product_info.get('name')
                        product.brand = product_info.get('brand')
                        product.image_url = product_info.get('image_url')
                        product.quantity = product_info.get('quantity')  # Scrape package size
                        product.nutriscore_grade = product_info.get('nutriscore_grade')  # Scrape Nutri-Score
                        product.save()
                except Exception as e:
                    logger.warning(f"Scraping failed for {barcode}: {e}")

            existing_items = InventoryItem.objects.filter(supermarket=supermarket, product=product).select_related(
                'rack').order_by('expiry_date')
            categories = list(Category.objects.values('id', 'name'))

            # --- ✅ AUTO-FETCH ALL DEFAULTS ---
            default_price = None
            default_category_id = product.category_id  # Fallback to product's category
            default_rack_id = None
            try:
                defaults_entry = ProductPrice.objects.get(supermarket=supermarket, product=product)
                default_price = defaults_entry.price
                if defaults_entry.default_category_id:
                    default_category_id = defaults_entry.default_category_id
                if defaults_entry.default_rack_id:
                    default_rack_id = defaults_entry.default_rack_id
            except ProductPrice.DoesNotExist:
                pass

            return Response({
                'product': {
                    'barcode': product.barcode, 'name': product.name, 'brand': product.brand,
                    'image_url': product.display_image_url,
                    'default_store_price': default_price,
                    'category_id': default_category_id,  # Send the smart default
                    'default_rack_id': default_rack_id,  # Send the smart default
                },
                'existing_items': [
                    {'id': item.id, 'quantity': item.quantity, 'expiry_date': item.expiry_date, 'rack_id': item.rack_id,
                     'rack_name': item.rack.name if item.rack else None, 'store_price': item.store_price} for item in
                    existing_items],
                'categories': categories
            })
        except Exception as e:
            logger.error(f"Error in scan_api lookup: {e}", exc_info=True)
            return Response({'error': 'An internal server error occurred.'}, status=500)

    elif mode == 'add':
        data = request.data
        try:
            product = get_object_or_404(Product, barcode=data.get('barcode'))

            # --- 1. Get explicit choices from the form ---
            form_category_id = data.get('category_id') or None
            form_rack_id = data.get('rack_id') or None
            form_price_str = data.get('store_price')
            form_store_price = form_price_str if form_price_str and form_price_str.strip() else None
            form_manufacture_date = data.get('manufacture_date') or None
            form_expiry_date = data.get('expiry_date')
            form_quantity = int(data.get('quantity', 1))

            if not form_expiry_date:
                return Response({'error': 'Expiry date is required.'}, status=400)

            # --- 2. Initialize final values ---
            final_category_id = form_category_id
            final_rack_id = form_rack_id
            final_store_price = form_store_price

            # --- 3. AUTO-FETCH DEFAULTS ---
            try:
                defaults_entry = ProductPrice.objects.get(supermarket=supermarket, product=product)
                if final_store_price is None:
                    final_store_price = defaults_entry.price
                if final_category_id is None:
                    final_category_id = defaults_entry.default_category_id
                if final_rack_id is None:
                    final_rack_id = defaults_entry.default_rack_id
            except ProductPrice.DoesNotExist:
                pass  # No defaults, just use form values

            # --- 4. Fallback for Category ---
            if final_category_id is None and product.category_id:
                final_category_id = product.category_id

            # --- 5. Create or Update Logic ---
            item, created = InventoryItem.objects.get_or_create(
                supermarket=supermarket,
                product=product,
                expiry_date=form_expiry_date,
                store_price=final_store_price,
                rack_id=final_rack_id,
                category_id=final_category_id,
                manufacture_date=form_manufacture_date,
                defaults={'quantity': form_quantity}
            )
            if not created:
                item.quantity = F('quantity') + form_quantity
                item.save()
                return Response({'message': 'Updated quantity for existing batch.'}, status=200)
            else:
                return Response({'message': f'New batch of {product.name} added.'}, status=201)

        except IntegrityError:
            return Response({'error': 'A batch with these exact details already exists.'}, status=400)
        except Exception as e:
            logger.error(f"Error in scan_api add mode: {e}", exc_info=True)
            return Response({'error': f'An error occurred: {e}'}, status=400)

    elif mode == 'remove':
        try:
            item = get_object_or_404(InventoryItem, pk=request.data.get('inventory_item_id'), supermarket=supermarket)
            item.delete()
            return Response({'message': 'Batch removed.'})
        except Exception as e:
            logger.error(f"Error removing item: {e}", exc_info=True)
            return Response({'error': 'Failed to remove item.'}, status=500)

    return Response({'error': 'Invalid mode.'}, status=400)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def scan_api(request):
#     mode = request.data.get('mode')
#     supermarket_id = request.data.get('supermarket_id')
#     if not all([mode, supermarket_id]):
#         return Response({'error': 'Mode and supermarket_id required.'}, status=400)
#
#     supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
#
#     if mode == 'lookup':
#         barcode = request.data.get('barcode')
#         if not barcode:
#             return Response({'error': 'Barcode required.'}, status=400)
#
#         try:  # Add outer try block for general safety
#             product, created = Product.objects.get_or_create(barcode=barcode)
#
#             # --- ✅ START: Robust Scraping ---
#             if created or not product.name:
#                 try:
#                     logger.info(f"Attempting to scrape info for new/incomplete product: {barcode}")
#                     product_info = get_product_info_cascade(barcode)  # Your scraping function
#                     if product_info and product_info.get('name'):
#                         product.name = product_info.get('name', f"Product {barcode}")  # Default name if needed
#                         product.brand = product_info.get('brand')
#                         product.image_url = product_info.get('image_url')
#                         product.quantity = product_info.get('quantity')  # Scrape package size
#                         product.nutriscore_grade = product_info.get('nutriscore_grade')  # Scrape Nutri-Score
#                         # Add description if your scraper provides it
#                         # product.description = product_info.get('description')
#                         product.save()
#                         logger.info(f"Successfully scraped and saved info for {barcode}")
#                     else:
#                         logger.warning(f"Scraping yielded no useful info for {barcode}")
#                         # Optionally set a default name if created and scraping failed
#                         if created and not product.name:
#                             product.name = f"Product {barcode}"
#                             product.save()
#                 except Exception as e:
#                     # Log the error but don't crash the API response
#                     logger.error(f"Error during scraping for barcode {barcode}: {e}", exc_info=True)
#                     # Ensure a default name if needed
#                     if created and not product.name:
#                         product.name = f"Product {barcode}"
#                         product.save()
#             # --- ✅ END: Robust Scraping ---
#
#             existing_items = InventoryItem.objects.filter(supermarket=supermarket, product=product).select_related(
#                 'rack').order_by('expiry_date')  # Select related rack
#
#             categories = list(Category.objects.values('id', 'name'))
#
#             default_price = None
#             try:
#                 # Find the default price for this product at this specific supermarket
#                 product_price_entry = ProductPrice.objects.get(supermarket=supermarket, product=product)
#                 default_price = product_price_entry.price
#             except ProductPrice.DoesNotExist:
#                 pass  # No default price has been set, so it remains None
#
#             return Response({
#                 'product': {
#                     'barcode': product.barcode,
#                     'name': product.name,
#                     'brand': product.brand,
#                     'image_url': product.display_image_url,
#                     'category_id': product.category_id,
#                     'default_store_price':default_price,
#                 },
#                 'existing_items': [
#                     {
#                         'id': item.id,
#                         'quantity': item.quantity,
#                         'expiry_date': item.expiry_date,
#                         'rack_id': item.rack_id,  # Return rack ID
#                         'rack_name': item.rack.name if item.rack else None,  # Return rack name
#                         'store_price': item.store_price
#                     } for item in existing_items
#                 ],
#                 'categories': categories
#             })
#
#         except Exception as e:
#             # Catch any other unexpected errors and return JSON
#             logger.error(f"Unexpected error in scan_api lookup for barcode {barcode}: {e}", exc_info=True)
#             return Response({'error': 'An internal server error occurred during lookup.'}, status=500)
#
#
#     elif mode == 'add':
#         data = request.data
#         try:  # Add outer try block
#             product = get_object_or_404(Product, barcode=data.get('barcode'))
#
#             category_id = data.get('category_id') or None
#             store_price = data.get('store_price') or None
#             rack_id = data.get('rack_id') or None  # Use rack_id
#             manufacture_date = data.get('manufacture_date') or None
#             quantity_to_add = int(data.get('quantity', 1))
#
#             # If no price was entered manually, try to find the default price
#             if store_price is None:
#                 try:
#                     product_price_entry = ProductPrice.objects.get(supermarket=supermarket, product=product)
#                     store_price = product_price_entry.price
#                 except ProductPrice.DoesNotExist:
#                     store_price = None
#
#                     # Use get_or_create with rack_id
#             item, created = InventoryItem.objects.get_or_create(
#                 supermarket=supermarket,
#                 product=product,
#                 expiry_date=data.get('expiry_date'),
#                 rack_id=rack_id,  # Use rack_id
#                 store_price=store_price,
#                 # Consider adding manufacture_date here if it should be part of uniqueness
#                 # manufacture_date=manufacture_date,
#                 defaults={
#                     'quantity': quantity_to_add,
#                     'category_id': category_id,
#                     'manufacture_date': manufacture_date
#                 }
#             )
#
#             if not created:
#                 item.quantity = F('quantity') + quantity_to_add
#                 item.save()
#                 # Use request._request.session for messages in DRF/API views if needed
#                 # messages.success(request._request, f"Added {quantity_to_add} more...")
#                 logger.info(f"Updated quantity for existing batch of {product.name} (Barcode: {product.barcode})")
#                 return Response({'message': f'Updated quantity for existing batch of {product.name}.'}, status=200)
#             else:
#                 # messages.success(request._request, f"New batch...")
#                 logger.info(f"Created new batch for {product.name} (Barcode: {product.barcode})")
#                 return Response({'message': f'New batch of {product.name} added.'}, status=201)
#
#         except IntegrityError:
#             logger.warning(f"IntegrityError: Attempted to add duplicate batch for barcode {data.get('barcode')}")
#             return Response(
#                 {'error': 'A batch with these exact details (Product, Expiry, Rack, Price) already exists.'},
#                 status=400)
#         except Exception as e:
#             logger.error(f"Error in scan_api add mode for barcode {data.get('barcode')}: {e}", exc_info=True)
#             return Response({'error': f'An error occurred: {e}'}, status=400)
#
#
#     elif mode == 'remove':
#         try:  # Add try block
#             item = get_object_or_404(InventoryItem, pk=request.data.get('inventory_item_id'), supermarket=supermarket)
#             product_name = item.product.name
#             item.delete()
#             logger.info(f"Removed inventory batch ID {request.data.get('inventory_item_id')} ({product_name})")
#             return Response({'message': 'Batch removed.'})
#         except Exception as e:
#             logger.error(f"Error removing inventory item ID {request.data.get('inventory_item_id')}: {e}",
#                          exc_info=True)
#             return Response({'error': 'Failed to remove item.'}, status=500)
#
#     return Response({'error': 'Invalid mode.'}, status=400)

# ... (rest of your views.py) ...

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def scan_api(request):
#     mode, barcode, supermarket_id = request.data.get('mode'), request.data.get('barcode'), request.data.get('supermarket_id')
#     if not all([mode, supermarket_id]): return Response({'error': 'Mode and supermarket_id are required.'}, status=400)
#     supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
#     if mode == 'lookup':
#         if not barcode: return Response({'error': 'Barcode is required.'}, status=400)
#         product, created = Product.objects.get_or_create(barcode=barcode)
#         if created or not product.name or "Product " in product.name:
#             product_info = get_product_info_cascade(barcode)
#             if product_info.get('name'):
#                 product.name = product_info.get('name')
#                 product.brand = product_info.get('brand')
#                 product.image_url = product_info.get('image_url')
#                 product.description = product_info.get('description')
#                 product.save()
#         inventory_items = InventoryItem.objects.filter(supermarket=supermarket, product=product)
#         categories = list(Category.objects.values('id', 'name'))
#         return Response({'product': {'barcode': product.barcode, 'name': product.name, 'brand': product.brand, 'image_url': product.image_url}, 'inventory_items': [{'id': item.id, 'quantity': item.quantity, 'expiry_date': item.expiry_date, 'rack_zone': item.rack_zone} for item in inventory_items], 'categories': categories})
#     elif mode == 'add':
#         product = get_object_or_404(Product, barcode=barcode)
#         category = get_object_or_404(Category, id=request.data.get('category_id')) if request.data.get('category_id') else None
#         InventoryItem.objects.create(supermarket=supermarket, product=product, category=category, quantity=request.data.get('quantity', 1), expiry_date=request.data.get('expiry_date'), rack_zone=request.data.get('rack_zone', 'N/A'), store_price=request.data.get('store_price'))
#         return Response({'message': f'{product.name} added.'}, status=201)
#     elif mode == 'remove':
#         item = get_object_or_404(InventoryItem, pk=request.data.get('inventory_item_id'), supermarket=supermarket)
#         item.delete()
#         return Response({'message': f'Batch of {item.product.name} removed.'})
#     return Response({'error': 'Invalid mode specified.'}, status=400)



# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def dashboard_stats_api(request, supermarket_id):
#     supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
#     today = timezone.now().date()
#     stats = supermarket.inventory_items.aggregate(total=Sum('quantity'), fresh=Count('id', filter=Q(
#         expiry_date__gt=today + timezone.timedelta(days=7))), soon=Count('id', filter=Q(expiry_date__gte=today,
#                                                                                         expiry_date__lte=today + timezone.timedelta(
#                                                                                             days=7))),
#                                                   expired=Count('id', filter=Q(expiry_date__lt=today)))
#     return Response(
#         {'total_items': stats['total'] or 0, 'fresh_count': stats['fresh'], 'expires_soon_count': stats['soon'],
#          'expired_count': stats['expired']})


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def urgent_items_api(request, supermarket_id):
#     supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
#     today = timezone.now().date()
#     urgent_items = supermarket.inventory_items.filter(
#         Q(expiry_date__lt=today) | Q(expiry_date__lte=today + timezone.timedelta(days=7))).select_related(
#         'product').order_by('expiry_date')
#     data = []
#     for item in urgent_items:
#         days_diff = (item.expiry_date - today).days
#         data.append({'id': item.id, 'product': {'name': item.product.name, 'brand': item.product.brand,
#                                                 'image_url': item.product.image_url}, 'quantity': item.quantity,
#                      'rack_zone': item.rack_zone, 'status': item.status,
#                      'days_left': days_diff if days_diff >= 0 else 0,
#                      'days_since_expiry': abs(days_diff) if days_diff < 0 else 0})
#     return Response(data)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Avg, Min, Max, Count
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from .tasks import scrape_product_task
from .scraping_utils import get_product_info_cascade


# ... (all other views remain the same) ...

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()
    stats = supermarket.inventory_items.aggregate(total=Sum('quantity'), fresh=Count('id', filter=Q(
        expiry_date__gt=today + timezone.timedelta(days=7))), soon=Count('id', filter=Q(expiry_date__gte=today,
                                                                                        expiry_date__lte=today + timezone.timedelta(
                                                                                            days=7))),
                                                  expired=Count('id', filter=Q(expiry_date__lt=today)))
    return Response(
        {'total_items': stats['total'] or 0, 'fresh_count': stats['fresh'], 'expires_soon_count': stats['soon'],
         'expired_count': stats['expired']})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def urgent_items_api(request, supermarket_id):
    """
    API endpoint for the "Urgent Attention" list on the dashboard.
    This version now includes the product barcode in the response.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()
    urgent_items = supermarket.inventory_items.filter(
        Q(expiry_date__lt=today) | Q(expiry_date__lte=today + timezone.timedelta(days=7))).select_related(
        'product').order_by('expiry_date')

    data = []
    for item in urgent_items:
        days_diff = (item.expiry_date - today).days
        data.append({
            'id': item.id,
            'product': {
                'name': item.product.name,
                'brand': item.product.brand,
                'image_url': item.product.image_url,
                'barcode': item.product.barcode  # --- FIX: Barcode is now included ---
            },
            'quantity': item.quantity,
            'rack_name': item.rack.name if item.rack else 'N/A',
            'rack_zone': item.rack_zone,
            'status': item.status,
            'days_left': days_diff if days_diff >= 0 else 0,
            'days_since_expiry': abs(days_diff) if days_diff < 0 else 0
        })
    return Response(data)

# ... (all other views and API endpoints remain the same) ...



