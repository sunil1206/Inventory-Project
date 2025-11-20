# packaging/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

from Inventory.models import Product, Supermarket, Supplier


class ProductPackaging(models.Model):
    """
    Maps a UNIT barcode (consumer unit / CU) to an optional CARTON barcode (distribution unit / DU).
    You only enter the unit barcode when creating a Product.
    Carton barcode and units_per_carton can be added later when you scan the carton.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="packaging_options"
    )

    # Usually same as Product.barcode
    unit_barcode = models.CharField(
        max_length=50,
        help_text="Consumer Unit (CU) barcode — EAN-13"
    )

    # Optional until you scan the carton
    carton_barcode = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="Distribution Unit (DU) barcode — GTIN-14 / Code128 / internal"
    )

    units_per_carton = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="How many units in one carton (DU)."
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['unit_barcode', 'carton_barcode']
        verbose_name = "Product Packaging"
        verbose_name_plural = "Product Packaging"

    def __str__(self):
        base = f"{self.product.name} packaging"
        if self.units_per_carton:
            return f"{base} - {self.units_per_carton} units/carton"
        return base


class OrderBatch(models.Model):
    """
    One order document (for a supplier) containing multiple lines.
    """
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("finalized", "Finalized"),
    ]

    supermarket = models.ForeignKey(
        Supermarket,
        on_delete=models.CASCADE,
        related_name="order_batches"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="order_batches"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="order_batches"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional internal reference / note for this order."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OrderBatch #{self.id} - {self.supermarket.name} ({self.status})"


class OrderLine(models.Model):
    """
    One product line inside an OrderBatch.
    Quantity is expressed in cartons.
    """
    batch = models.ForeignKey(
        OrderBatch,
        on_delete=models.CASCADE,
        related_name="lines"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="order_lines"
    )
    unit_barcode = models.CharField(
        max_length=50,
        help_text="Consumer unit barcode (EAN-13)."
    )
    carton_barcode = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="Carton barcode if mapped."
    )
    units_per_carton = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="How many units in one carton."
    )
    cartons = models.PositiveIntegerField(
        default=0,
        help_text="Number of cartons ordered."
    )

    class Meta:
        unique_together = ["batch", "product", "unit_barcode"]

    def __str__(self):
        return f"{self.product.name} x {self.cartons} cartons"

    @property
    def total_units(self) -> int:
        upc = self.units_per_carton or 1
        return self.cartons * upc
