# ... (all your existing imports)
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from Inventory.models import Product, InventoryItem, Category, ProductPrice, Rack  # Make sure Product is imported





from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q, F, Avg, Min, Sum, Count
import decimal
import random

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Import models from other apps
from Inventory.models import Supermarket
from Inventory.models import InventoryItem, Product

# Import models and forms from THIS app
from pricing.models import DiscountedSale, WastageRecord


import random
# ... (all your other imports)
import decimal
from django.db.models import Q, Subquery, OuterRef
from django.core.paginator import Paginator
from Inventory.models import ProductPrice

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Subquery, OuterRef, Q, DecimalField
from django.core.paginator import Paginator

import decimal

# This is the single view that handles everything
@login_required(login_url='account_login')
def manage_product_prices_view(request, supermarket_id):
    """
    (CRUD) Handles setting, viewing, and updating default prices,
    categories, and racks from a single page.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # Fetch related objects for the filters and forms
    try:
        racks = Rack.objects.filter(supermarket=supermarket)
    except NameError:
        racks = []  # Fallback if Rack model isn't imported

    categories = Category.objects.all()

    # --- POST (Create/Update Price & Defaults) Logic ---
    if request.method == 'POST':
        product_barcode = request.POST.get('product_id')
        price_str = request.POST.get('price', '').strip()
        category_id = request.POST.get('category_id') or None
        rack_id = request.POST.get('rack_id') or None

        if not product_barcode:
            messages.error(request, "Invalid product.")
            return redirect(request.META.get('HTTP_REFERER', 'product_pricing:product_price_list'))

        product = get_object_or_404(Product, pk=product_barcode)

        try:
            # Prepare the new price value
            new_price = None
            if price_str:
                new_price = decimal.Decimal(price_str)

            # --- LOGIC FIX ---
            # Use update_or_create to safely find or create the object
            # and update its values in a single, atomic database transaction.
            obj, created = ProductPrice.objects.update_or_create(
                supermarket=supermarket,
                product=product,
                defaults={
                    'price': new_price,
                    'default_category_id': category_id,
                    'default_rack_id': rack_id
                }
            )
            # --- END OF FIX ---

            if created:
                messages.success(request, f"Defaults for {product.name} created.")
            else:
                messages.success(request, f"Defaults for {product.name} updated.")

            # --- CASCADING UPDATE LOGIC ---
            if new_price is not None:
                updated_count = InventoryItem.objects.filter(
                    supermarket=supermarket,
                    product=product,
                    promotion__isnull=True,
                    applied_rule__isnull=True
                ).update(store_price=new_price)

                if updated_count > 0:
                    messages.info(request, f"Updated price for {updated_count} existing inventory batches.")

        except (decimal.InvalidOperation, ValueError):
            messages.error(request, "Invalid price format. Please enter a number like 12.50.")
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            logger.error(f"Error in manage_product_prices POST: {e}", exc_info=True)

        query_params = request.GET.urlencode()
        redirect_url = f"{request.path}?{query_params}#product-row-{product.barcode}"
        return redirect(redirect_url)

    # --- GET Request (Read) Logic ---

    price_subquery = ProductPrice.objects.filter(product=OuterRef('pk'), supermarket=supermarket).values('price')[:1]
    cat_name_subquery = ProductPrice.objects.filter(product=OuterRef('pk'), supermarket=supermarket).values(
        'default_category__name')[:1]
    rack_name_subquery = ProductPrice.objects.filter(product=OuterRef('pk'), supermarket=supermarket).values(
        'default_rack__name')[:1]

    product_list = Product.objects.annotate(
        current_price=Subquery(price_subquery, output_field=DecimalField()),
        current_category=Subquery(cat_name_subquery),
        current_rack=Subquery(rack_name_subquery)
    ).order_by('name')

    # --- Filters ---
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    rack_id_filter = request.GET.get('rack', '')
    price_status = request.GET.get('price_status', '')

    if query:
        product_list = product_list.filter(
            Q(name__icontains=query) | Q(brand__icontains=query) | Q(barcode__icontains=query))
    if category_id:
        product_list = product_list.filter(price_listings__default_category__id=category_id)
    if rack_id_filter:
        product_list = product_list.filter(price_listings__default_rack__id=rack_id_filter)
    if price_status == 'set':
        product_list = product_list.filter(current_price__isnull=False)
    elif price_status == 'unset':
        product_list = product_list.filter(current_price__isnull=True)

    paginator = Paginator(product_list.distinct(), 30)
    page_number = request.GET.get('page')

    # --- "Scan to Find" Feature Logic ---
    if query and not page_number and Product.objects.filter(barcode=query).exists():
        product_ids = list(product_list.values_list('barcode', flat=True))
        try:
            index = product_ids.index(query)
            page_number = (index // 30) + 1
        except ValueError:
            page_number = 1
    # --- End "Scan to Find" Logic ---

    page_obj = paginator.get_page(page_number)

    context = {
        'supermarket': supermarket,
        'page_obj': page_obj,
        'categories': categories,
        'racks': racks,
        'search_query': query,
        'category_filter': category_id,
        'rack_filter': rack_id_filter,
        'price_status_filter': price_status,
    }
    return render(request, 'pricing/manage_product_prices.html', context)
    # --- GET Request (Read) Logic ---
    # (Your GET logic appears correct and does not need changes)
    price_subquery = ProductPrice.objects.filter(product=OuterRef('pk'), supermarket=supermarket).values('price')[:1]
    cat_name_subquery = ProductPrice.objects.filter(product=OuterRef('pk'), supermarket=supermarket).values('default_category__name')[:1]
    rack_name_subquery = ProductPrice.objects.filter(product=OuterRef('pk'), supermarket=supermarket).values('default_rack__name')[:1]

    product_list = Product.objects.annotate(
        current_price=Subquery(price_subquery, output_field=DecimalField()),
        current_category=Subquery(cat_name_subquery),
        current_rack=Subquery(rack_name_subquery)
    ).order_by('name')

    # --- Filters ---
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    rack_id = request.GET.get('rack', '')
    price_status = request.GET.get('price_status', '')

    if query:
        product_list = product_list.filter(Q(name__icontains=query) | Q(brand__icontains=query) | Q(barcode__icontains=query))
    if category_id:
        product_list = product_list.filter(price_listings__default_category__id=category_id)
    if rack_id:
        product_list = product_list.filter(price_listings__default_rack__id=rack_id)
    if price_status == 'set':
        product_list = product_list.filter(current_price__isnull=False)
    elif price_status == 'unset':
        product_list = product_list.filter(current_price__isnull=True)

    paginator = Paginator(product_list.distinct(), 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'supermarket': supermarket,
        'page_obj': page_obj,
        'categories': categories,
        'racks': racks,
        'search_query': query,
        'category_filter': category_id,
        'rack_filter': rack_id,
        'price_status_filter': price_status,
    }
    return render(request, 'pricing/manage_product_prices.html', context)

# This is the single view that handles everything
# @login_required(login_url='account_login')
# def manage_product_prices_view(request, supermarket_id):
#     """
#     (CRUD) Handles setting, viewing, and updating default prices,
#     categories, and racks from a single page.
#     """
#     supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
#
#     # Fetch all racks for this supermarket (for forms and filters)
#     racks = Rack.objects.filter(supermarket=supermarket)
#     categories = Category.objects.all()
#
#     # --- POST (Create/Update Price & Defaults) Logic ---
#     if request.method == 'POST':
#         product_barcode = request.POST.get('product_id')
#         price_str = request.POST.get('price', '').strip()
#         category_id = request.POST.get('category_id') or None  # Handle "" as None
#         rack_id = request.POST.get('rack_id') or None  # Handle "" as None
#
#         if not product_barcode:
#             messages.error(request, "Invalid product.")
#             # Redirect back to the page you were on, with filters
#             return redirect(request.META.get('HTTP_REFERER', 'product_pricing:product_price_list'))
#
#         product = get_object_or_404(Product, pk=product_barcode)
#
#         try:
#             # Get the defaults object or create it
#             obj, created = ProductPrice.objects.get_or_create(
#                 supermarket=supermarket,
#                 product=product
#             )
#
#             # Update fields from the form
#             obj.default_category_id = category_id
#             obj.default_rack_id = rack_id
#
#             new_price = None
#             if price_str:
#                 new_price = decimal.Decimal(price_str)
#                 obj.price = new_price
#             else:
#                 obj.price = None  # Clear the price if the field was empty
#
#             obj.save()
#             messages.success(request, f"Defaults for {product.name} updated.")
#
#             # --- CASCADING UPDATE LOGIC ---
#             if new_price is not None:
#                 updated_count = InventoryItem.objects.filter(
#                     supermarket=supermarket,
#                     product=product,
#                     promotion__isnull=True,
#                     applied_rule__isnull=True
#                 ).update(store_price=new_price)
#
#                 if updated_count > 0:
#                     messages.info(request, f"Updated price for {updated_count} existing inventory batches.")
#
#         except (decimal.InvalidOperation, ValueError):
#             messages.error(request, "Invalid price format.")
#         except Exception as e:
#             messages.error(request, f"An error occurred: {e}")
#
#         # Redirect back to the same page, preserving filters
#         # And jump to the row you just edited
#         query_params = request.GET.urlencode()
#         redirect_url = f"{request.path}?{query_params}#product-row-{product.barcode}"
#         return redirect(redirect_url)
#
#     # --- GET Request (Read) Logic ---
#
#     # Subqueries to fetch all defaults in one go
#     price_subquery = ProductPrice.objects.filter(
#         product=OuterRef('pk'), supermarket=supermarket
#     ).values('price')[:1]
#
#     cat_name_subquery = ProductPrice.objects.filter(
#         product=OuterRef('pk'), supermarket=supermarket
#     ).values('default_category__name')[:1]  # Get name for display
#
#     rack_name_subquery = ProductPrice.objects.filter(
#         product=OuterRef('pk'), supermarket=supermarket
#     ).values('default_rack__name')[:1]  # Get name for display
#
#     product_list = Product.objects.annotate(
#         current_price=Subquery(price_subquery, output_field=DecimalField()),
#         current_category=Subquery(cat_name_subquery),  # Your template uses this
#         current_rack=Subquery(rack_name_subquery)  # Your template uses this
#     ).order_by('name')
#
#     # --- Filters ---
#     query = request.GET.get('q', '')
#     category_id = request.GET.get('category', '')
#     rack_id = request.GET.get('rack', '')
#     price_status = request.GET.get('price_status', '')
#
#     if query:
#         product_list = product_list.filter(
#             Q(name__icontains=query) | Q(brand__icontains=query) | Q(barcode__icontains=query))
#     if category_id:
#         product_list = product_list.filter(price_listings__default_category__id=category_id)
#     if rack_id:
#         product_list = product_list.filter(price_listings__default_rack__id=rack_id)
#     if price_status == 'set':
#         product_list = product_list.filter(current_price__isnull=False)
#     elif price_status == 'unset':
#         product_list = product_list.filter(current_price__isnull=True)
#
#     paginator = Paginator(product_list.distinct(), 30)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
#
#     context = {
#         'supermarket': supermarket,
#         'page_obj': page_obj,
#         'categories': categories,
#         'racks': racks,
#         'search_query': query,
#         'category_filter': category_id,
#         'rack_filter': rack_id,
#         'price_status_filter': price_status,
#     }
#     return render(request, 'pricing/manage_product_prices.html', context)
# ... (all your existing views like pricing_strategy_view, alert_monitor_view, etc.) ...


