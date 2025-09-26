from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Supermarket(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_supermarkets')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True, help_text="A short description of the supermarket.")
    logo = models.ImageField(upload_to='supermarket_logos/', blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True,
                                help_text="e.g., Street Address, City, Postal Code")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(max_length=255, blank=True, null=True)
    opening_hours = models.JSONField(blank=True, null=True,
                                     help_text="e.g., {'Monday': '09:00-20:00', 'Tuesday': '09:00-20:00'}")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class StaffProfile(models.Model):
    ROLE_CHOICES = [('ADMIN', 'Administrator'), ('MANAGER', 'Manager'), ('STAFF', 'Staff')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staff_profiles')
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='staff_members')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='STAFF')
    can_edit_prices = models.BooleanField(default=False)
    can_delete_items = models.BooleanField(default=False)

    class Meta: unique_together = ('user', 'supermarket')

    def __str__(self): return f"{self.user.username} - {self.get_role_display()} at {self.supermarket.name}"


class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self): return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta: verbose_name_plural = "Categories"; ordering = ['name']

    def __str__(self): return self.name


class Product(models.Model):
    barcode = models.CharField(max_length=100, unique=True, primary_key=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=150, blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    suppliers = models.ManyToManyField(Supplier, blank=True, related_name='products')
    last_scraped = models.DateTimeField(auto_now=True)

    def __str__(self): return f"{self.name} ({self.barcode})"


class InventoryItem(models.Model):
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='inventory_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_instances')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    expiry_date = models.DateField()
    rack_zone = models.CharField(max_length=100, help_text="e.g., Aisle 5, R3 or F&V Section")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="The price paid to the supplier for this item.")
    store_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                      help_text="The current price the item is sold at in your store.")
    suggested_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                          help_text="Price suggested by the pricing strategy.")
    applied_rule = models.CharField(max_length=255, blank=True, null=True,
                                    help_text="The name of the pricing rule that was last applied.")
    promotion = models.ForeignKey('Promotion', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='inventory_items')
    added_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date']

    def __str__(self):
        return f"{self.product.name} in {self.supermarket.name} expires on {self.expiry_date}"

    @property
    def status(self):
        if not self.expiry_date: return 'unknown'
        today = timezone.now().date()
        days_left = (self.expiry_date - today).days
        if days_left < 0:
            return 'expired'
        elif days_left <= 1:
            return 'expires_today'
        elif days_left <= 7:
            return 'expires_soon'
        else:
            return 'fresh'


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

