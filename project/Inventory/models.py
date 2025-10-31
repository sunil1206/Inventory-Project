from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from project import settings


class Supermarket(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_supermarkets')
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profiles')
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
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Scraped image URL")

    # --- NEW FEATURE: Override Image ---
    cover_image = models.ImageField(
        upload_to='product_images/',
        blank=True, null=True,
        help_text="Upload an attractive image to override the scraped URL."
    )

    description = models.TextField(blank=True, null=True)
    quantity = models.CharField(max_length=100, blank=True, null=True)
    nutriscore_grade = models.CharField(max_length=1, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    suppliers = models.ManyToManyField(Supplier, blank=True, related_name='products')
    last_scraped = models.DateTimeField(null=True, blank=True)



    def __str__(self):
        return f"{self.name} ({self.barcode})"

    @property
    def display_image_url(self):
        """
        A property to intelligently show the best available image.
        It prioritizes the manually uploaded cover_image.
        """
        if self.cover_image:
            return self.cover_image.url
        if self.image_url:
            return self.image_url
        return 'https://placehold.co/300x300/F7F7F7/CCC?text=No+Image'


class Rack(models.Model):
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='racks')
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        # Ensures a supermarket cannot have two racks with the same name
        unique_together = ['supermarket', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.supermarket.name})"


class InventoryItem(models.Model):
    """
    Represents a specific batch of a product in a specific supermarket.
    This is the core model for all inventory tracking.
    """
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE, related_name='inventory_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_instances')

    # This category is specific to this batch, and can override the product's main category
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                 help_text="Overrides product's main category if set.")

    quantity = models.PositiveIntegerField(default=1)
    expiry_date = models.DateField()
    manufacture_date = models.DateField(null=True, blank=True, help_text="Optional: For data analysis")

    # This is the foreign key to your new Rack model
    rack = models.ForeignKey(Rack, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')

    store_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Use string 'app_label.ModelName' to prevent circular import errors

    applied_rule = models.ForeignKey(
        'pricing.PricingRule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The pricing rule that was last applied."
    )
    promotion = models.ForeignKey('pricing.Promotion', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='inventory_items')

    added_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date']
        # ✅ THIS IS THE RULE THAT PREVENTS DUPLICATES
        # It defines a "batch" as a unique combination of these 5 fields.
        unique_together = ['supermarket', 'product', 'expiry_date', 'store_price']

    class Meta:
        ordering = ['expiry_date']
        # This constraint prevents duplicate entries for the same batch
        unique_together = ['supermarket', 'product', 'expiry_date', 'rack', 'store_price']

    def __str__(self):
        return f"{self.product.name} ({self.quantity}) in {self.supermarket.name}"

    @property
    def get_category(self):
        """Returns the item-specific category if it exists, otherwise falls back to the product's main category."""
        return self.category or self.product.category

    @property
    def status(self):
        """Returns a string representing the expiry status of the item."""
        if not self.expiry_date:
            return 'unknown'
        today = timezone.now().date()
        days_left = (self.expiry_date - today).days

        if days_left < 0:
            return 'expired'
        elif days_left == 0:
            return 'expires_today'
        elif days_left <= 7:
            return 'expires_soon'
        else:
            return 'fresh'



class ProductPrice(models.Model):
    """
    Represents the default, user-defined price for a specific product
    at a specific supermarket. This is our main "Price List" table.
    """
    product = models.ForeignKey('Inventory.Product', on_delete=models.SET_NULL, null=True, related_name='price_listings')
    supermarket = models.ForeignKey('Inventory.Supermarket', on_delete=models.CASCADE, related_name='product_prices')
    product = models.ForeignKey('Inventory.Product', on_delete=models.CASCADE, related_name='price_listings')
    price = models.DecimalField(max_digits=5, decimal_places=2)
    # --- ADD THESE TWO NEW FIELDS ---
    default_category = models.ForeignKey(
        'Inventory.Category',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="The default category for this product at this supermarket."
    )
    default_rack = models.ForeignKey(
        'Inventory.Rack',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="The default rack for this product at this supermarket."
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        # A product can only have one default price per supermarket
        unique_together = ['supermarket', 'product']
        ordering = ['product__name']

    def __str__(self):
        return f"{self.product.name} at {self.supermarket.name}: {self.price}"

