import decimal

from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

# Create your views here.
from django.views.decorators.http import require_POST

from django.contrib import messages


# ... (all your existing imports) ...
from django.utils import timezone
from requests import Response
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from Inventory.models import Supermarket, InventoryItem, Category, Rack
from pricing.models import PricingRule, DiscountedSale, Promotion, WastageRecord  # ✅ Import models


@require_POST
@login_required(login_url='account_login')
def apply_discount_view(request, supermarket_id, item_id):
    """
    Applies an expiry-based discount to a specific inventory item.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)

    # Find the first-priority "Expiry Discount" rule for this supermarket
    rule = PricingRule.objects.filter(
        supermarket=supermarket,
        rule_type=PricingRule.RuleType.EXPIRY_DISCOUNT
    ).order_by('priority').first()

    if rule:
        if item.store_price:
            # Calculate the new price
            discount_multiplier = (100 - rule.amount) / 100
            new_price = round(item.store_price * discount_multiplier, 2)

            # Apply the new price and link the rule
            item.suggested_price = new_price
            item.applied_rule = rule  # Save the rule object (ForeignKey)
            item.save()
            messages.success(request, f"Discount of {rule.amount}% applied to {item.product.name}.")
        else:
            messages.error(request, f"Cannot apply discount: '{item.product.name}' has no base price set.")
    else:
        messages.warning(request, "No 'Expiry Discount' pricing rule has been set up for this supermarket.")

    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)


@require_POST
@login_required(login_url='account_login')
def mark_item_sold_view(request, supermarket_id, item_id):
    """
    Logs the discounted sale for analysis and then deletes the inventory item.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)

    # Log the sale to the new DiscountedSale table
    DiscountedSale.objects.create(
        product=item.product,
        supermarket=item.supermarket,
        category=item.get_category,  # Use the smart property
        original_price=item.store_price,
        final_price=item.suggested_price or item.store_price,  # Use discounted price if available
        quantity=item.quantity,
        triggering_rule=item.applied_rule  # Pass the rule object
    )

    item_name = item.product.name
    item.delete()  # Remove from inventory

    messages.success(request, f"Successfully logged sale of {item_name}.")
    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)


@require_POST
@login_required
def delete_inventory_item_from_alert(request, supermarket_id, item_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)
    item.delete()
    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)



# ... (rest of your views.py file) ...


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import PromotionForm, PricingRuleForm


