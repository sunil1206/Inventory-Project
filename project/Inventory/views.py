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

from .models import Supermarket, Product, InventoryItem, Category, CompetitorPrice, StaffProfile, Supplier, PricingRule, \
    Promotion
from .tasks import scrape_product_task  # Correctly import the Celery task
from .scraping_utils import get_product_info_cascade  # Correctly import the cascade function


# --- Page Rendering Views ---

def landing_page_view(request):
    if request.user.is_authenticated:
        return redirect('inventory:home')
    return render(request, 'inventory/landing_page.html')


@login_required
def home_view(request):
    return render(request, 'inventory/home.html')


@login_required
def supermarket_dashboard_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    return render(request, 'inventory/dashboard.html', {'supermarket': supermarket})


@login_required
def scan_item_page_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    categories = Category.objects.all()
    return render(request, 'inventory/scan.html', {'supermarket': supermarket, 'categories': categories})


@login_required
def inventory_list_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        category_name = request.POST.get('name')
        if category_name:
            Category.objects.get_or_create(name__iexact=category_name, defaults={'name': category_name})
        return redirect('inventory:inventory_list', supermarket_id=supermarket.id)
    inventory_items = supermarket.inventory_items.all().select_related('product', 'category')
    categories = Category.objects.all()
    context = {'supermarket': supermarket, 'inventory_items': inventory_items, 'categories': categories}
    return render(request, 'inventory/inventory_list.html', context)


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


@login_required
def pricing_strategy_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        category_id = request.POST.get('category')
        supplier_id = request.POST.get('supplier')

        PricingRule.objects.create(
            supermarket=supermarket,
            name=request.POST.get('name'),
            rule_type=request.POST.get('rule_type'),
            amount=request.POST.get('amount'),
            category_id=category_id if category_id else None,
            supplier_id=supplier_id if supplier_id else None,
            days_until_expiry=request.POST.get('days_until_expiry') or None
        )
        return redirect('inventory:pricing_strategy', supermarket_id=supermarket.id)
    rules = supermarket.pricing_rules.all()
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()
    return render(request, 'inventory/management/pricing_strategy.html',
                  {'supermarket': supermarket, 'rules': rules, 'categories': categories, 'suppliers': suppliers})


@login_required
def promotion_list_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        Promotion.objects.create(supermarket=supermarket, name=request.POST.get('name'),
                                 start_date=request.POST.get('start_date'), end_date=request.POST.get('end_date'),
                                 discount_type=request.POST.get('discount_type'),
                                 discount_value=request.POST.get('discount_value'))
        return redirect('inventory:promotion_list', supermarket_id=supermarket.id)
    promotions = supermarket.promotions.all()
    return render(request, 'inventory/management/promotion_list.html',
                  {'supermarket': supermarket, 'promotions': promotions})


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_api(request):
    mode, barcode, supermarket_id = request.data.get('mode'), request.data.get('barcode'), request.data.get(
        'supermarket_id')
    if not all([mode, supermarket_id]): return Response({'error': 'Mode and supermarket_id are required.'}, status=400)
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if mode == 'lookup':
        if not barcode: return Response({'error': 'Barcode is required.'}, status=400)
        product, created = Product.objects.get_or_create(barcode=barcode)
        if created or not product.name or "Product " in product.name:
            product_info = get_product_info_cascade(barcode)
            product.name = product_info.get('name')
            product.brand = product_info.get('brand')
            product.image_url = product_info.get('image_url')
            product.description = product_info.get('description')
            product.save()
        inventory_items = InventoryItem.objects.filter(supermarket=supermarket, product=product)
        categories = list(Category.objects.values('id', 'name'))
        return Response({'product': {'barcode': product.barcode, 'name': product.name, 'brand': product.brand,
                                     'image_url': product.image_url},
                         'inventory_items': [{'id': item.id, 'quantity': item.quantity, 'expiry_date': item.expiry_date}
                                             for item in inventory_items], 'categories': categories})
    elif mode == 'add':
        product = get_object_or_404(Product, barcode=barcode)
        category = get_object_or_404(Category, id=request.data.get('category_id')) if request.data.get(
            'category_id') else None
        InventoryItem.objects.create(supermarket=supermarket, product=product, category=category,
                                     quantity=request.data.get('quantity', 1),
                                     expiry_date=request.data.get('expiry_date'),
                                     rack_zone=request.data.get('rack_zone', 'N/A'),
                                     store_price=request.data.get('store_price'))
        return Response({'message': f'{product.name} added.'}, status=201)
    elif mode == 'remove':
        item = get_object_or_404(InventoryItem, pk=request.data.get('inventory_item_id'), supermarket=supermarket)
        item.delete()
        return Response({'message': f'Batch of {item.product.name} removed.'})
    return Response({'error': 'Invalid mode specified.'}, status=400)


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
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()
    urgent_items = supermarket.inventory_items.filter(
        Q(expiry_date__lt=today) | Q(expiry_date__lte=today + timezone.timedelta(days=7))).select_related(
        'product').order_by('expiry_date')
    data = []
    for item in urgent_items:
        days_diff = (item.expiry_date - today).days
        data.append({'id': item.id, 'product': {'name': item.product.name, 'brand': item.product.brand,
                                                'image_url': item.product.image_url}, 'quantity': item.quantity,
                     'rack_zone': item.rack_zone, 'status': item.status,
                     'days_left': days_diff if days_diff >= 0 else 0,
                     'days_since_expiry': abs(days_diff) if days_diff < 0 else 0})
    return Response(data)

