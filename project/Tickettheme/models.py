from django.db import models
from django.conf import settings
from Inventory.models import Product, Supermarket

class TicketTheme(models.Model):
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)

    # Colors
    background_color = models.CharField(max_length=20, default="#FFFFFF")
    text_color = models.CharField(max_length=20, default="#000000")
    accent_color = models.CharField(max_length=20, default="#FF0000")

    # Ticket dimensions
    width_mm = models.PositiveIntegerField(default=80)
    height_mm = models.PositiveIntegerField(default=50)

    # Auto styling
    match_product_color = models.BooleanField(default=False)

    def __str__(self):
        return self.name

# tickettheme/models.py

from django.db import models
from django.conf import settings
from Inventory.models import Product, Supermarket
from Tickettheme.models import TicketTheme


class TicketLabel(models.Model):
    """
    A printable label for a product at a specific supermarket.
    Stores snapshot data to avoid price inconsistency later.
    """

    # --- which store this ticket belongs to
    supermarket = models.ForeignKey(
        Supermarket,
        on_delete=models.CASCADE,
        related_name="ticket_labels"
    )

    # --- product reference (for name/brand/barcodes)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="ticketlabel"
    )

    # --- final price to print
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=False,
        blank=False,
        help_text="Final price to display on ticket"
    )

    # --- price per liter/kg
    price_per_liter = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="€/L or €/kg text snapshot"
    )

    # ======================
    # SNAPSHOT FIELDS
    # ======================
    # DO NOT trust live product fields after printing.
    # These values freeze the label details at print time.

    # product name snapshot
    product_name = models.CharField(max_length=255)

    # brand snapshot
    product_brand = models.CharField(
        max_length=120,
        null=True,
        blank=True
    )

    # primary barcode (CU = consumer unit)
    unit_barcode = models.CharField(
        max_length=32,
        null=True,
        blank=True
    )

    # carton / master barcode
    carton_barcode = models.CharField(
        max_length=32,
        null=True,
        blank=True
    )

    # how many units in the carton
    units_per_carton = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    include_carton_barcode = models.BooleanField(
        default=False,
        help_text="If true, carton barcode will be printed"
    )

    # ======================
    # PROMOTION SNAPSHOT
    # ======================
    promo_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="PERCENTAGE / FIXED / BOGO / MULTIPACK / None"
    )

    promo_display = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        help_text="Text shown on ticket (e.g. BUY 2 GET 1)"
    )

    promo_original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price before promo"
    )

    promo_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Effective promo price snapshot"
    )

    # ======================
    # THEME
    # ======================
    theme = models.ForeignKey(
        TicketTheme,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    # ======================
    # QUEUE STATUS
    # ======================
    created_at = models.DateTimeField(auto_now_add=True)
    printed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Null = waiting to print"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product_name} — {self.unit_price}€"



class LabelSheet(models.Model):
    name = models.CharField(max_length=50)

    # mm sizing
    label_width_mm = models.FloatField()
    label_height_mm = models.FloatField()

    cols = models.PositiveIntegerField()
    rows = models.PositiveIntegerField()

    margin_top_mm = models.FloatField(default=5)
    margin_left_mm = models.FloatField(default=5)
    gap_vertical_mm = models.FloatField(default=2)
    gap_horizontal_mm = models.FloatField(default=2)

    def __str__(self):
        return f"{self.name} ({self.cols}x{self.rows})"