@login_required(login_url='account_login')
def pricing_strategy_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        form = PricingRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.supermarket = supermarket
            rule.save()
            messages.success(request, 'New pricing rule created.')
            return redirect('pricing:pricing_strategy', supermarket_id=supermarket.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PricingRuleForm()

    rules = supermarket.pricing_rules.all().order_by('priority')
    context = {'supermarket': supermarket, 'rules': rules, 'form': form}
    return render(request, 'inventory/management/pricing_strategy.html', context)


@login_required(login_url='account_login')
def promotion_list_view(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    if request.method == 'POST':
        form = PromotionForm(request.POST)
        if form.is_valid():
            promotion = form.save(commit=False)
            promotion.supermarket = supermarket
            promotion.save()
            form.save_m2m()  # Save ManyToMany relationships
            messages.success(request, f"Promotion '{promotion.name}' created.")
            return redirect('pricing:promotion_list', supermarket_id=supermarket.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PromotionForm()

    promotions = supermarket.promotions.all().order_by('-start_date')
    context = {'supermarket': supermarket, 'promotions': promotions, 'form': form}
    return render(request, 'pricing/promotion_list.html', context)


# --- Alert Monitor & Item Action Views ---

@login_required(login_url='account_login')
# pricing/views.py

# ... (other imports)





# Add these imports at the top of pricing/views.py

# ... (other imports)

@login_required(login_url='account_login')
def alert_monitor_view(request, supermarket_id):
    """
    Displays items that are expired or expiring soon, pre-sorted into lists.
    This view is optimized to perform only one database query.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date()

    # 1. Fetch all urgent items ONCE...
    urgent_items_list = list(
        supermarket.inventory_items.filter(
            expiry_date__lt=today + timezone.timedelta(days=8)
        ).select_related(
            'product', 'applied_rule', 'category', 'promotion'  # ✅ ADD 'promotion' HERE
        ).order_by('expiry_date')
    )

    # ... (rest of your item sorting logic from line 2 to 5) ...
    expired_items, expires_today_items, expires_soon_items = [], [], []
    categories_set = set()
    racks_set = set()
    for item in urgent_items_list:
        status = item.status
        days_diff = (item.expiry_date - today).days

        if status == 'expired':
            item.days_since_expiry = abs(days_diff)
            expired_items.append(item)
        elif status == 'expires_today':
            item.days_left = 0
            expires_today_items.append(item)
        elif status == 'expires_soon':
            item.days_left = days_diff
            expires_soon_items.append(item)

    categories = Category.objects.all()
    # ✅ ADDED: Get all racks for this supermarket to populate the dropdown
    racks = Rack.objects.filter(supermarket=supermarket).order_by('name')

    # --- ✅ ADD THIS SECTION ---
    # Fetch active discounts for this supermarket to populate the modal dropdown
    # Fetch active discounts...
    active_rules = PricingRule.objects.filter(
        supermarket=supermarket
    ).order_by('name')

    active_promotions = Promotion.objects.filter(
        supermarket=supermarket,
        start_date__lte=today,
        end_date__gte=today
    ).order_by('name')
    # --- END ADDED SECTION ---

    # 6. Build the final context
    context = {
        'supermarket': supermarket,
        'expired_items': expired_items,
        'expires_today_items': expires_today_items,
        'expires_soon_items': expires_soon_items,
        'total_urgent_count': len(urgent_items_list),
        'available_categories': categories,
        'available_racks': racks,

        # --- ✅ ADD THESE LINES ---
        'active_rules': active_rules,
        'active_promotions': active_promotions,
        # --- END ADDED LINES ---
    }
    return render(request, 'inventory/alert_monitor.html', context)



@require_POST
@login_required(login_url='account_login')
def apply_specific_discount_view(request, supermarket_id, item_id):
    """
    Applies a *specific* Pricing Rule or Promotion to an item from the alert modal.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)

    discount_type = request.POST.get('discount_type')
    discount_id = request.POST.get('discount_id')

    if not item.store_price:
        messages.error(request, f"Cannot apply discount: '{item.product.name}' has no base price set.")
        return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)

    try:
        new_price = None
        applied_rule_obj = None
        applied_promo_obj = None
        rule_name = "Discount"

        if discount_type == 'rule':
            rule = get_object_or_404(PricingRule, pk=discount_id, supermarket=supermarket)
            discount_multiplier = (100 - rule.amount) / 100
            new_price = round(item.store_price * decimal.Decimal(discount_multiplier), 2)
            applied_rule_obj = rule
            rule_name = rule.name

        elif discount_type == 'promotion':
            promo = get_object_or_404(Promotion, pk=discount_id, supermarket=supermarket)
            if promo.discount_type == Promotion.DiscountType.PERCENTAGE:
                discount_multiplier = (100 - promo.discount_value) / 100
                new_price = round(item.store_price * decimal.Decimal(discount_multiplier), 2)
            else:  # Fixed amount
                new_price = item.store_price - promo.discount_value
            applied_promo_obj = promo
            rule_name = promo.name

        if new_price is not None and new_price >= 0:
            item.suggested_price = new_price
            item.applied_rule = applied_rule_obj
            item.promotion = applied_promo_obj
            item.save()
            messages.success(request, f"Discount '{rule_name}' applied to {item.product.name}.")
        else:
            messages.error(request, "Invalid discount type or price.")

    except Exception as e:
        messages.error(request, f"An error occurred: {e}")

    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)

# pricing/views.py
from django.views.decorators.http import require_POST
from django.db.models import F
from decimal import Decimal, InvalidOperation # Import InvalidOperation
# ... other imports ...

# --- API Endpoints ---
# pricing/views/api.py or pricing/views.py

