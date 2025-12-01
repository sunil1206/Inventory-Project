# packaging/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

from Inventory.models import Product, Supermarket, Supplier


class ProductPackaging(models.Model):
    """
    Maps a UNIT barcode (consumer unit / CU) to one or more CARTON barcodes (DU).
    Only superadmins should create/update these (enforced in views/admin).
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="packaging_options",
    )

    unit_barcode = models.CharField(
        max_length=50,
        help_text="Consumer Unit (CU) barcode — usually same as Product.barcode",
    )

    carton_barcode = models.CharField(
        max_length=50,
        help_text="Distribution Unit (DU) barcode — GTIN-14 / Code128 / internal",
    )

    units_per_carton = models.PositiveIntegerField(
        help_text="How many units in one carton (DU).",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional default supplier for this pack size.",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "unit_barcode", "carton_barcode")
        verbose_name = "Product Packaging"
        verbose_name_plural = "Product Packaging"

    def __str__(self):
        return f"{self.product.name} / {self.units_per_carton} units per carton"


class OrderBatch(models.Model):
    """
    One supplier order document per supermarket.
    """
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("finalized", "Finalized"),
    ]

    supermarket = models.ForeignKey(
        Supermarket,
        on_delete=models.CASCADE,
        related_name="order_batches",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_batches",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="order_batches",
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional internal reference / note for this order.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
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
        related_name="lines",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="order_lines",
    )

    # Which CU barcode we scanned (shelf label)
    unit_barcode = models.CharField(
        max_length=50,
        help_text="Consumer unit barcode (EAN-13).",
    )

    # Which carton config we are using (may be null if no mapping yet)
    packaging = models.ForeignKey(
        ProductPackaging,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_lines",
    )

    cartons = models.PositiveIntegerField(
        default=0,
        help_text="Number of cartons ordered.",
    )

    class Meta:
        unique_together = ("batch", "product", "unit_barcode", "packaging")

    def __str__(self):
        return f"{self.product.name} x {self.cartons} cartons"

    @property
    def units_per_carton(self) -> int:
        if self.packaging and self.packaging.units_per_carton:
            return self.packaging.units_per_carton
        return 1

    @property
    def carton_barcode(self) -> str:
        if self.packaging:
            return self.packaging.carton_barcode
        return ""

    @property
    def total_units(self) -> int:
        return self.cartons * self.units_per_carton


