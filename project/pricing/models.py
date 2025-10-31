from django.db import models

# Create your models here.
from Inventory.models import Product, Category, Supermarket, Supplier


class CompetitorPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='competitor_prices')
    competitor_name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    scraped_at = models.DateTimeField(auto_now_add=True)
    url = models.URLField(max_length=500, blank=True, null=True)

    class Meta: ordering = ['-scraped_at']

    def __str__(self): return f"{self.product.name} at {self.competitor_name}: {self.price}"


# --- NEW MODELS FOR COMPETITIVE STRATEGY ---

class PricingRule(models.Model):
    """
    Defines automated pricing strategies for a supermarket.
    A background task would periodically evaluate these rules against inventory.
    """

    class RuleType(models.TextChoices):
        MATCH_LOWEST = 'MATCH_LOWEST', 'Match Lowest Competitor'
        BEAT_LOWEST = 'BEAT_LOWEST', 'Beat Lowest Competitor by %'
        PROFIT_MARGIN = 'PROFIT_MARGIN', 'Maintain Profit Margin %'
        EXPIRY_DISCOUNT = 'EXPIRY_DISCOUNT', 'Discount by % based on Expiry'

    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='pricing_rules')
    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    amount = models.DecimalField(max_digits=5, decimal_places=2,
                                 help_text="Percentage value (e.g., 5 for 5%, 50 for 50%)")

    # Optional filters to apply the rule to specific items
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, null=True, blank=True)
    days_until_expiry = models.IntegerField(null=True, blank=True, help_text="Only for Expiry Discount rule type")

    priority = models.IntegerField(default=100, help_text="Lower number means higher priority.")
    is_active = models.BooleanField(default=True,
                                    help_text="Uncheck this to disable the promotion without deleting it.")

    class Meta:
        ordering = ['priority']

    def __str__(self):
        return f"{self.name} for {self.supermarket.name}"


class Promotion(models.Model):
    """
    Manages special sales events and promotions.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', 'Percentage Off'
        FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed Amount Off'

    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='promotions')
    name = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)

    # Apply promotion to specific products or whole categories
    products = models.ManyToManyField(Product, blank=True, related_name='promotions')
    categories = models.ManyToManyField(Category, blank=True, related_name='promotions')

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.start_date.date()} to {self.end_date.date()})"


# ... (existing imports and models: CompetitorPrice, PricingRule, Promotion, Advertisement) ...
# pricing/models.py
from django.db import models
from decimal import Decimal

# Assuming PricingRule and Promotion are defined in this file or imported
# Assuming Inventory.Product, Inventory.Supermarket, Inventory.Category are imported or use string refs

class DiscountedSale(models.Model):
    product = models.ForeignKey('Inventory.Product', on_delete=models.SET_NULL, null=True, related_name='sales_logs')
    supermarket = models.ForeignKey('Inventory.Supermarket', on_delete=models.CASCADE, related_name='sales_logs')
    category = models.ForeignKey('Inventory.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_logs')

    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_sold = models.PositiveIntegerField(default=1) # Renamed for clarity

    # Link to the specific rule OR promotion that influenced the price
    triggering_rule = models.ForeignKey(PricingRule, on_delete=models.SET_NULL, null=True, blank=True, help_text="The Pricing Rule applied, if any.")
    promotion = models.ForeignKey(Promotion, on_delete=models.SET_NULL, null=True, blank=True, help_text="The Promotion applied, if any.")

    date_sold = models.DateTimeField(auto_now_add=True)
    # Store the expiry date at the time of sale for analysis
    expiry_date_at_sale = models.DateField(null=True, blank=True) # Changed to allow null temporarily if needed

    def __str__(self):
        product_name = self.product.name if self.product else "[Deleted Product]"
        return f"Sold {self.quantity_sold}x {product_name} for €{self.final_price}"

    # Optional: Add a property to show which discount was applied
    @property
    def applied_discount_name(self):
        if self.promotion:
            return f"Promo: {self.promotion.name}"
        if self.triggering_rule:
             return f"Rule: {self.triggering_rule.name}"
        return "Manual Price / None"



class WastageRecord(models.Model):
    """
    Logs items that were removed as wastage (expired, damaged, etc.)
    """
    product = models.ForeignKey('Inventory.Product', on_delete=models.SET_NULL, null=True)
    supermarket = models.ForeignKey('Inventory.Supermarket', on_delete=models.CASCADE)
    category = models.ForeignKey('Inventory.Category', on_delete=models.SET_NULL, null=True, blank=True)
    quantity_wasted = models.PositiveIntegerField(default=1)
    date_removed = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(help_text="The expiry date of the item when it was wasted")

    def __str__(self):
        product_name = self.product.name if self.product else "[Deleted Product]"
        return f"Wasted {self.quantity_wasted}x {product_name}"