from django.db.models import Q
from django.utils import timezone

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_discounts_api(request, supermarket_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    today = timezone.now().date() # Use date for comparison with rule days

    # Fetch active rules applicable to this supermarket or globally
    rules = PricingRule.objects.filter(
        Q(supermarket=supermarket) | Q(supermarket__isnull=True),
        is_active=True
    ).order_by('-priority', 'name') # Example ordering

    # Fetch active promotions applicable to this supermarket or globally
    promotions = Promotion.objects.filter(
        Q(supermarket=supermarket) | Q(supermarket__isnull=True),
        is_active=True,
        start_date__lte=timezone.now(), # Ensure promotion is currently active
        end_date__gte=timezone.now()
    ).order_by('name') # Example ordering

    rule_data = [{
        'id': rule.id,
        'name': rule.name,
        # ✅ RETURN ACTUAL DISCOUNT VALUE
        'discount_percentage': rule.discount_percentage,
        'details': f"{rule.discount_percentage}% off. Applies " +
                   (f"{rule.days_until_expiry_min}-" if rule.days_until_expiry_min is not None else "any day to ") +
                   (f"{rule.days_until_expiry_max} days" if rule.days_until_expiry_max is not None else "any day") +
                   " before expiry." +
                   (f" (Category: {rule.category.name})" if rule.category else "")
     } for rule in rules]

    promo_data = [{
        'id': promo.id,
        'name': promo.name,
         # ✅ RETURN ACTUAL DISCOUNT VALUE
        'discount_percentage': promo.discount_percentage,
        'details': f"{promo.discount_percentage}% off. {promo.description or ''}"
    } for promo in promotions]

    return Response({
        'rules': rule_data,
        'promotions': promo_data
    })

# --- ✅ ADD EDIT VIEW ---
@login_required(login_url='account_login')
def pricing_rule_edit_view(request, supermarket_id, rule_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    # Ensure the rule belongs to the supermarket (or adjust logic for global rules)
    rule = get_object_or_404(PricingRule, pk=rule_id, supermarket=supermarket)

    if request.method == 'POST':
        form = PricingRuleForm(request.POST, instance=rule)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Rule '{rule.name}' updated successfully.")
                return redirect('pricing:pricing_strategy', supermarket_id=supermarket.id)
            except IntegrityError as e:
                messages.error(request, f"Could not update rule: {e}")
            except ValueError as e:
                messages.error(request, f"Invalid input: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PricingRuleForm(instance=rule)

    context = {
        'supermarket': supermarket,
        'rule': rule,
        'form': form,
    }
    return render(request, 'pricing/pricing_rule_edit.html', context) # Use a new template


# --- ✅ ADD DELETE VIEW ---
@login_required(login_url='account_login')
@require_POST # Make sure deletion only happens via POST
def pricing_rule_delete_view(request, supermarket_id, rule_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    rule = get_object_or_404(PricingRule, pk=rule_id, supermarket=supermarket)
    rule_name = rule.name
    try:
        rule.delete()
        messages.success(request, f"Pricing rule '{rule_name}' has been deleted.")
    except Exception as e:
        messages.error(request, f"Could not delete rule: {e}")
    return redirect('pricing:pricing_strategy', supermarket_id=supermarket.id)

# ... your other pricing views (alert_monitor, mark_item_sold, api) ...

@require_POST
@login_required(login_url='account_login')
def remove_as_wastage_view(request, supermarket_id, item_id):
    """
    Logs an item as wastage and removes it from inventory.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem, pk=item_id, supermarket=supermarket)

    WastageRecord.objects.create(
        product=item.product,
        supermarket=item.supermarket,
        category=item.get_category,
        quantity_wasted=item.quantity,
        expiry_date=item.expiry_date,

    )

    item_name = item.product.name
    item_qty = item.quantity
    item.delete()  # Remove from inventory

    messages.success(request, f"Item '{item_name}' (Qty: {item_qty}) was logged as wastage and removed.")
    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)

# pricing/views.py
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import F
from django.db import IntegrityError
from decimal import Decimal, InvalidOperation

# Make sure all necessary models are imported

@require_POST
@login_required(login_url='account_login')
def mark_item_sold(request, supermarket_id, item_id):
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem.objects.select_related('product'), pk=item_id, supermarket=supermarket) # Select related product

    try:
        quantity_sold_str = request.POST.get('quantity_sold')
        final_price_str = request.POST.get('final_price')
        # GET DISCOUNT INFO FROM FORM
        discount_type = request.POST.get('discount_type') # 'rule' or 'promotion'
        discount_id_str = request.POST.get('discount_id') # ID of the rule/promo

        # Basic Validation
        if not quantity_sold_str or not final_price_str:
            raise ValueError("Quantity sold and final price are required.")

        quantity_sold = int(quantity_sold_str)
        final_price = Decimal(final_price_str).quantize(Decimal('0.01'))

        if quantity_sold <= 0:
            raise ValueError("Quantity sold must be positive.")
        if quantity_sold > item.quantity:
            raise ValueError(f"Cannot sell {quantity_sold}. Only {item.quantity} available.")
        if final_price < 0:
             raise ValueError("Final price cannot be negative.")

        # --- DETERMINE TRIGGERING RULE/PROMOTION ---
        triggering_rule_instance = None
        promotion_instance = None
        discount_id = None
        if discount_id_str:
            try:
                discount_id = int(discount_id_str)
            except ValueError:
                discount_id = None # Ignore invalid ID

        if discount_type == 'rule' and discount_id is not None:
            # Try to get the specific rule chosen in the modal
            try:
                # This query assumes you've added 'is_active' to your model
                triggering_rule_instance = PricingRule.objects.get(
                    pk=discount_id,
                    supermarket=supermarket,
                    is_active=True
                )
            except PricingRule.DoesNotExist:
                messages.warning(request, "Selected pricing rule was not found or is inactive. Sale logged without rule link.")
        elif discount_type == 'promotion' and discount_id is not None:
            # Try to get the specific promotion chosen in the modal
            try:
                # This query assumes you've added 'is_active' to your model
                promotion_instance = Promotion.objects.get(
                    pk=discount_id,
                    supermarket=supermarket,
                    is_active=True,
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                )
            except Promotion.DoesNotExist:
                messages.warning(request, "Selected promotion was not found or is inactive. Sale logged without promotion link.")
        # --- END DETERMINE TRIGGERING RULE/PROMOTION ---


        # Log the sale
        sale = DiscountedSale.objects.create(
            product=item.product,
            supermarket=supermarket,
            category=item.get_category, # Uses the property from InventoryItem
            original_price=item.store_price, # Log original price from item
            final_price=final_price,
            quantity_sold=quantity_sold,
            triggering_rule=triggering_rule_instance, # Log the specific rule if found
            promotion=promotion_instance, # Log the specific promotion if found
            expiry_date_at_sale=item.expiry_date # Log expiry date
            # date_sold is auto_now_add
        )

        # Update inventory
        if quantity_sold == item.quantity:
            item_name = item.product.name # Get name before delete
            item_pk = item.pk
            item.delete()
            messages.success(request, f"Sold out and removed {item_name} (Batch ID: {item_pk}). Sale logged (ID: {sale.id}).")
        else:
            item.quantity = F('quantity') - quantity_sold
            item.save()
            # Refresh to get the updated quantity for the message
            item.refresh_from_db()
            messages.success(request, f"Sold {quantity_sold} of {item.product.name} (Batch ID: {item.id}). {item.quantity} remaining. Sale logged (ID: {sale.id}).")

    except (ValueError, TypeError, InvalidOperation) as e:
        messages.error(request, f"Invalid input: {e}")
    except IntegrityError as e: # Catch potential DB errors during save/delete
        messages.error(request, f"Database error: Could not complete sale log or inventory update. {e}")
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")

    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)


# pricing/views.py

# ... (other imports) ...
from .models import WastageRecord  # Make sure this is imported


@require_POST
@login_required(login_url='account_login')
def mark_item_wastage(request, supermarket_id, item_id):
    """
    Marks a full or partial quantity of an item as wastage.
    """
    supermarket = get_object_or_404(Supermarket, pk=supermarket_id, owner=request.user)
    item = get_object_or_404(InventoryItem.objects.select_related('product', 'category'),
                             pk=item_id,
                             supermarket=supermarket)

    try:
        quantity_wasted_str = request.POST.get('quantity_wasted')

        if not quantity_wasted_str:
            raise ValueError("Wastage quantity is required.")

        quantity_wasted = int(quantity_wasted_str)

        if quantity_wasted <= 0:
            raise ValueError("Wastage quantity must be positive.")
        if quantity_wasted > item.quantity:
            raise ValueError(f"Cannot waste {quantity_wasted}. Only {item.quantity} available.")

        # 1. Log the wastage
        WastageRecord.objects.create(
            product=item.product,
            supermarket=supermarket,
            category=item.get_category,  # Use get_category property
            quantity_wasted=quantity_wasted,
            expiry_date=item.expiry_date
            # date_removed is auto_now_add
        )

        item_name = item.product.name
        item_pk = item.pk

        # 2. Update inventory
        if quantity_wasted == item.quantity:
            # Remove the item batch completely
            item.delete()
            messages.success(request,
                             f"Removed all {quantity_wasted} units of {item_name} (Batch ID: {item_pk}) as wastage.")
        else:
            # Decrease the quantity
            item.quantity = F('quantity') - quantity_wasted
            item.save()
            item.refresh_from_db()
            messages.success(request,
                             f"Removed {quantity_wasted} units of {item_name} (Batch ID: {item_pk}) as wastage. {item.quantity} remaining.")

    except (ValueError, TypeError, InvalidOperation) as e:
        messages.error(request, f"Invalid input: {e}")
    except IntegrityError as e:
        messages.error(request, f"Database error: Could not log wastage or update inventory. {e}")
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")

    return redirect('pricing:alert_monitor', supermarket_id=supermarket.id)