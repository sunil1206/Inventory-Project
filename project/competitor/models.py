from django.db import models
from django.utils import timezone
from Inventory.models import Product


# competitor/models.py

class Competitor(models.Model):
    SCRAPE_METHODS = [
        ("api", "API"),
        ("selenium", "Selenium"),
        ("html", "HTML"),
    ]

    name = models.CharField(max_length=100, unique=True)
    search_url_template = models.CharField(max_length=500)
    price_selector = models.CharField(max_length=200, blank=True, null=True)

    scrape_method = models.CharField(
        max_length=20,
        choices=SCRAPE_METHODS,
        default="selenium"
    )
    logo = models.ImageField(upload_to="competitor_logos/", null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class CompetitorPriceSnapshot(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="competitor_snapshots")
    competitor = models.ForeignKey(Competitor, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    scraped_at = models.DateTimeField(default=timezone.now)
    product_url = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        ordering = ["-scraped_at"]

    def __str__(self): return f"{self.price}€ - {self.product.name} @ {self.competitor.name}"