# --- ✅ NEW: API Views for Dashboard Analytics ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_financial_kpi_api(request, supermarket_id):
    """
    Calculates and returns key financial metrics for the dashboard.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # Calculate revenue from successfully sold discounted items
    recaptured_revenue = DiscountedSale.objects.filter(supermarket=supermarket).aggregate(
        total=Sum('final_price')
    )['total'] or 0

    # Calculate total wasted items
    total_wasted_items = WastageRecord.objects.filter(supermarket=supermarket).aggregate(
        total=Sum('quantity_wasted')
    )['total'] or 0

    return Response({
        'recaptured_revenue': f"{recaptured_revenue:,.2f}",
        'total_wasted_items': total_wasted_items or 0,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_competitor_api(request, supermarket_id):
    """
    Fetches 5 random products with competitor pricing analysis.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)

    # Get all products that have a price set in this supermarket
    # Note: This requires the 'ProductPrice' model from our previous discussion
    try:
        from .models import ProductPrice
        priced_products = Product.objects.filter(
            price_listings__supermarket=supermarket
        ).annotate(
            store_price=F('price_listings__price'),
            avg_comp_price=Avg('competitor_prices__price')
        ).filter(avg_comp_price__isnull=False)

        product_ids = list(priced_products.values_list('pk', flat=True))
        random_ids = random.sample(product_ids, min(len(product_ids), 5))
        products_sample = priced_products.filter(pk__in=random_ids)

        data = []
        for product in products_sample:
            difference = product.store_price - product.avg_comp_price
            data.append({
                'name': product.name,
                'store_price': product.store_price,
                'avg_comp_price': product.avg_comp_price,
                'difference': difference,
            })
    except ImportError:
        # Fallback if ProductPrice model isn't imported
        data = []

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()
    stats = supermarket.inventory_items.aggregate(
        total_items=Sum('quantity'),
        fresh_count=Count('id', filter=Q(expiry_date__gt=today + timezone.timedelta(days=7))),
        soon_count=Count('id', filter=Q(expiry_date__range=[today, today + timezone.timedelta(days=7)])),
        expired_count=Count('id', GTR(expiry_date__lt=today))
    )
    return Response({
        'total_items': stats['total_items'] or 0,
        'fresh_count': stats['fresh_count'],
        'expires_soon_count': stats['soon_count'],
        'expired_count': stats['expired_count']
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def urgent_items_api(request, supermarket_id):
    """
    API endpoint for the "Urgent Attention" list on the dashboard.
    ✅ This is the single, correct version of this function.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()
    urgent_items_qs = supermarket.inventory_items.filter(
        expiry_date__lt=today + timezone.timedelta(days=8)
    ).select_related('product', 'rack', 'applied_rule', 'promotion').order_by('expiry_date')

    data = []
    for item in urgent_items_qs:
        days_diff = (item.expiry_date - today).days
        data.append({
            'id': item.id,
            'product': {
                'name': item.product.name,
                'brand': item.product.brand,
                'image_url': item.product.display_image_url,  # ✅ Use smart property
                'barcode': item.product.barcode
            },
            'quantity': item.quantity,
            'rack_name': item.rack.name if item.rack else 'N/A',  # ✅ Use rack.name
            'status': item.status,
            'days_left': days_diff if days_diff >= 0 else 0,
            'days_since_expiry': abs(days_diff) if days_diff < 0 else 0
        })
    return Response(data)


# Add this new view to your product_price/views.py




# --- ADD THIS ENTIRE FUNCTION ---

@require_POST  # This view ONLY accepts POST
@login_required(login_url='account_login')
def update_product_defaults_view(request, supermarket_id, product_barcode):
    """
    Handles the POST submission from the "Edit Defaults" modal.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    product = get_object_or_404(Product, pk=product_barcode)

    # Get data from the modal form
    price_str = request.POST.get('price', '').strip()
    category_id = request.POST.get('category_id') or None
    rack_id = request.POST.get('rack_id') or None

    try:
        # Get or create the defaults object
        obj, created = ProductPrice.objects.get_or_create(
            supermarket=supermarket,
            product=product
        )

        # Update fields from the form
        obj.default_category_id = category_id
        obj.default_rack_id = rack_id

        new_price = None
        if price_str:
            new_price = decimal.Decimal(price_str)
            obj.price = new_price
        else:
            obj.price = None  # Clear the price

        obj.save()
        messages.success(request, f"Defaults for {product.name} updated.")

        # --- CASCADING UPDATE LOGIC ---
        if new_price is not None:
            updated_count = InventoryItem.objects.filter(
                supermarket=supermarket,
                product=product,
                promotion__isnull=True,
                applied_rule__isnull=True
            ).update(store_price=new_price)

            if updated_count > 0:
                messages.info(request, f"Updated price for {updated_count} existing inventory batches.")

    except (decimal.InvalidOperation, ValueError):
        messages.error(request, "Invalid price format.")
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")

    # --- REDIRECT WITH ANCHOR ---
    list_url = reverse('product_pricing:product_price_list', args=[supermarket_id])
    query_params = request.META.get('HTTP_REFERER', '').split('?')[-1]
    final_url = f"{list_url}?{query_params}#product-row-{product.barcode}"

    return redirect(final_url)
